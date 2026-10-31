# -*- coding: utf-8 -*-
"""TransCoder-NEXT experiment runner (P5/P6).

Experiment matrix (experiments-design.md §2): G0 direct / G1 direct-small /
G2 reflection-small / G3 iterative-small / G4 team-small / G5 team-hybrid.
Corpus + references live in RESULTS/corpus/dataset.json (built by
build_corpus.py, sourced & dated). Every run appends redacted events to
RESULTS/events_<group>.jsonl; per-pair metrics go to RESULTS/<G>/results.json;
aggregates to RESULTS/summary_table.csv and RESULTS/cost_report.json.

Usage:
    python run_experiment.py --dry                    # orchestration dry-run (no model calls)
    python run_experiment.py --groups G0,G5           # run a subset
    python run_experiment.py --dataset RESULTS/corpus/dataset.json --groups G0,G1,G2,G3,G4,G5
"""
from __future__ import annotations

import os

# Must be set before any HF `tokenizers` import in this process: on macOS the
# fast (Rust) tokenizer's parallel path segfaults in bert_score scoring
# (handoff 2026-10-19). bert_score is also called with use_fast_tokenizer=False.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
# libomp 多线程 worker 池在本机 (torch 2.14, macOS) 触发确定性段错误（.ips 崩溃栈
# __kmp_fork_barrier，2026-10-19 实测 OMP∈{2,4,6} 必崩、=1 必稳）；JUDGE.md 预注册
# 的"torch 线程 6"以 OMP=1 如实偏离并在事件流水记录。必须先于任何 torch import。
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import csv
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcoder.orchestrator import EventLog

REPO = Path(__file__).resolve().parent
RESULTS = REPO / "RESULTS"
sys.path.insert(0, str(REPO))

DEFAULT_TEMPERATURE = 0.3
TECH_TERMS = ("模型",)  # injected glossary via TerminologyService for C3

GROUPS = {
    "G0": "direct (online big model, upper reference)",
    "G1": "direct-small (edge small model)",
    "G2": "reflection-small (existing single-model loop, 1 iteration)",
    "G3": "iterative-small (existing loop, 5 iterations)",
    "G4": "team-small (edge translator + local small reviewer)",
    "G5": "team-hybrid (edge translator + online reviewer)",
}

ONLINE_REVIEWER = ("deepseek", "deepseek-chat")      # reachable, probe.json 2026-10-19
ALT_REVIEWER = ("cycleuser-halogen", "halogen-flash-v2")
ONLINE_DIRECT = ("deepseek", None)                   # model resolved from probe/config


# --------------------------------------------------------------------------- #
# data loading
# --------------------------------------------------------------------------- #

def load_dataset(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert data.get("schema") == "transcoder-next/dataset/v1", "bad dataset schema"
    return data


def corpus_of(dataset: dict, subset: Optional[str] = None):
    pairs = dataset["pairs"]
    if subset:
        wanted = {s.strip() for s in subset.split(",")}
        pairs = [p for p in pairs if p.get("subset") in wanted]
    return pairs


# Pre-registered G3 subset (RESULTS/JUDGE.md 执行细节 3, locked 2026-10-19):
# C1-la ch1 & ch8 × 5 方向 + C1-aq xu en + C3-tech1。
G3_SUBSET_IDS = (
    [f"la-ch{n}-{l}" for n in (1, 8) for l in ("en", "ja", "ko", "fr", "de")]
    + ["aq-xu-en", "c3-tech1"]
)


def corpus_of_g3(dataset: dict):
    ids = set(G3_SUBSET_IDS)
    return [p for p in dataset["pairs"] if p["pair_id"] in ids]


# --------------------------------------------------------------------------- #
# group execution
# --------------------------------------------------------------------------- #

class GroupRunner:
    def __init__(self, group: str, dataset: dict, temp: float = DEFAULT_TEMPERATURE,
                 seed: int = 42, max_rounds: int = 3, events_path: Optional[Path] = None,
                 edge_tag: str = "qwen3:0.6b", edge_reviewer_tag: str = "gemma3:270m",
                 pass_threshold: float = 7.0, pass_policy: str = "scores", use_guard: bool = True,
                 minimal_edit: bool = False, span_rewrite: bool = False,
                 reviewer: tuple = ONLINE_REVIEWER, terminology_db: Optional[str] = None):
        self.group = group
        self.dataset = dataset
        self.temp = temp
        self.seed = seed
        self.max_rounds = max_rounds
        self.edge_tag = edge_tag
        self.edge_reviewer_tag = edge_reviewer_tag
        self.pass_threshold = pass_threshold
        self.pass_policy = pass_policy
        self.use_guard = use_guard
        self.minimal_edit = minimal_edit
        self.span_rewrite = span_rewrite
        self.reviewer = reviewer
        self.terminology_db = terminology_db
        self.events_path = events_path or RESULTS / f"events_{group}.jsonl"
        self.rows: List[dict] = []
        self._edge_provider = None
        self._edge_reviewer_provider = None
        self._terminology = None

    # -- providers (lazy, one instance per process) ------------------------- #

    def edge_provider(self, tag: Optional[str] = None, temperature: float = DEFAULT_TEMPERATURE):
        tag = tag or self.edge_tag
        # GGUF path: when a local OpenAI-compatible endpoint is configured, use it
        # instead of loading safetensors through transformers.
        if os.environ.get("TRANSCODER_ENDPOINT_EDGE_GEN_BASE_URL"):
            if self._edge_provider is None:
                from transcoder.team_setup import provider_for_endpoint

                self._edge_provider = provider_for_endpoint("edge-gen", timeout=300)
            return self._edge_provider
        path = _edge_model_path(tag)
        if path is None:
            return None
        from transcoder.edge_local import EdgeTransformersProvider

        if self._edge_provider is None or self._edge_provider.model_tag != tag:
            # threads 参数交由 OMP_NUM_THREADS 环境变量控制（torch 2.14 + libomp 在本机
            # 多线程 worker 池触发确定性段错误，见 handoff.md 2026-10-19 记录）。
            self._edge_provider = EdgeTransformersProvider(model_path=path, model_tag=tag,
                                                           default_temperature=temperature)
        return self._edge_provider

    def edge_reviewer_provider(self, temperature: float = DEFAULT_TEMPERATURE):
        if os.environ.get("TRANSCODER_ENDPOINT_EDGE_REV_BASE_URL"):
            if self._edge_reviewer_provider is None:
                from transcoder.team_setup import provider_for_endpoint

                self._edge_reviewer_provider = provider_for_endpoint("edge-rev", timeout=300)
            return self._edge_reviewer_provider
        path = _edge_model_path(self.edge_reviewer_tag)
        if path is None:
            return None
        if self._edge_reviewer_provider is None:
            from transcoder.edge_local import EdgeTransformersProvider

            self._edge_reviewer_provider = EdgeTransformersProvider(
                model_path=path, model_tag=self.edge_reviewer_tag, default_temperature=temperature)
        return self._edge_reviewer_provider

    def terminology(self):
        if self._terminology is None:
            from transcoder.core import TerminologyService

            db = str(RESULTS / "terminology_exp") if self.terminology_db is None else self.terminology_db
            ts = TerminologyService(db_path=db)
            for term, translations in (self.dataset.get("glossary") or {}).items():
                ts.add_term(term, translations)
            self._terminology = ts
        return self._terminology

    # -- run one pair ------------------------------------------------------- #

    def run_pair(self, pair: dict, dry: bool = False) -> dict:
        src = pair["source_text"]
        tgt = pair["target_text"] if pair.get("direction") == "zh-tgt" else None
        source_lang, target_lang = pair["source_lang"], pair["target_lang"]
        ref = pair.get("reference")
        row = {
            "group": self.group, "pair_id": pair.get("pair_id", "?"), "subset": pair.get("subset", ""),
            "source_lang": source_lang, "target_lang": target_lang,
            "has_reference": bool(ref), "seed": self.seed,
            "source_tokens_o200k": _tc(src),
        }
        # Determinism for the legacy single-model loops (G2/G3): seed torch
        # sampling per pair. G1/G4/G5 already receive seed= via provider.chat();
        # the legacy service has no seed plumbing (JUDGE 执行细节 1: seed=42).
        if self.group in ("G1", "G2", "G3", "G4", "G5"):
            try:
                import torch

                torch.manual_seed(int(self.seed))
            except Exception:
                pass
        t0 = time.time()
        ev = EventLog(path=self.events_path)
        if self.group not in ("G4", "G5"):  # team groups: orchestrator logs its own full stream
            ev.log("pair.start", payload={"group": self.group, "pair_id": pair.get("pair_id", "?")})
        if self.group == "G0":
            out = self._run_online_direct(pair, dry)
        elif self.group in ("G1", "G2", "G3"):
            out = self._run_edge_mechanism(pair, dry)
        elif self.group == "G4":
            out = self._run_team(pair, dry, online_reviewer=False)
        elif self.group == "G5":
            out = self._run_team(pair, dry, online_reviewer=True)
        else:
            raise ValueError(f"unknown group {self.group}")
        elapsed = round(time.time() - t0, 2)
        row.update(out)
        row["wall_s"] = elapsed
        if self.group not in ("G4", "G5") and not dry:
            ev.log("pair.result", payload={"group": self.group, "pair_id": pair.get("pair_id", "?"),
                                           "error": row.get("error"),
                                           "wall_s": elapsed,
                                           "output_tokens_o200k": _tc(row.get("output") or "")})
        # evaluation (paper metrics; separate from any internal team check)
        if not dry:
            row["metrics"] = evaluate_pair(src, row.get("output") or "", ref, target_lang)
            if self.group not in ("G4", "G5"):
                ev.log("pair.metrics", payload={"group": self.group, "pair_id": pair.get("pair_id", "?"),
                                                "bleu": row["metrics"].get("bleu"),
                                                "chrf": row["metrics"].get("chrf"),
                                                "bert_f1": row["metrics"].get("bert_f1"),
                                                "rougeL": row["metrics"].get("rougeL"),
                                                "ter": row["metrics"].get("ter"),
                                                "length_ratio": row["metrics"].get("length_ratio")})
        self.rows.append(row)
        return row

    # -- group mechanisms --------------------------------------------------- #

    def _run_online_direct(self, pair: dict, dry: bool) -> dict:
        """G0: online big model direct translation (upper reference)."""
        if not self.reviewer or not self.reviewer[0]:
            return {"output": "", "error": "no online endpoint configured (G0 skipped)"}
        from transcoder.agents import TranslatorAgent
        from transcoder.team_setup import provider_for_endpoint

        try:
            prov = provider_for_endpoint(self.reviewer[0], self.reviewer[1])
        except ValueError as e:
            return {"output": "", "error": f"endpoint unavailable: {e}", "online_tokens": {}}
        agent = TranslatorAgent(prov, model=self.reviewer[1] or prov.default_model, temperature=self.temp)
        if dry:
            return {"output": "", "dry": True, "would_call": [agent.model]}
        out = agent.translate(pair["source_text"], pair["source_lang"], pair["target_lang"], seed=self.seed)
        return {"output": out.translation, "error": out.error,
                "online_tokens": {"in": out.tokens_in, "out": out.tokens_out},
                "latency_s": out.latency_s, "model": out.model}

    def _run_edge_mechanism(self, pair: dict, dry: bool) -> dict:
        """G1 direct (same TranslatorAgent prompt as team groups) / G2 reflection /
        G3 iterative via the EXISTING TranslationService (legacy prompts, per
        JUDGE.md 执行细节 7)."""
        from transcoder.core import TranslationService

        prov = self.edge_provider()
        if prov is None:
            return {"output": "", "error": "edge model unavailable"}
        svc = TranslationService(model=self.edge_tag, provider=prov)
        if dry:
            calls = {"G1": 1, "G2": 3, "G3": 11}[self.group]
            return {"output": "", "dry": True, "would_call": [f"{self.edge_tag} x{calls}"]}
        if self.group == "G1":
            from transcoder.agents import TranslatorAgent

            agent = TranslatorAgent(prov, model=self.edge_tag, temperature=self.temp)
            out = agent.translate(pair["source_text"], pair["source_lang"], pair["target_lang"], seed=self.seed)
            rec = {"output": out.translation, "error": out.error, "mechanism": "direct",
                   "model": out.model, "latency_s": out.latency_s}
            logs = getattr(prov, "gen_log", None) or []
            if logs and logs[-1].get("tok_s"):
                rec["edge_tok_s"] = logs[-1]["tok_s"]
            return rec
        iterations = 1 if self.group == "G2" else 5
        mech = "reflection" if self.group == "G2" else "iterative"
        r = svc.translate_with_reflection(pair["source_text"], pair["source_lang"], pair["target_lang"],
                                          model=self.edge_tag, iterations=iterations)
        if r.success:
            gens = (getattr(prov, "gen_log", None) or [])[-3 * iterations :] if iterations else []
            tokss = [g["tok_s"] for g in gens if g.get("tok_s")]
            return {"output": r.data.get("text", ""), "mechanism": mech,
                    "rounds": len(r.data.get("reflection_history", [])),
                    "edge_tok_s": round(statistics.mean(tokss), 2) if tokss else None}
        return {"output": "", "error": r.error, "mechanism": mech}

    def _run_team(self, pair: dict, dry: bool, online_reviewer: bool) -> dict:
        """G4 (edge reviewer) / G5 (online reviewer); degraded chain per spec §2."""
        from transcoder.core import TranslationService
        from transcoder.orchestrator import EventLog

        prov = self.edge_provider()
        if prov is None:
            return {"output": "", "error": "edge model unavailable"}

        if self.group == "G4":
            rprov = self.edge_reviewer_provider()
            rmodel = self.edge_reviewer_tag
        else:
            rprov_name, rmodel = self.reviewer
            try:
                from transcoder.team_setup import provider_for_endpoint

                rprov = provider_for_endpoint(rprov_name, rmodel)
            except ValueError as e:
                rprov, rmodel = None, None

        run_key = f"{pair.get('pair_id','?')}_{self.seed}"
        ev = EventLog(path=self.events_path)
        from transcoder.team_setup import build_team

        orch = build_team(
            translator_provider=prov, translator_model=self.edge_tag,
            reviewer_provider=rprov, reviewer_model=rmodel,
            terminology_service=self.terminology() if self.use_guard else None, vector_db_service=None,
            local_fallback=TranslationService(model=self.edge_tag, provider=prov),
            max_rounds=self.max_rounds, temperature=self.temp, event_log=ev, seed=self.seed,
            pass_threshold=self.pass_threshold, pass_policy=self.pass_policy,
            minimal_edit=self.minimal_edit, span_rewrite=self.span_rewrite,
        )
        if dry:
            # dry planning without reviewer availability probing cost: force dry plan
            result = orch.run(pair["source_text"], pair["source_lang"], pair["target_lang"], dry=True)
            return {"dry": True, "degraded": result.degraded, "degraded_reason": result.degraded_reason}
        result = orch.run(pair["source_text"], pair["source_lang"], pair["target_lang"], dry=False)
        out = {"degraded": result.degraded, "degraded_reason": result.degraded_reason,
               "rounds": len(result.rounds), "model": self.edge_tag,
               "reviewer_model": rmodel, "reviewer_kind": "online" if online_reviewer else "edge"}
        out["output"] = result.final_translation
        if result.final_review:
            fr = result.final_review
            out["review_scores"] = fr.get("scores") or {}
            out["review_pass"] = fr.get("passed")
            out["review_parse_ok"] = fr.get("parse_ok")
        if result.degraded:
            out["online_tokens"] = {"in": 0, "out": 0}
        elif self.group == "G5":
            out["online_tokens"] = {"in": result.tokens.get("reviewer_in", 0),
                                    "out": result.tokens.get("reviewer_out", 0)}
        out["team_tokens"] = result.tokens
        return out


# --------------------------------------------------------------------------- #
# metrics / aggregation
# --------------------------------------------------------------------------- #

def _tc(text: str) -> int:
    if not text:
        return 0
    from transcoder.tokcount import count_tokens

    return count_tokens(text)


def evaluate_pair(source: str, hyp: str, ref: Optional[str], target_lang: str) -> dict:
    """Paper metrics. With reference: BLEU+chrF(sacrebleu)+ROUGE-L+BERTScore(+TER).
    Without: length-ratio + chrF-free 'no-reference' flags only (experiments-design §1/§6)."""
    out = {"no_reference": ref is None}
    if not hyp:
        out["error"] = "empty hypothesis"
        return out
    out["length_ratio"] = round((len(hyp) / len(source)) if source else 0.0, 3)
    if not ref:
        return out
    import sacrebleu

    tok = {"en": "13a", "fr": "13a", "de": "13a", "es": "13a"}.get(target_lang, "char")
    try:
        bleu = sacrebleu.corpus_bleu([hyp], [[ref]], tokenize=tok, lowercase=True)
        out["bleu"] = round(bleu.score, 2)
        chrf = sacrebleu.corpus_chrf([hyp], [[ref]], word_order=2, beta=2.0)
        out["chrf"] = round(chrf.score, 2)
        from sacrebleu.metrics import TER

        ter = TER()
        out["ter"] = round(ter.corpus_score([hyp], [[ref]]).score, 2)
    except Exception as e:
        out["bleu_error"] = str(e)[:200]
    try:
        from rouge_score import rouge_scorer

        rs = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
        s = rs.score(ref, hyp)
        out["rougeL"] = round(s["rougeL"].fmeasure, 3)
    except Exception as e:
        out["rougeL_error"] = str(e)[:200]
    try:
        # JUDGE.md 判据①口径：全语对统一 bert-base-multilingual-cased（不加 rescale）。
        # use_fast_tokenizer=False + TOKENIZERS_PARALLELISM=false (module top):
        # macOS segfault mitigation, verified 2026-10-19 (bert_score 0.3.12).
        # BERTScorer 进程内缓存（bert_score.score() 每次调用都重载权重 ~5s，38 对 × 6 组
        # 纯属浪费；数值口径不变——同模型同层、无 rescale baseline）。
        global _BS_SCORER
        if _BS_SCORER is None:
            from bert_score import BERTScorer

            _BS_SCORER = BERTScorer(model_type="bert-base-multilingual-cased",
                                    device="cpu", use_fast_tokenizer=False)
        _, _, F = _BS_SCORER.score([hyp], [ref])
        out["bert_f1"] = round(float(F[0]), 3)
    except Exception as e:
        out["bert_error"] = str(e)[:200]
    return out


_BS_SCORER: Optional[object] = None


def write_results(group: str, runner: GroupRunner, filename: str = "results.json") -> Path:
    out_dir = RESULTS / group
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    if path.exists():
        # archive-before-overwrite: keep every prior version (RESULTS/archive/<ts>/<G>/)
        ar = RESULTS / "archive" / time.strftime("%Y%m%d_%H%M%S") / group
        ar.mkdir(parents=True, exist_ok=True)
        (ar / filename).write_bytes(path.read_bytes())
    doc = {
        "schema": "transcoder-next/results/v1",
        "group": group,
        "description": GROUPS[group],
        "temperature": runner.temp,
        "seed": runner.seed,
        "translator_model": runner.edge_tag,
        "reviewer": list(runner.reviewer),
        "n_pairs": len(runner.rows),
        "rows": runner.rows,
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def aggregate(groups: List[str]) -> Path:
    """RESULTS/summary_table.csv — one row per (group, pair)."""
    out_path = RESULTS / "summary_table.csv"
    cols = ["group", "pair_id", "subset", "source_lang", "target_lang", "has_reference",
            "bleu", "chrf", "rougeL", "bert_f1", "ter", "length_ratio", "online_tokens_in",
            "online_tokens_out", "rounds", "degraded", "review_pass", "review_parse_ok",
            "latency_s", "wall_s", "error"]
    rows_out = []
    for g in groups:
        p = RESULTS / g / "results.json"
        if not p.exists():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        for r in doc["rows"]:
            on = r.get("online_tokens") or {}
            m = r.get("metrics") or {}
            rows_out.append({
                "group": g, "pair_id": r.get("pair_id", ""), "subset": r.get("subset", ""),
                "source_lang": r.get("source_lang", ""), "target_lang": r.get("target_lang", ""),
                "has_reference": m.get("no_reference") is False,
                "bleu": m.get("bleu", ""), "chrf": m.get("chrf", ""),
                "rougeL": m.get("rougeL", ""), "bert_f1": m.get("bert_f1", ""),
                "ter": m.get("ter", ""), "length_ratio": m.get("length_ratio", ""),
                "online_tokens_in": on.get("in", ""), "online_tokens_out": on.get("out", ""),
                "rounds": r.get("rounds", ""), "degraded": r.get("degraded", ""),
                "review_pass": r.get("review_pass", ""), "review_parse_ok": r.get("review_parse_ok", ""),
                "latency_s": r.get("latency_s", ""), "wall_s": r.get("wall_s", ""),
                "error": (r.get("error") or "")[:120],
            })
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows_out)
    return out_path


def cost_report(groups: List[str]) -> Path:
    """RESULTS/cost_report.json — online tokens per group (o200k accounting)."""
    from transcoder.tokcount import count_tokens

    report = {"schema": "transcoder-next/cost/v1", "date": "2026-10-19",
              "unit": "o200k tokens (uniform accounting; vendor rate application below)",
              "groups": {}}
    for g in groups:
        p = RESULTS / g / "results.json"
        if not p.exists():
            report["groups"][g] = {"missing": True}
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        tin = sum((r.get("online_tokens") or {}).get("in", 0) for r in doc["rows"])
        tout = sum((r.get("online_tokens") or {}).get("out", 0) for r in doc["rows"])
        report["groups"][g] = {"calls_with_online": sum(1 for r in doc["rows"] if r.get("online_tokens")),
                               "online_tokens_in": tin, "online_tokens_out": tout,
                               "total_online": tin + tout}
    path = RESULTS / "cost_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# edge model registry
# --------------------------------------------------------------------------- #

def _edge_model_path(tag: str) -> Optional[str]:
    log_path = RESULTS / "edge_download_log.json"
    if not log_path.exists():
        return None
    log = json.loads(log_path.read_text(encoding="utf-8"))
    entry = log.get(tag)
    if entry and entry.get("ok"):
        return entry.get("path")
    return None


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(prog="run_experiment", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default=str(RESULTS / "corpus" / "dataset.json"))
    parser.add_argument("--groups", default="G0,G1,G2,G3,G4,G5")
    parser.add_argument("--subset", default=None, help="filter corpus subset (c1|c2|c3)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--team-rounds", type=int, default=3)
    parser.add_argument("--span-rewrite", action="store_true",
                        help="rewrite only the quoted spans and splice them back (ablation)")
    parser.add_argument("--minimal-edit", action="store_true",
                        help="reject rewrites that change text no issue quotes (ablation)")
    parser.add_argument("--no-guard", action="store_true",
                        help="disable the terminology/memory guard (ablation)")
    parser.add_argument("--reviewer", default="deepseek", help="online reviewer endpoint")
    parser.add_argument("--reviewer-model", default="deepseek-chat")
    parser.add_argument("--refs-only", action="store_true",
                        help="only pairs with a reference translation (stability subset)")
    parser.add_argument("--dry", action="store_true", help="orchestration only, no model calls")
    parser.add_argument("--pass-threshold", type=float, default=7.0,
                        help="rubric score at or above which a review passes (default 7.0)")
    parser.add_argument("--pass-policy", default="scores", choices=("scores", "model", "both"),
                        help="who decides pass: rubric scores (default), the model's own flag, or both")
    args = parser.parse_args()

    dataset = load_dataset(Path(args.dataset))
    groups = [g.strip() for g in args.groups.split(",") if g.strip()]
    pairs = corpus_of(dataset, args.subset)
    if args.refs_only:
        pairs = [p for p in pairs if p.get("reference")]
    tag = time.strftime("%H%M%S")
    print(f"dataset={args.dataset} pairs={len(pairs)} groups={groups} seed={args.seed} dry={args.dry}")

    # Pre-probe edge models (P6 edge protocol): presence + tok/s per call below.
    for g in groups:
        g_pairs = corpus_of_g3(dataset) if (g == "G3" and not args.subset and not args.refs_only) else pairs
        # one event file per (group, seed, run): raw data is append-only, never overwritten
        events_path = RESULTS / f"events_{g}_s{args.seed}_{tag}.jsonl"
        edge_tag = os.environ.get("TRANSCODER_ENDPOINT_EDGE_GEN_MODELS") or "qwen3:0.6b"
        edge_rev_tag = os.environ.get("TRANSCODER_ENDPOINT_EDGE_REV_MODELS") or "gemma3:270m"
        runner = GroupRunner(g, dataset, seed=args.seed, max_rounds=args.team_rounds, events_path=events_path,
                             edge_tag=edge_tag, edge_reviewer_tag=edge_rev_tag,
                             pass_threshold=args.pass_threshold, pass_policy=args.pass_policy,
                             use_guard=not args.no_guard, minimal_edit=args.minimal_edit,
                             span_rewrite=args.span_rewrite,
                             reviewer=(args.reviewer, args.reviewer_model) if args.reviewer != "none" else (None, None))
        for i, pair in enumerate(g_pairs):
            print(f"[{g}] {i + 1}/{len(g_pairs)} {pair.get('pair_id', i)} {pair['source_lang']}->{pair['target_lang']} ...",
                  flush=True)
            try:
                row = runner.run_pair(pair, dry=args.dry)
                m = row.get("metrics") or {}
                print(f"    out={'.' if args.dry else (row.get('output') or '')[:60]!r} "
                      f"bleu={m.get('bleu')} chrf={m.get('chrf')} bert={m.get('bert_f1')}" +
                      (f" err={row.get('error')}" if row.get("error") else ""), flush=True)
            except KeyboardInterrupt:
                print(f"[{g}] interrupted; partial results written", flush=True)
                break
            except Exception as e:
                runner.rows.append({
                    "group": g, "pair_id": pair.get("pair_id", "?"), "subset": pair.get("subset", ""),
                    "source_lang": pair["source_lang"], "target_lang": pair["target_lang"],
                    "has_reference": bool(pair.get("reference")), "seed": args.seed,
                    "error" : f"{type(e).__name__}: {e}", "output": "",
                })
                print(f"    ERROR {type(e).__name__}: {e}", flush=True)
        if runner.rows:
            # 主矩阵（seed=42, 全量）写 results.json；稳定性/子集运行落独立文件，不覆盖
            is_main = args.seed == 42 and not args.refs_only
            fn = "results.json" if is_main else f"results_s{args.seed}{'_refs' if args.refs_only else ''}.json"
            p = write_results(g, runner, fn)
            print(f"    -> {p}")
            # edge tok/s honest record whenever edge inference ran
            if runner._edge_provider is not None and getattr(runner._edge_provider, "gen_log", None):
                es = RESULTS / f"edge_tok_s_{g}.json"
                es.write_text(json.dumps({"tag": runner.edge_tag, "gen_log": runner._edge_provider.gen_log},
                                         ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.dry and args.seed == 42 and not args.refs_only:
        sp = aggregate(groups)
        cp = cost_report(groups)
        print(f"summary -> {sp}\ncost    -> {cp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())