#!/usr/bin/env python3
"""A/B check: the two GGUF on-device models vs the numbers in the paper.

Runs the 14 reference pairs through edge translation (Qwen3.5-2B) and then the
strict reviewer (LFM2.5-1.2B), using the same prompts and validator as the
pipeline, and reports parse rate, BLEU and latency.

Usage:
  TRANSCODER_ENDPOINT_EDGE_GEN_BASE_URL=... TRANSCODER_ENDPOINT_EDGE_REV_BASE_URL=...
  python RESULTS/tools/gguf_abtest.py [--limit N]
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import time
from pathlib import Path

import sacrebleu

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from transcoder.agents import ReviewerAgent, TranslatorAgent  # noqa: E402
from transcoder.team_setup import provider_for_endpoint  # noqa: E402

TOK = {"en": "13a", "fr": "13a", "ja": "char", "de": "13a", "ko": "char"}
SYSTEM = ("You are a professional translator. Translate the source text into the target "
          "language. Output only the translation, with no notes or commentary.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    data = json.loads((ROOT / "RESULTS/corpus/dataset.json").read_text())
    pairs = [p for p in data["pairs"] if p.get("reference") and str(p["reference"]) != "None"]
    if args.limit:
        pairs = pairs[: args.limit]
    pairs.sort(key=lambda p: p["pair_id"])

    gen = provider_for_endpoint("edge-gen", timeout=300)
    rev = provider_for_endpoint("edge-rev", timeout=300)
    translator = TranslatorAgent(gen, model="Qwen3.5-2B-Q4_K_M.gguf", temperature=0.3)
    reviewer = ReviewerAgent(rev, model="LFM2.5-1.2B-Instruct-Q4_K_M.gguf", temperature=0.0)

    rows, t_all = [], time.time()
    for p in pairs:
        t0 = time.time()
        out = translator.translate(
            source_text=p["source_text"], source_lang=p["source_lang"], target_lang=p["target_lang"],
            system=SYSTEM, user=None) if False else None
        # TranslatorAgent.translate signature varies; call the provider directly with the same shape.
        text, usage = gen.chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": f"Target language: {p['target_lang']}\n\n{p['source_text']}"}],
            model="Qwen3.5-2B-Q4_K_M.gguf", temperature=0.3)
        text = (text or "").strip()
        rv = reviewer.review(p["source_text"], text, p["source_lang"], p["target_lang"], strict=True)
        bleu = sacrebleu.sentence_bleu(text, [p["reference"]],
                                       tokenize=TOK.get(p["target_lang"], "13a")).score
        rows.append({"pair": p["pair_id"], "lang": p["target_lang"], "bleu": bleu,
                     "parse_ok": rv.parse_ok, "passed": rv.passed, "secs": time.time() - t0,
                     "chars": len(text)})
        print(f"  {p['pair_id']:16s} {p['target_lang']:3s} bleu={bleu:5.2f} "
              f"parse_ok={rv.parse_ok!s:5s} pass={rv.passed!s:5s} {rows[-1]['secs']:.1f}s")

    print()
    print(f"pairs           : {len(rows)}")
    print(f"parse_ok rate   : {sum(r['parse_ok'] for r in rows)}/{len(rows)} "
          f"= {100*sum(r['parse_ok'] for r in rows)/len(rows):.1f}%")
    print(f"mean BLEU (seg) : {st.mean(r['bleu'] for r in rows):.2f}")
    for lang in sorted({r['lang'] for r in rows}):
        sel = [r for r in rows if r['lang'] == lang]
        print(f"  {lang}: n={len(sel)} mean={st.mean(r['bleu'] for r in sel):.2f}")
    print(f"median per pair : {st.median(r['secs'] for r in rows):.1f}s "
          f"(total {time.time()-t_all:.0f}s)")
    print(f"median length   : {st.median(r['chars'] for r in rows):.0f} chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
