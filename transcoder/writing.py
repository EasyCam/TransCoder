"""Essay grading and correction for teaching Chinese as a foreign language.

Two model calls:
- grade(): rubric scores (content / organization / grammar / vocabulary /
  coherence) + concrete issues + an overall comment + a rough HSK level hint.
- polish(): a corrected essay plus a structured edit list, preserving the
  student's intent (this is 批改, not rewriting from scratch).
"""

import time
from typing import Any, Dict, List, Optional

from transcoder.agents import extract_json_block
from transcoder.endpoints import redact
from transcoder.human_workbench import _call_provider

WRITING_SCORE_KEYS = ("content", "organization", "grammar", "vocabulary", "coherence")
WRITING_ISSUE_TYPES = (
    "grammar", "vocabulary", "characters", "punctuation", "organization", "content", "coherence", "other",
)
WRITING_EDIT_TYPES = (
    "grammar", "vocabulary", "characters", "punctuation", "word_order", "style", "coherence", "other",
)

GRADE_SYSTEM_EN = (
    "You are an experienced English writing examiner (CET-4/CET-6/ postgraduate entrance exam). "
    "Score each dimension 0-10 and reply ONLY with a JSON object, no other text:\n"
    '{"scores": {"content": 0-10, "organization": 0-10, "grammar": 0-10, "vocabulary": 0-10, '
    '"coherence": 0-10}, "issues": [{"type": "grammar|vocabulary|punctuation|organization|content|coherence|other", '
    '"span": "exact text from the essay", "advice": "how to fix, in English"}], '
    '"comment": "2-3 sentences of overall feedback in English", "level": "estimated level, e.g. CET-4"}\n'
    "Quote the student's exact text in span. Do not rewrite the essay."
)

GRADE_SYSTEM_JA = (
    "あなたは日本語能力試験(JLPT)の作文を採点する経験豊富な教師です。"
    "各観点を0-10で採点し、JSONオブジェクトだけを返してください:\n"
    '{"scores": {"content": 0-10, "organization": 0-10, "grammar": 0-10, "vocabulary": 0-10, '
    '"coherence": 0-10}, "issues": [{"type": "grammar|vocabulary|characters|punctuation|organization|content|coherence|other", '
    '"span": "作文からの正確な引用", "advice": "日本語で修正方法"}], '
    '"comment": "日本語で2〜3文の総評", "level": "推定レベル（例：JLPT N3）"}\n'
    "作文を書き直さず、引用は原文どおりにしてください。"
)

GRADE_SYSTEM = (
    "You are an experienced teacher of Chinese as a foreign language (对外汉语) grading a student essay. "
    "Score each dimension 0-10 and reply ONLY with a JSON object, no other text:\n"
    '{"scores": {"content": 0-10, "organization": 0-10, "grammar": 0-10, "vocabulary": 0-10, '
    '"coherence": 0-10}, "issues": [{"type": "grammar|vocabulary|characters|punctuation|organization|content|coherence|other", '
    '"span": "exact text from the essay", "advice": "how to fix, in Chinese"}], '
    '"comment": "2-3 sentences of overall feedback in Chinese", "level": "estimated HSK level, e.g. HSK 4"}\n'
    "Be specific and encouraging; quote the student's exact text in span. Do not rewrite the essay."
)

POLISH_SYSTEM_EN = (
    "You are an English writing tutor correcting a student essay. Preserve the student's ideas and voice. "
    "Reply ONLY with a JSON object, no other text:\n"
    '{"polished": "the corrected essay", '
    '"edits": [{"type": "grammar|vocabulary|punctuation|word_order|style|coherence|other", '
    '"original": "exact span", "revised": "replacement", "reason": "short explanation in English"}], '
    '"summary": "1-2 sentences in English"}'
)

POLISH_SYSTEM_JA = (
    "あなたは日本語作文の添削者です。学生の考えと文体を保ちながら修正してください。"
    "JSONオブジェクトだけを返してください:\n"
    '{"polished": "添削後の作文", '
    '"edits": [{"type": "grammar|vocabulary|characters|punctuation|word_order|style|coherence|other", '
    '"original": "原文の正確な引用", "revised": "修正案", "reason": "日本語で短い説明"}], '
    '"summary": "日本語で1〜2文の総評"}'
)

POLISH_SYSTEM = (
    "You are an experienced teacher of Chinese as a foreign language correcting a student essay. "
    "Preserve the student's ideas, structure and voice; fix errors and improve expression. "
    "Reply ONLY with a JSON object, no other text:\n"
    '{"polished": "the corrected essay", '
    '"edits": [{"type": "grammar|vocabulary|characters|punctuation|word_order|style|coherence|other", '
    '"original": "exact span from the student essay", "revised": "replacement", "reason": "short explanation in Chinese"}], '
    '"summary": "1-2 sentences in Chinese"}'
)


def grade_writing(provider, model: str, prompt: str, essay: str, temperature: float = 0.3,
                  length_hint: Optional[str] = None, language: str = "zh") -> Dict[str, Any]:
    system = {"en": GRADE_SYSTEM_EN, "ja": GRADE_SYSTEM_JA}.get(language, GRADE_SYSTEM)
    user = f"作文题目：\n{prompt}\n\n学生作文：\n{essay}"
    if length_hint:
        user += f"\n\n（参考要求：{length_hint}）"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    start = time.time()
    try:
        raw, tokens_in, tokens_out = _call_provider(provider, messages, model, temperature)
    except Exception as e:
        return {
            "scores": {}, "overall": None, "dimensions": list(WRITING_SCORE_KEYS),
            "issues": [], "comment": "", "level": "", "parse_ok": False,
            "model": model, "tokens_in": 0, "tokens_out": 0,
            "latency_s": round(time.time() - start, 3),
            "error": str(redact(f"{type(e).__name__}: {e}")),
        }

    obj = extract_json_block(raw) or {}
    scores: Dict[str, float] = {}
    for k in WRITING_SCORE_KEYS:
        v = (obj.get("scores") or {}).get(k)
        try:
            v = float(v)
            if 0 <= v <= 10:
                scores[k] = v
        except (TypeError, ValueError):
            pass

    issues: List[Dict[str, str]] = []
    for it in (obj.get("issues") or [])[:15]:
        if not isinstance(it, dict):
            continue
        t = str(it.get("type", "other")).lower()
        if t not in WRITING_ISSUE_TYPES:
            t = "other"
        issues.append({
            "type": t,
            "span": str(it.get("span", ""))[:200],
            "advice": str(it.get("advice", ""))[:400],
        })

    overall = round(sum(scores.values()) / len(scores), 2) if scores else None
    return {
        "scores": scores,
        "overall": overall,
        "dimensions": list(WRITING_SCORE_KEYS),
        "issues": issues,
        "comment": str(obj.get("comment", "") or "")[:1000],
        "level": str(obj.get("level", "") or "")[:40],
        "parse_ok": bool(obj),
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_s": round(time.time() - start, 3),
        "error": None if obj else "could not parse model reply as JSON",
    }


def polish_writing(provider, model: str, prompt: str, essay: str, temperature: float = 0.3,
                   language: str = "zh") -> Dict[str, Any]:
    system = {"en": POLISH_SYSTEM_EN, "ja": POLISH_SYSTEM_JA}.get(language, POLISH_SYSTEM)
    user = f"作文题目：\n{prompt}\n\n学生作文：\n{essay}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    start = time.time()
    try:
        raw, tokens_in, tokens_out = _call_provider(provider, messages, model, temperature)
    except Exception as e:
        return {
            "polished": "", "edits": [], "summary": "", "parse_ok": False,
            "model": model, "tokens_in": 0, "tokens_out": 0,
            "latency_s": round(time.time() - start, 3),
            "error": str(redact(f"{type(e).__name__}: {e}")),
        }

    obj = extract_json_block(raw) or {}
    edits = []
    for it in (obj.get("edits") or [])[:25]:
        if not isinstance(it, dict):
            continue
        t = str(it.get("type", "other")).lower()
        if t not in WRITING_EDIT_TYPES:
            t = "other"
        edits.append({
            "type": t,
            "original": str(it.get("original", ""))[:300],
            "revised": str(it.get("revised", ""))[:300],
            "reason": str(it.get("reason", ""))[:400],
        })

    return {
        "polished": str(obj.get("polished", "") or "")[:12000],
        "edits": edits,
        "summary": str(obj.get("summary", "") or "")[:800],
        "parse_ok": bool(obj),
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_s": round(time.time() - start, 3),
        "error": None if obj else "could not parse model reply as JSON",
    }
