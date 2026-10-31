#!/usr/bin/env python3
"""Recompute the Condition-B table with empty outputs scored as 0 BLEU.

Three cells in the four G5 seeds returned an empty translation; the metric
layer recorded `error: empty hypothesis` and dropped them, which inflated the
pooled score. This script rebuilds every aggregate under the defensible
convention (a call that returns nothing scores 0) and writes the numbers the
manuscript must quote.
"""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "gguf_matrix_summary_corrected.json"
BOOT = 10_000
RNG = random.Random(20261021)


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


def cells(d: dict) -> dict[str, tuple[float, bool]]:
    """pair_id -> (bleu or 0 if empty, was_empty)"""
    out = {}
    for row in d["rows"]:
        if not row.get("has_reference"):
            continue
        m = row["metrics"] or {}
        empty = m.get("error") == "empty hypothesis" or m.get("bleu") is None
        out[row["pair_id"]] = (0.0 if empty else float(m["bleu"]), empty)
    meta = {
        "target": {r["pair_id"]: r["target_lang"] for r in d["rows"] if r.get("has_reference")},
        "tokens": {r["pair_id"]: sum((r.get("online_tokens") or {}).values()) for r in d["rows"] if r.get("has_reference")},
        "wall": {r["pair_id"]: (r.get("wall_s") or 0.0) for r in d["rows"] if r.get("has_reference")},
        "pass": {r["pair_id"]: bool(r.get("review_pass")) for r in d["rows"] if r.get("has_reference")},
    }
    out["__meta__"] = meta  # type: ignore[assignment]
    return out


def bleu_map(c: dict) -> dict[str, float]:
    return {k: v[0] for k, v in c.items() if k != "__meta__"}


def boot_ci(values: list[float]) -> tuple[float, float]:
    n = len(values)
    means = []
    for _ in range(BOOT):
        means.append(sum(values[RNG.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return means[int(0.025 * BOOT)], means[int(0.975 * BOOT) - 1]


def main() -> None:
    g0 = bleu_map(cells(load("RESULTS/G0/results_s42_refs.json")))
    g1 = bleu_map(cells(load("RESULTS/G1/results_s42_refs.json")))
    g4 = bleu_map(cells(load("RESULTS/G4/results_s42_refs.json")))
    seeds = ["s42", "s43", "s44", "s45"]
    g5 = {s: cells(load(f"RESULTS/G5/results_{s}_refs.json")) for s in seeds}
    pair_ids = sorted(g1)

    # per-pair mean across seeds, empty = 0
    per_pair = {p: statistics.mean(g5[s][p][0] for s in seeds) for p in pair_ids}
    run_means = {s: statistics.mean(g5[s][p][0] for p in pair_ids) for s in seeds}

    summary = {
        "convention": "a call that returns an empty translation scores 0 BLEU",
        "empty_cells": {s: [p for p in pair_ids if g5[s][p][1]] for s in seeds},
        "n_empty_cells": sum(1 for s in seeds for p in pair_ids if g5[s][p][1]),
        "n_cells": len(seeds) * len(pair_ids),
        "G0": round(statistics.mean(g0.values()), 2),
        "G1": round(statistics.mean(g1.values()), 2),
        "G4": round(statistics.mean(g4.values()), 2),
        "G5": round(statistics.mean(per_pair.values()), 2),
        "G5_run_means": {s: round(v, 2) for s, v in run_means.items()},
        "G5_run_sd": round(statistics.stdev(run_means.values()), 2),
        "delta_vs_G1": round(statistics.mean(per_pair[p] - g1[p] for p in pair_ids), 2),
        "per_pair": {p: round(v, 2) for p, v in per_pair.items()},
        "G1_per_pair": {p: round(v, 2) for p, v in g1.items()},
    }

    delta_pairs = [per_pair[p] - g1[p] for p in pair_ids]
    lo, hi = boot_ci(delta_pairs)
    summary["delta_ci_pair"] = [round(lo, 2), round(hi, 2)]
    summary["pairs_positive"] = sum(1 for d in delta_pairs if d > 0)

    # run-level: resample the four runs, each contributing its own 14-pair delta mean
    run_deltas = [statistics.mean(g5[s][p][0] - g1[p] for p in pair_ids) for s in seeds]
    summary["run_deltas"] = [round(d, 2) for d in run_deltas]
    n = len(run_deltas)
    means = []
    for _ in range(BOOT):
        pick = [run_deltas[RNG.randrange(n)] for _ in range(n)]
        means.append(sum(pick) / n)
    means.sort()
    summary["delta_ci_run"] = [round(means[int(0.025 * BOOT)], 2), round(means[int(0.975 * BOOT) - 1], 2)]

    # per target language
    meta = g5["s42"]["__meta__"]
    by_lang = {}
    for lang in ("en", "fr", "ja"):
        ids = [p for p in pair_ids if meta["target"][p] == lang]
        d = [per_pair[p] - g1[p] for p in ids]
        lo, hi = boot_ci(d)
        by_lang[lang] = {
            "n": len(ids),
            "G1": round(statistics.mean(g1[p] for p in ids), 2),
            "G5": round(statistics.mean(per_pair[p] for p in ids), 2),
            "delta": round(statistics.mean(d), 2),
            "ci": [round(lo, 2), round(hi, 2)],
            "pairs_up": sum(1 for x in d if x > 0),
        }
    summary["by_language"] = by_lang

    # robustness: drop the largest-gain pair
    worst = max(pair_ids, key=lambda p: per_pair[p] - g1[p])
    rest = [per_pair[p] - g1[p] for p in pair_ids if p != worst]
    lo, hi = boot_ci(rest)
    summary["drop_largest"] = {"pair": worst, "delta": round(statistics.mean(rest), 2),
                               "ci": [round(lo, 2), round(hi, 2)]}

    # tokens / latency
    tok = [g5[s]["__meta__"]["tokens"][p] for s in seeds for p in pair_ids]
    walls = sorted(g5[s]["__meta__"]["wall"][p] for s in seeds for p in pair_ids)
    summary["tokens_mean"] = round(statistics.mean(tok), 0)
    summary["token_ratio_vs_G0"] = round(statistics.mean(tok) / (3244 / 14), 2)
    summary["wall_median"] = round(statistics.median(walls), 1)
    summary["pass_per_run"] = {s: sum(1 for p in pair_ids if g5[s]["__meta__"]["pass"][p]) for s in seeds}

    # round dose, empty = 0
    def arm(path: str) -> dict:
        c = cells(load(path))
        return {p: c[p][0] for p in pair_ids if p in c}

    r1 = arm("RESULTS/G5/results_s42_rounds1.json")
    r2 = {}
    for s in seeds:
        for cand in (f"RESULTS/G5/results_{s}_r2.json", f"RESULTS/G5/results_{s}_rounds2.json"):
            if (ROOT / cand).exists():
                r2[s] = arm(cand)
                break
        else:
            r2[s] = arm("RESULTS/G5/results_s42_rounds2.json")
    summary["rounds"] = {
        "1": {"bleu": round(statistics.mean(r1.values()), 2), "n": len(r1)},
        "2": {"bleu": round(statistics.mean(statistics.mean(r2[s].get(p, 0.0) for s in seeds) for p in pair_ids), 2)},
        "3": {"bleu": summary["G5"]},
    }
    d32 = [statistics.mean(g5[s][p][0] for s in seeds) - statistics.mean(r2[s].get(p, 0.0) for s in seeds) for p in pair_ids]
    lo, hi = boot_ci(d32)
    summary["rounds"]["paired_3_vs_2"] = {"delta": round(statistics.mean(d32), 2),
                                          "ci": [round(lo, 2), round(hi, 2)],
                                          "pairs_up": sum(1 for x in d32 if x > 0)}

    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("per_pair", "G1_per_pair")},
                     indent=2, ensure_ascii=False))
    print("written:", OUT)


if __name__ == "__main__":
    main()
