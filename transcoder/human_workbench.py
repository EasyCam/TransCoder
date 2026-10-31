"""AI-assisted human translation workflow: grading, polishing, and edit extraction.

- grade(): reuse ReviewerAgent (same rubric as the experiment reviewer) so the
  teaching score and the research evaluation stay on one scale.
- polish(): ask the model for a corrected translation plus a structured list of
  edits (grammar / word choice / fluency / terminology / accuracy / style).
"""

import time
from typing import Any, Dict, List, Optional

from transcoder.agents import REVIEW_SCORE_KEYS, ReviewerAgent, extract_json_block
from transcoder.endpoints import redact
from transcoder.tokcount import count_chat, count_tokens

EDIT_TYPES = ("grammar", "word_choice", "fluency", "terminology", "accuracy", "style", "other")

POLISH_SYSTEM = (
    "You are a translation teacher polishing a student's translation. "
    "Given the source text and the student's translation, reply ONLY with a JSON object, no other text:\n"
    '{"polished": "corrected and polished translation", '
    '"edits": [{"type": "grammar|word_choice|fluency|terminology|accuracy|style|other", '
    '"original": "exact span from the student translation", "revised": "replacement", '
    '"reason": "short explanation"}], '
    '"summary": "1-2 sentence overall comment"}\n'
    "Never invent meaning that is not in the source; preserve the student's intent and register."
)


def grade(
    provider,
    model: str,
    source_text: str,
    translation: str,
    source_lang: str = "auto",
    target_lang: str = "",
    glossary: Optional[Dict[str, str]] = None,
    temperature: float = 0.3,
) -> Dict[str, Any]:
    """Score a human translation on the standard 4-dimension rubric (0-10)."""
    reviewer = ReviewerAgent(provider, model, temperature=temperature)
    out = reviewer.review(source_text, translation, source_lang, target_lang, glossary=glossary)
    overall = None
    if out.scores:
        overall = round(sum(out.scores.values()) / len(out.scores), 2)
    return {
        "scores": out.scores,
        "dimensions": list(REVIEW_SCORE_KEYS),
        "overall": overall,
        "issues": [
            {"type": i.type, "span": i.span, "advice": i.advice} for i in out.issues
        ],
        "passed": out.passed,
        "parse_ok": out.parse_ok,
        "model": out.model,
        "tokens_in": out.tokens_in,
        "tokens_out": out.tokens_out,
        "latency_s": out.latency_s,
        "error": out.error,
    }


def _call_provider(provider, messages: List[Dict[str, str]], model: str, temperature: float):
    """One completion, mirroring ReviewerAgent (chat if available, else generate)."""
    if hasattr(provider, "chat"):
        raw, usage = provider.chat(messages, model=model, temperature=temperature)
        tokens_in = (usage or {}).get("prompt_tokens") or count_chat(messages)
    else:
        raw = provider.generate(
            f"{messages[0]['content']}\n\n{messages[1]['content']}", model=model, temperature=temperature
        )
        tokens_in = count_chat(messages)
    return raw or "", int(tokens_in or 0), count_tokens(raw or "")


def polish(
    provider,
    model: str,
    source_text: str,
    translation: str,
    source_lang: str = "auto",
    target_lang: str = "",
    issues: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.3,
) -> Dict[str, Any]:
    """Correct + polish a human translation; returns polished text and edit list."""
    user = f"Source ({source_lang}):\n{source_text}\n\nStudent translation ({target_lang}):\n{translation}"
    if issues:
        lines = "\n".join(
            f"- [{i.get('type', 'other')}] {i.get('span', '')}: {i.get('advice', '')}" for i in issues[:10]
        )
        user += f"\n\nKnown reviewer issues to address:\n{lines}"

    messages = [{"role": "system", "content": POLISH_SYSTEM}, {"role": "user", "content": user}]
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

    latency = round(time.time() - start, 3)
    obj = extract_json_block(raw) or {}
    edits = []
    for it in (obj.get("edits") or [])[:20]:
        if not isinstance(it, dict):
            continue
        etype = str(it.get("type", "other")).lower()
        if etype not in EDIT_TYPES:
            etype = "other"
        edits.append({
            "type": etype,
            "original": str(it.get("original", ""))[:300],
            "revised": str(it.get("revised", ""))[:300],
            "reason": str(it.get("reason", ""))[:400],
        })

    return {
        "polished": str(obj.get("polished", "") or "")[:8000],
        "edits": edits,
        "summary": str(obj.get("summary", "") or "")[:600],
        "parse_ok": bool(obj),
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_s": latency,
        "error": None if obj else "could not parse model reply as JSON",
    }
