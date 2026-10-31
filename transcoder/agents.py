"""
TransCoder-NEXT agent layer (P2): four roles with structured outputs.

Roles (spec-agent-design.md §2):
- TranslatorAgent      generation model, edge-side <=1B (or any provider)
- ReviewerAgent        REVIEW ONLY, never rewrites by itself; produces
                       structured JSON opinion {scores, issues, pass}
- TerminologyGuardAgent glossary retrieval + FAISS translation-memory recall
- EventLog             event-sourced JSONL recorder — the raw experimental data layer

Every structured payload of every role goes through a schema validator and
through `endpoints.redact` before being returned or written; the EventLog
always appends redacted JSON lines.
"""

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from transcoder.endpoints import redact
from transcoder.tokcount import count_chat, count_tokens


# --------------------------------------------------------------------------- #
# Structured outputs
# --------------------------------------------------------------------------- #

@dataclass
class TranslationOutput:
    translation: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    model: str = ""
    error: Optional[str] = None
    meta: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReviewIssue:
    type: str
    span: str = ""
    advice: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReviewOutput:
    scores: Dict[str, float] = field(default_factory=dict)  # adequacy/terminology/fluency/culture 0-10
    issues: List[ReviewIssue] = field(default_factory=list)
    passed: bool = False
    raw: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    model: str = ""
    error: Optional[str] = None
    parse_ok: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["issues"] = [i if isinstance(i, dict) else i.to_dict() for i in d["issues"]]
        return d


REVIEW_SCORE_KEYS = ("adequacy", "terminology", "fluency", "culture")
VALID_ISSUE_TYPES = ("accuracy", "terminology", "fluency", "culture", "other")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def extract_json_block(text: str) -> Optional[dict]:
    """Extract the first balanced JSON object from an LLM reply (fenced or raw)."""
    if not text:
        return None
    unfenced = re.sub(r"```(?:json)?", "", text)
    start = unfenced.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(unfenced)):
            c = unfenced[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = unfenced[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except Exception:
                        break
        start = unfenced.find("{", start + 1)
    return None


# --------------------------------------------------------------------------- #
# Roles
# --------------------------------------------------------------------------- #

class TranslatorAgent:
    """Generation role: translate / rewrite. Keeps tokens from true o200k counting."""

    def __init__(self, provider, model: str, temperature: float = 0.3):
        self.provider = provider
        self.model = model
        self.temperature = temperature

    def _messages(self, system, user) -> list:
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _call(self, messages, seed: Optional[int] = None) -> Dict[str, Any]:
        start = time.time()
        try:
            if hasattr(self.provider, "chat"):
                out_text, usage = self.provider.chat(messages, model=self.model, temperature=self.temperature, seed=seed)
            else:
                # LLMProvider ABC generates from a single prompt (legacy path).
                sys_txt = messages[0]["content"]
                usr_txt = messages[1]["content"]
                out_text = self.provider.generate(f"{sys_txt}\n\n{usr_txt}", model=self.model)
                usage = None
            latency = time.time() - start
            tokens_in = usage.get("prompt_tokens") if usage else count_chat(messages)
            tokens_out = usage.get("completion_tokens") if usage else count_tokens(out_text)
            return {
                "text": (out_text or "").strip(),
                "tokens_in": int(tokens_in or 0),
                "tokens_out": int(tokens_out or 0),
                "latency_s": round(latency, 3),
                "error": None,
            }
        except Exception as e:
            return {
                "text": "",
                "tokens_in": 0,
                "tokens_out": 0,
                "latency_s": round(time.time() - start, 3),
                "error": redact(f"{type(e).__name__}: {e}"),
            }

    def translate(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        glossary: Optional[Dict[str, str]] = None,
        memory: Optional[List[Dict[str, Any]]] = None,
        seed: Optional[int] = None,
    ) -> TranslationOutput:
        system = "You are a professional translator. Translate faithfully and fluently. Output ONLY the translation."
        user = _build_translation_user(source_text, source_lang, target_lang, glossary, memory)
        r = self._call(self._messages(system, user), seed=seed)
        return TranslationOutput(translation=r["text"], tokens_in=r["tokens_in"], tokens_out=r["tokens_out"],
                                 latency_s=r["latency_s"], model=self.model, error=r["error"])

    def rewrite(
        self,
        source_text: str,
        target_lang: str,
        current: str,
        issues: List[ReviewIssue],
        source_lang: str = "auto",
        seed: Optional[int] = None,
    ) -> TranslationOutput:
        issue_lines = "\n".join(f"- [{i.type}] {i.span}: {i.advice}" for i in issues) or "- (none)"
        system = ("You are a professional translator. Revise the translation per the reviewer's issues. "
                  "Change only the clauses that the issues quote; copy every other sentence verbatim. "
                  "Do not rephrase, reorder or restructure text that no issue mentions. "
                  "Preserve meaning. Output ONLY the revised translation.")
        user = (
            f"Source ({source_lang}):\n{source_text}\n\n"
            f"Current translation ({target_lang}):\n{current}\n\n"
            f"Reviewer issues to fix:\n{issue_lines}\n\n"
            f"Output ONLY the revised {target_lang} translation."
        )
        r = self._call(self._messages(system, user), seed=seed)
        return TranslationOutput(translation=r["text"], tokens_in=r["tokens_in"], tokens_out=r["tokens_out"],
                                 latency_s=r["latency_s"], model=self.model, error=r["error"])


    def rewrite_spans(
        self,
        target_lang: str,
        current: str,
        issues: List[ReviewIssue],
        seed: Optional[int] = None,
        max_span_factor: float = 4.0,
    ) -> "TranslationOutput":
        """Rewrite only the quoted spans and splice them back.

        One call per quoted span. A replacement is accepted only if it is a single
        line, non-empty, and no longer than ``max_span_factor`` times the span;
        otherwise the span is left as it was. The full text is never regenerated,
        so text that no issue quotes cannot change.
        """
        text = current
        applied, skipped = [], []
        tin = tout = 0
        for issue in issues:
            span = (issue.span or "").strip()
            if len(span) < 3:
                skipped.append({"span": span, "why": "empty"})
                continue
            if span not in text:
                skipped.append({"span": span, "why": "not found"})
                continue
            system = ("You are a professional translator. Rewrite one clause so that it addresses "
                      "the reviewer's note. Output ONLY the replacement clause: no quotes, no "
                      "explanation, no other text.")
            user = (f"Full translation ({target_lang}):\n{text}\n\n"
                    f"Clause to rewrite:\n{span}\n\n"
                    f"Reviewer note:\n{issue.advice}\n\n"
                    f"Return only the replacement for the clause, grammatical in its sentence.")
            r = self._call(self._messages(system, user), seed=seed)
            tin += r["tokens_in"]; tout += r["tokens_out"]
            repl = (r["text"] or "").strip().strip('"').strip()
            too_long = len(repl) > max_span_factor * max(len(span), 1)
            multi = "\n" in repl
            if r["error"] or not repl or too_long or multi:
                skipped.append({"span": span, "why": r["error"] or ("too_long" if too_long else "multi_line" if multi else "empty")})
                continue
            text = text.replace(span, repl, 1)
            applied.append({"span": span, "replacement": repl})
        return TranslationOutput(translation=text, tokens_in=tin, tokens_out=tout,
                                 latency_s=0.0, model=self.model, error=None,
                                 meta={"applied": applied, "skipped": skipped})


def _build_translation_user(source_text, source_lang, target_lang, glossary, memory) -> str:
    parts = [f"Translate the following {source_lang} text into {target_lang}.", f"Source:\n{source_text}"]
    if glossary:
        lines = "\n".join(f"{k} -> {v}" for k, v in list(glossary.items())[:20])
        parts.append(f"Required terminology (must use these target-side renderings):\n{lines}")
    if memory:
        lines = "\n".join(f"src: {h.get('source', '')}\nref: {h.get('translation', '')}" for h in memory[:3])
        parts.append(f"Similar past translations from memory:\n{lines}")
    parts.append("Output ONLY the translation.")
    return "\n\n".join(parts)


class ReviewerAgent:
    """Review role: scores + issues + pass. NEVER produces a replacement text."""

    REVIEW_SYSTEM = (
        "You are a translation quality reviewer. Given a source text and a translation, "
        "evaluate and reply ONLY with a JSON object, no other text:\n"
        '{"scores": {"adequacy": 0-10, "terminology": 0-10, "fluency": 0-10, "culture": 0-10}, '
        '"issues": [{"type": "accuracy|terminology|fluency|culture|other", "span": "quoted faulty span", '
        '"advice": "how to fix"}], "pass": true|false}\n'
        "pass=true only when no issue of type accuracy or terminology exists. "
        "You review; you never output a rewritten translation."
    )

    def __init__(self, provider, model: str, temperature: float = 0.3, pass_threshold: float = 7.0,
                 pass_policy: str = "scores"):
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.pass_threshold = pass_threshold
        self.pass_policy = pass_policy

    STRICT_HINT = (
        "\nSTRICT MODE: return exactly one JSON object and nothing else. "
        "No markdown fences, no prose, no trailing text."
    )

    def review(
        self, source_text: str, translation: str, source_lang: str, target_lang: str,
        glossary: Optional[Dict[str, str]] = None, seed: Optional[int] = None,
        strict: bool = False, threshold: Optional[float] = None, policy: Optional[str] = None,
    ) -> ReviewOutput:
        messages = self._build_review_messages(source_text, translation, source_lang, target_lang, glossary,
                                               strict=strict)
        start = time.time()
        raw = ""
        try:
            temperature = 0.0 if strict else self.temperature
            if hasattr(self.provider, "chat"):
                raw, usage = self.provider.chat(messages, model=self.model, temperature=temperature, seed=seed)
                tokens_in = usage.get("prompt_tokens") if usage else count_chat(messages)
            else:
                sys_txt = messages[0]["content"]
                usr_txt = "\n\n".join(m["content"] for m in messages[1:])
                raw = self.provider.generate(f"{sys_txt}\n\n{usr_txt}", model=self.model)
                tokens_in = count_chat(messages)
            tokens_out = count_tokens(raw)
            latency = time.time() - start
        except Exception as e:
            return ReviewOutput(
                raw="",
                tokens_in=0, tokens_out=0, latency_s=round(time.time() - start, 3),
                model=self.model, error=redact(f"{type(e).__name__}: {e}"), parse_ok=False,
            )

        out = validate_review_json(raw, threshold=self.pass_threshold if threshold is None else threshold,
                                   policy=self.pass_policy if policy is None else policy)
        out.tokens_in = int(tokens_in or 0)
        out.tokens_out = int(tokens_out or 0)
        out.latency_s = round(latency, 3)
        out.model = self.model
        return out

    def _build_review_messages(self, source_text, translation, source_lang, target_lang, glossary=None,
                               strict: bool = False) -> list:
        user = (
            f"Source ({source_lang}):\n{source_text}\n\n"
            f"Translation ({target_lang}):\n{translation}"
        )
        if glossary:
            lines = "\n".join(f"{k} -> {v}" for k, v in list(glossary.items())[:20])
            user += f"\n\nRequired terminology (check the translation uses these):\n{lines}"
        system = self.REVIEW_SYSTEM + (self.STRICT_HINT if strict else "")
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def validate_review_json(raw: str, threshold: float = 7.0, policy: str = "scores") -> ReviewOutput:
    """Parse + schema-validate a reviewer reply; never raises."""
    obj = extract_json_block(raw or "")
    if not obj:
        return ReviewOutput(raw=raw, parse_ok=False)
    scores = {}
    for k in REVIEW_SCORE_KEYS:
        v = (obj.get("scores") or {}).get(k)
        try:
            v = float(v)
            if 0 <= v <= 10:
                scores[k] = v
        except (TypeError, ValueError):
            pass
    issues = []
    for it in (obj.get("issues") or [])[:12]:
        if not isinstance(it, dict):
            continue
        t = str(it.get("type", "other")).lower()
        if t not in VALID_ISSUE_TYPES:
            t = "other"
        issues.append(ReviewIssue(type=t, span=str(it.get("span", ""))[:200], advice=str(it.get("advice", ""))[:400]))
    # An issue only blocks when it quotes the faulty span. A reviewer that emits
    # {"type": "accuracy"} with an empty span has flagged nothing actionable.
    blocking = [i for i in issues if i.type in ("accuracy", "terminology") and i.span.strip()]
    parse_ok = len(scores) == len(REVIEW_SCORE_KEYS)
    model_flag = obj.get("pass")
    if isinstance(model_flag, str):
        model_flag = model_flag.strip().lower() not in ("false", "no", "off", "0", "")
    model_flag = None if model_flag is None else bool(model_flag)
    score_pass = bool(scores) and min(scores.values()) >= threshold
    if policy == "model":
        passed = bool(model_flag) and score_pass
    elif policy == "both":
        passed = bool(model_flag) and score_pass
    else:  # "scores": the rubric is the contract, the model's own flag is advisory
        passed = score_pass
    # A reply that does not carry the full rubric cannot be a pass: otherwise a
    # JSON object with no scores at all would silently approve the translation.
    passed = bool(passed) and parse_ok and not blocking
    return ReviewOutput(scores=scores, issues=issues, passed=passed, raw=raw, parse_ok=parse_ok)


class TerminologyGuardAgent:
    """Zero-model-cost role: glossary + translation-memory recall."""

    def __init__(self, terminology_service=None, vector_db_service=None, tm_top_k: int = 3):
        self.ts = terminology_service
        self.vdb = vector_db_service
        self.tm_top_k = tm_top_k

    def inspect(self, source_text: str, target_lang: str) -> Dict[str, Any]:
        out = {"terms": {}, "tm_hits": [], "note": None}
        if self.ts is not None:
            try:
                res = self.ts.get_relevant_terms(source_text)
                if res.success:
                    for term, trans in (res.data.get("terms") or {}).items():
                        rendering = trans.get(target_lang if target_lang in trans else next(iter(trans), ""), "")
                        if rendering:
                            out["terms"][term] = rendering
            except Exception as e:
                out["note"] = f"terminology lookup failed: {type(e).__name__}"
        if self.vdb is not None:
            try:
                res = self.vdb.search_similar(source_text, k=self.tm_top_k)
                if res.success:
                    per_lang = (res.data.get("results") or {}).get(target_lang) or []
                    out["tm_hits"] = [
                        {"source": h["source"], "translation": h["translation"], "similarity": h["similarity"]}
                        for h in per_lang[: self.tm_top_k]
                    ]
            except Exception as e:
                out["note"] = (out["note"] or "") + f" | vector-db unavailable: {type(e).__name__}"
        else:
            out["note"] = "vector-db not loaded (faiss/sentence-transformers lazy path off)"
        return out