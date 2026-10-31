#!/usr/bin/env python3
"""Pool the repeated G5 runs and compare them with the deterministic G1 baseline.

The online reviewer is a remote chat model that ignores the sampling seed, so every
G5 run is a draw.  This script:

* loads every G5 results file listed on the command line,
* averages each pair over the runs,
* computes the paired delta against G1 with a bootstrap CI,
* reports the run-to-run spread of the aggregate and the mean cost.

Usage:
    python RESULTS/tools/pool_g5.py \
        RESULTS/archive/20261020_160708/G5/results_s42_refs.json \
        RESULTS/G5/results_s42_refs.json \
        RESULTS/G5/results_s43_refs.json \
        RESULTS/G5/results_s44_refs.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(p: str | Path) -> dict[str, dict]:
    rows = json.loads(Path(p).read_text())["rows"]
    return {r["pair_id"]: r for r in rows if not r.get("error")}


def bleu(r: dict) -> float | None:
    return (r.get("metrics") or {}).get("bleu")


def tokens(r: dict) -> int:
    t = r.get("online_tokens")
    return int(t.get("in", 0) + t.get("out", 0)) if isinstance(t, dict) else int(t or 0)


def boot(vals: list[float], n: int = 10000) -> tuple[float, float]:
    rng = random.Random(0)
    m = sorted(st.mean(rng.choices(vals, k=len(vals))) for _ in range(n))
    return m[int(0.025 * n)], m[int(0.975 * n)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--ref", default=str(ROOT / "RESULTS/G1/results_s42_refs.json"))
    a = ap.parse_args()

    runs = [load(p) for p in a.runs]
    ref = load(a.ref)
    pairs = sorted(set.intersection(*(set(r) for r in runs)) & set(ref))

    per_pair, deltas, toks, walls = {}, [], [], []
    for pid in pairs:
        b = [bleu(r[pid]) for r in runs if bleu(r[pid]) is not None]
        if not b or bleu(ref[pid]) is None:
            continue
        per_pair[pid] = st.mean(b)
        deltas.append(per_pair[pid] - bleu(ref[pid]))
        toks.append(st.mean(tokens(r[pid]) for r in runs))
        walls.append(st.mean(r[pid].get("wall_s") or 0 for r in runs))

    lo, hi = boot(deltas)
    run_means = [st.mean([bleu(r[p]) for p in pairs if bleu(r[p]) is not None]) for r in runs]

    out = {
        "runs": len(runs),
        "pairs": len(deltas),
        "bleu_per_pair_mean": round(st.mean(per_pair.values()), 2),
        "bleu_run_means": [round(x, 2) for x in run_means],
        "bleu_run_sd": round(st.stdev(run_means), 2) if len(run_means) > 1 else None,
        "delta_vs_ref": round(st.mean(deltas), 2),
        "delta_ci95": [round(lo, 2), round(hi, 2)],
        "pairs_improved": sum(1 for d in deltas if d > 0),
        "tokens_total_mean": round(st.mean(toks) * 14),
        "wall_median_mean": round(st.mean(walls), 1),
    }
    # sensitivity: drop the single largest delta
    worst = max(deltas)
    rest = [d for d in deltas if d != worst]
    lo2, hi2 = boot(rest)
    out["without_largest_pair"] = {"delta": round(st.mean(rest), 2), "ci95": [round(lo2, 2), round(hi2, 2)]}

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
