# -*- coding: utf-8 -*-
"""P4: old vs new token accounting on REAL samples; writes RESULTS/tokcount_report.json."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from services.translation_service import TranslationService  # noqa: E402 (real engine)
from transcoder.tokcount import count_tokens, estimate_tokens_legacy  # noqa: E402

SAMPLES = [
    ("hello-en", "Hello, how is your day going today?"),
    ("zh-short", "未庄的人都说阿Q阔了。"),
    ("zh-para", "阿Q在形式上打败了，被人揪住黄辫子，在壁上碰了四五个响头，闲人这才心满意足的得胜的走了。"),
    ("ja-short", "文節パターンに基づいた文章の書き手の識別"),
    ("mixed-tech", "TransCoder 使用 VectorDBService 和 TerminologyService 提供翻译记忆与术语约束，tokenizer 计数采用 tiktoken o200k_base。"),
]


def main():
    rows = []
    for name, text in SAMPLES:
        legacy = estimate_tokens_legacy(text)
        o200k = count_tokens(text)
        rows.append({
            "sample": name,
            "chars": len(text),
            "legacy_estimate": legacy,
            "o200k": o200k,
            "diff": legacy - o200k,
            "rel_diff_pct": round(100 * (legacy - o200k) / max(o200k, 1), 1),
        })
    doc = {
        "schema": "transcoder-next/tokcount/v1",
        "date": "2026-10-19",
        "standard": "tiktoken o200k_base (uniform cross-model accounting)",
        "legacy": "word_count + char_count // 4 (PERFORMANCE_METRICS_SUMMARY.md)",
        "samples": rows,
        "note": "o200k is the accounting layer for cross-group comparison; vendor invoices "
                "may differ (DeepSeek/ollama tokenize differently). Engine metrics now use "
                "count_tokens(); legacy estimator retained only for this report.",
    }
    out = REPO / "RESULTS" / "tokcount_report.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in rows:
        print(f"{r['sample']:12s} chars={r['chars']:6d} legacy={r['legacy_estimate']:5d} "
              f"o200k={r['o200k']:5d} diff={r['diff']:+4d} ({r['rel_diff_pct']:+.1f}%)")
    print("->", out)


if __name__ == "__main__":
    main()