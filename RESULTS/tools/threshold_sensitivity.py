#!/usr/bin/env python3
"""Threshold sensitivity for the reviewer pass rule.

The threshold is a decision rule on top of the reviewer, so it can be varied on the
recorded rubrics without re-running the models.  This tool prints the table used in
Section 7.5 of the manuscript:

    group, threshold -> reviews whose lowest rubric dimension is >= threshold

and the operational pass counts (score criterion AND no blocking issue quoting a span).

Usage:  python RESULTS/tools/threshold_sensitivity.py [--group G4 G5]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "RESULTS"
THRESHOLDS = (6.0, 6.5, 7.0, 7.5)


def load(group: str) -> list[dict]:
    p = RESULTS / group / "results_s42_refs.json"
    if not p.exists():
        return []
    return [r for r in json.loads(p.read_text())["rows"] if not r.get("error")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", nargs="+", default=["G4", "G5"])
    a = ap.parse_args()

    print("| group | threshold | score pass | operational pass |")
    print("|---|---|---|---|")
    for g in a.group:
        rows = load(g)
        scored = [r for r in rows if r.get("review_scores")]
        for T in THRESHOLDS:
            ok = sum(1 for r in scored if min(r["review_scores"].values()) >= T)
            # operational: what the run actually recorded at its own threshold (7.0)
            op = sum(1 for r in rows if r.get("review_pass")) if T == 7.0 else "--"
            print(f"| {g} | {T} | {ok}/{len(scored)} of parsed ({ok}/{len(rows)} of all) | {op} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
