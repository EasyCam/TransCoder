#!/usr/bin/env python3
"""Aggregate repeated runs of a group and paired deltas against a reference group.

The online reviewer (G5) is served by a remote chat model that does not honour
the sampling seed, so a single run is one draw.  This tool averages the group
over seeds and reports a bootstrap CI for the paired delta against a
deterministic local group (G1), so the paper can quote a distribution rather
than a single sample.

Usage:
    python RESULTS/tools/aggregate_seeds.py --group G5 --seeds 42 43 44 --ref G1 --ref-seed 42
"""
from __future__ import annotations

import argparse
import json
import random
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "RESULTS"


def load(group: str, seed: int) -> dict[str, dict]:
    p = RESULTS / group / f"results_s{seed}_refs.json"
    if not p.exists():
        raise SystemExit(f"missing {p}")
    return {r["pair_id"]: r for r in json.loads(p.read_text())["rows"] if not r.get("error")}


def bleu(r: dict) -> float | None:
    return (r.get("metrics") or {}).get("bleu")


def tokens(r: dict) -> int:
    t = r.get("online_tokens")
    if isinstance(t, dict):
        return int(t.get("in", 0) + t.get("out", 0))
    return int(t or 0)


def boot_ci(vals: list[float], n: int = 5000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    m = [st.mean(rng.choices(vals, k=len(vals))) for _ in range(n)]
    m.sort()
    return m[int(0.025 * n)], m[int(0.975 * n)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="G5")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--ref", default="G1")
    ap.add_argument("--ref-seed", type=int, default=42)
    a = ap.parse_args()

    runs = [load(a.group, s) for s in a.seeds]
    ref = load(a.ref, a.ref_seed)
    pairs = sorted(set.intersection(*(set(r) for r in runs)) & set(ref))

    per_pair_mean, deltas, toks, walls = [], [], [], []
    for pid in pairs:
        b = [bleu(r[pid]) for r in runs if bleu(r[pid]) is not None]
        if not b or bleu(ref[pid]) is None:
            continue
        per_pair_mean.append(st.mean(b))
        deltas.append(st.mean(b) - bleu(ref[pid]))
        toks.append(st.mean(tokens(r[pid]) for r in runs))
        walls.append(st.mean(r[pid].get("wall_s") or 0 for r in runs))

    lo, hi = boot_ci(deltas)
    print(f"{a.group} over seeds {a.seeds} vs {a.ref} seed {a.ref_seed}: {len(deltas)} pairs")
    print(f"  BLEU {st.mean(per_pair_mean):.2f} (per-pair sd {st.stdev(per_pair_mean):.2f})")
    print(f"  delta vs {a.ref}: {st.mean(deltas):+.2f}  95% CI [{lo:+.2f}, {hi:+.2f}]")
    print(f"  tokens/pair {st.mean(toks):,.0f}   wall/pair {st.mean(walls):.1f} s")

    # run-to-run spread of the group mean
    means = []
    for r in runs:
        v = [bleu(r[p]) for p in pairs if bleu(r[p]) is not None]
        means.append(st.mean(v))
    if len(means) > 1:
        print(f"  run means: {', '.join(f'{m:.2f}' for m in means)}  "
              f"(mean {st.mean(means):.2f}, sd {st.stdev(means):.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
