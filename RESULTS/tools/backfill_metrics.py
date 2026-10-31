# -*- coding: utf-8 -*-
"""指标统一重算：对已产出的 results.json 逐行重算 evaluate_pair（含 chrF 嵌套修复、
BERTScorer 缓存），译文/评审产出不重跑（模型调用与 latency 记录保持原样）。
真实矩阵跑完后执行一次：python3 RESULTS/tools/backfill_metrics.py
幂等：重复执行得到同一结果。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from run_experiment import evaluate_pair  # noqa: E402  (导入即注入 OMP=1/TOKENIZERS env)

RESULTS = REPO / "RESULTS"


def backfill(group: str) -> int:
    p = RESULTS / group / "results.json"
    if not p.exists():
        return 0
    doc = json.loads(p.read_text(encoding="utf-8"))
    ds = json.loads((RESULTS / "corpus" / "dataset.json").read_text(encoding="utf-8"))
    ref_by_pair = {r["pair_id"]: r.get("reference") for r in ds["pairs"]}
    fixed = 0
    for r in doc.get("rows", []):
        if r.get("error") or not r.get("output"):
            continue
        before = json.dumps(r.get("metrics") or {}, sort_keys=True)
        m2 = evaluate_pair("", r["output"], ref_by_pair.get(r.get("pair_id")),
                           r.get("target_lang", "en"))
        # 保留生成层遥测字段（不属于指标）
        for k in ("edge_tok_s",):
            if (r.get("metrics") or {}).get(k) is not None:
                m2[k] = r["metrics"][k]
        r["metrics"] = m2
        if json.dumps(m2, sort_keys=True) != before:
            fixed += 1
    if fixed:
        ar = RESULTS / "archive" / time.strftime("%Y%m%d_%H%M%S") / group
        ar.mkdir(parents=True, exist_ok=True)
        (ar / "results.json").write_bytes(p.read_bytes())
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{group}] 重算 {fixed} 行有变化")
    return fixed


if __name__ == "__main__":
    total = sum(backfill(g) for g in ("G0", "G1", "G2", "G3", "G4", "G5"))
    print(f"合计重算 {total} 行有变化")