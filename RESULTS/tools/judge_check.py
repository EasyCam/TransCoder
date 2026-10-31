# -*- coding: utf-8 -*-
"""JUDGE.md 三条预注册判据核对 + stability_G5.csv 生成。

用法:
    python3 RESULTS/tools/judge_check.py            # 主矩阵核对
判据来源: RESULTS/JUDGE.md (落盘 2026-10-19, 实验前锁定, 本脚本只核对不修改判据)。
"""
from __future__ import annotations

import csv
import json
import random
import statistics
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[1]


def load_group(g: str) -> dict:
    p = RESULTS / g / "results.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def metric_by_pair(doc: dict, key: str) -> dict:
    out = {}
    for r in doc.get("rows", []):
        m = r.get("metrics") or {}
        if m.get(key) is not None and not r.get("error"):
            out[r["pair_id"]] = float(m[key])
    return out


def paired(groups: tuple, key: str) -> tuple:
    """(pair_id, g_a, g_b) triples on shared pairs with metric."""
    doc_a, doc_b = load_group(groups[0]), load_group(groups[1])
    if not doc_a or not doc_b:
        return []
    ma, mb = metric_by_pair(doc_a, key), metric_by_pair(doc_b, key)
    shared = sorted(set(ma) & set(mb))
    return [(p, ma[p], mb[p]) for p in shared]


def bootstrap_ci(diffs, n=1000, seed=42):
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        s = [rng.choice(diffs) for _ in diffs]
        means.append(statistics.mean(s))
    means.sort()
    lo, hi = means[int(n * 0.025)], means[int(n * 0.975) - 1]
    return round(statistics.mean(diffs), 3), round(lo, 3), round(hi, 3)


def main():
    print("=" * 62)
    print("JUDGE.md 三条判据核对（bootstrap 1000 次, 配对差, seed=42）")
    print("=" * 62)

    rows_a = []
    # 判据①: G5 vs G1, BLEU 与 BERTScore 配对差 95% CI 不跨 0（提升方向 G5 更高）
    for key in ("bleu", "bert_f1"):
        triples = paired(("G5", "G1"), key)
        if not triples:
            print(f"判据①[{key}]: 无共享配对（缺 G5/G1 实测指标）")
            continue
        diffs = [a - b for _, a, b in [(t[0], t[1], t[2]) for t in triples]]
        # G5 在前：diff = G5 - G1
        vals = [t[1] - t[2] for t in triples]
        mean, lo, hi = bootstrap_ci(vals)
        sig = (lo > 0) or (hi < 0)
        pos = mean > 0
        print(f"判据①[{key}] n={len(vals)} meanΔ={mean} 95%CI=[{lo},{hi}] "
              f"{'✓ 显著且方向正确' if sig and pos else '✗ 未达显著提升'}")
        rows_a.append((key, len(vals), mean, lo, hi, sig and pos))

    # 判据②: G5 与 G0 均值差：BLEU 差 ≤5 或 BERTScore F1 差 ≤0.05（组级均值差）
    ok2 = False
    for key, thr in (("bleu", 5.0), ("bert_f1", 0.05)):
        t5 = paired(("G0", "G5"), key)  # diff = G0 - G5
        if not t5:
            print(f"判据②[{key}]: 无共享配对")
            continue
        d0 = [b for _, a, b in t5]  # G5 值
        d0m = statistics.mean([t[2] for t in t5])
        g0m = statistics.mean([t[1] for t in t5])
        gap = g0m - d0m
        hit = abs(gap) <= thr
        ok2 = ok2 or hit
        print(f"判据②[{key}] G0均值={round(g0m,3)} G5均值={round(d0m,3)} 差距={round(gap,3)} "
              f"阈值≤{thr} {'✓ 达标' if hit else '✗ 未达'}")
    if not ok2:
        print("判据②: 两组指标均未达阈值（如实记录，不圆场）")

    # 判据③: sum(G5 online tokens) / sum(G0 online tokens) ≤ 0.25
    g0, g5 = load_group("G0"), load_group("G5")
    if g0 and g5:
        t0 = sum((r.get("online_tokens") or {}).get("in", 0) + (r.get("online_tokens") or {}).get("out", 0)
                 for r in g0["rows"] if not r.get("error"))
        t5 = sum((r.get("online_tokens") or {}).get("in", 0) + (r.get("online_tokens") or {}).get("out", 0)
                 for r in g5["rows"] if not r.get("error"))
        ratio = (t5 / t0) if t0 else None
        verdict = ("✓ 达标" if ratio is not None and ratio <= 0.25 else "✗ 未达") if ratio is not None else "无数据"
        print(f"判据③ 在线token: G0={t0} G5={t5} 比值={round(ratio, 3) if ratio is not None else '—'} 阈值≤0.25 {verdict}")

    # stability_G5.csv（seed 42/7/3407 的判据①子集, 若存在）
    seeds = {"42": "results.json", "7": "results_s7_refs.json", "3407": "results_s3407_refs.json"}
    lines = []
    for s, fn in seeds.items():
        p = RESULTS / "G5" / fn
        if not p.exists():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        for r in doc["rows"]:
            m = r.get("metrics") or {}
            if m.get("bleu") is not None:
                lines.append({"seed": s, "pair_id": r["pair_id"],
                              "bleu": m.get("bleu", ""), "chrf": m.get("chrf", ""),
                              "bert_f1": m.get("bert_f1", "")})
    if lines:
        out = RESULTS / "stability_G5.csv"
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["seed", "pair_id", "bleu", "chrf", "bert_f1"])
            w.writeheader()
            w.writerows(lines)
        # 组级均值稳定性
        by_seed = {}
        for L in lines:
            by_seed.setdefault(L["seed"], []).append(float(L["bleu"]))
        msg = {s: round(statistics.mean(v), 2) for s, v in sorted(by_seed.items())}
        print(f"stability_G5.csv -> {out} ({len(lines)} 行) BLEU均值: {msg}")


if __name__ == "__main__":
    main()