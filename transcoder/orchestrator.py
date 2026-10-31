"""
TransCoder-NEXT orchestrator (P2/P3): rule-based team protocol + degradation.

Protocol per review round (spec-agent-design.md §2, max `team-rounds` = 3):
    guard.inspect -> translator.translate -> reviewer.review
    if not review.pass and round < max: translator.rewrite(issues) -> re-review

Degradation chain (spec §2): when the configured reviewer is unavailable at
start (or errors on every attempt), fall back to the EXISTING single-model
self-reflection mechanism (`TranslationService.translate_with_reflection`,
unchanged) and record `degraded: true` with the reason. Events are the raw
data layer: every step appends one redacted JSON line (EventLog).
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcoder.agents import ReviewIssue, ReviewOutput, TranslationOutput
from transcoder.endpoints import redact
from transcoder.tokcount import count_tokens


class EventLog:
    """Append-only JSONL event log with guaranteed redaction."""

    SCHEMA = "transcoder-next/events/v1"

    def __init__(self, path: Optional[Path] = None, run_id: Optional[str] = None, enabled: bool = True):
        self.path = Path(path) if path else None
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.enabled = enabled
        self._n = 0

    def log(self, event: str, role: str = "", payload: Optional[dict] = None, **extra) -> dict:
        rec = {
            "schema": self.SCHEMA,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "seq": self._n,
            "run_id": self.run_id,
            "event": event,
            "role": role,
        }
        if payload:
            rec["payload"] = payload
        rec.update(extra)
        self._n += 1
        if self.enabled and self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(redact(rec), ensure_ascii=False, default=str) + "\n")
        return rec

    def read_events(self) -> List[dict]:
        if not self.path or not self.path.exists():
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out


@dataclass
class TeamResult:
    final_translation: str
    rounds: List[dict] = field(default_factory=list)
    final_review: Optional[dict] = None
    degraded: bool = False
    degraded_reason: Optional[str] = None
    total_latency_s: float = 0.0
    tokens: Dict[str, int] = field(default_factory=dict)
    guard: Optional[dict] = None
    review_failed: bool = False
    run_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict_safe(self)


def asdict_safe(obj: Any) -> Any:
    import dataclasses

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        # asdict() deep-converts nested dataclasses; then normalize values.
        return asdict_safe(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {k: asdict_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [asdict_safe(v) for v in obj]
    return obj


def is_broad_rewrite(prev: str, new: str, issues, *, min_similarity: float = 0.6,
                     max_span_ratio: float = 0.35) -> bool:
    """True when a rewrite changes far more text than the quoted issues justify.

    A rewrite may touch the quoted spans and a little context. If the quoted spans
    cover a small share of the text yet the output is largely different, the model
    has re-sequenced or re-phrased material that no issue mentions.
    """
    from difflib import SequenceMatcher

    if not prev or not new:
        return False
    span_chars = sum(len(i.span) for i in issues if getattr(i, "span", ""))
    span_ratio = span_chars / max(len(prev), 1)
    similarity = SequenceMatcher(None, prev, new).ratio()
    return similarity < min_similarity and span_ratio < max_span_ratio


class TeamOrchestrator:
    """Rule-based orchestration of the four-role team."""

    def __init__(
        self,
        translator,                       # TranslatorAgent (edge small model)
        reviewer=None,                    # ReviewerAgent (online big OR local small)
        reviewer_fallback=None,           # used when the primary reviewer cannot produce valid JSON
        guard=None,                       # TerminologyGuardAgent
        max_rounds: int = 3,
        event_log: Optional[EventLog] = None,
        local_fallback=None,              # TranslationService for degraded path (same provider)
        team_evaluator=None,              # optional internal quality check (separate from paper metrics)
        seed: Optional[int] = None,
        minimal_edit: bool = False,       # reject rewrites that change text no issue mentions
        span_rewrite: bool = False,       # rewrite only the quoted spans and splice them back
    ):
        self.translator = translator
        self.reviewer = reviewer
        self.reviewer_fallback = reviewer_fallback
        self.guard = guard
        self.max_rounds = max(1, int(max_rounds))
        self.event_log = event_log or EventLog()
        self.local_fallback = local_fallback
        self.team_evaluator = team_evaluator
        self.seed = seed
        self.minimal_edit = minimal_edit
        self.span_rewrite = span_rewrite

    # -- availability ------------------------------------------------------ #

    def reviewer_available(self) -> bool:
        if self.reviewer is None:
            return False
        try:
            return bool(self.reviewer.provider.is_available())
        except Exception:
            return False

    def _review_with_retry(self, source_text, translation, source_lang, target_lang, terms, ev, round_i):
        """Primary review -> strict retry -> fallback reviewer. Never silently passes."""
        review = self.reviewer.review(
            source_text, translation, source_lang, target_lang, glossary=terms, seed=self.seed,
        )
        if review.parse_ok or review.error:
            return review
        ev.log("reviewer.retry", role="reviewer", payload={"round": round_i, "reason": "unparseable JSON"})
        review = self.reviewer.review(
            source_text, translation, source_lang, target_lang, glossary=terms, seed=self.seed, strict=True,
        )
        if review.parse_ok or review.error:
            return review
        if self.reviewer_fallback is not None:
            ev.log("reviewer.fallback", role="orchestrator", payload={
                "round": round_i, "from": getattr(self.reviewer, "model", None),
                "to": getattr(self.reviewer_fallback, "model", None),
            })
            self.reviewer = self.reviewer_fallback
            self.reviewer_fallback = None
            review = self.reviewer.review(
                source_text, translation, source_lang, target_lang, glossary=terms, seed=self.seed, strict=True,
            )
        return review

    # -- main entry -------------------------------------------------------- #

    def run(self, source_text: str, source_lang: str, target_lang: str, dry: bool = False) -> TeamResult:
        t_start = time.time()
        ev = self.event_log
        ev.log("run.start", payload={
            "source_lang": source_lang, "target_lang": target_lang,
            "translator_model": self.translator.model,
            "reviewer_model": self.reviewer.model if self.reviewer else None,
            "max_rounds": self.max_rounds, "seed": self.seed, "dry": dry,
            "source_tokens_o200k": count_tokens(source_text),
        })

        guard_out = {}
        if self.guard is not None:
            guard_out = self.guard.inspect(source_text, target_lang)
            ev.log("guard.inspect", role="terminology_guard", payload=guard_out)

        result = TeamResult(final_translation="", guard=guard_out, run_id=ev.run_id)

        degraded_probe = (self.reviewer is None) or (not self.reviewer_available())
        if degraded_probe:
            reason = "no reviewer configured" if self.reviewer is None else "reviewer endpoint unreachable (is_available=False)"
            ev.log("degraded.start", role="orchestrator", payload={"reason": reason, "via": "local self-reflection (existing mechanism)"})
            result.degraded = True
            result.degraded_reason = reason
            fb = self._run_local_fallback(source_text, source_lang, target_lang, dry)
            result.final_translation = fb["text"]
            result.rounds = fb["rounds"]
            result.tokens = {"translator_out": sum(r.get("tokens_out", 0) for r in fb["rounds"])}
            result.total_latency_s = round(time.time() - t_start, 3)
            ev.log("degraded.end", role="orchestrator", payload={
                "rounds": len(fb["rounds"]), "final_tokens_o200k": count_tokens(result.final_translation),
            })
            ev.log("run.end", payload={"final_latency_s": result.total_latency_s, "degraded": True})
            return result

        if dry:
            plan = self._plan_events(source_text, target_lang)
            for step in plan:
                ev.log("dry.plan", role=step["role"], payload=step)
            ev.log("run.end", payload={"dry": True})
            result.final_translation = ""
            return result

        online_review = self.reviewer_available()
        if not online_review:
            ev.log("degraded.start", role="orchestrator", payload={"reason": "reviewer became unavailable at run time", "via": "local self-reflection (existing mechanism)"})
            result.degraded = True
            result.degraded_reason = "reviewer unavailable at run time"
            fb = self._run_local_fallback(source_text, source_lang, target_lang, dry)
            result.final_translation = fb["text"]
            result.rounds = fb["rounds"]
            result.total_latency_s = round(time.time() - t_start, 3)
            ev.log("run.end", payload={"final_latency_s": result.total_latency_s})
            return result

        tokens = {"translator_in": 0, "translator_out": 0, "reviewer_in": 0, "reviewer_out": 0}
        current: Optional[TranslationOutput] = None
        review: Optional[ReviewOutput] = None

        for round_i in range(1, self.max_rounds + 1):
            if current is None:
                current = self.translator.translate(
                    source_text, source_lang, target_lang,
                    glossary=(guard_out or {}).get("terms"), memory=(guard_out or {}).get("tm_hits"), seed=self.seed,
                )
                ev.log("translator.translate", role="translator", payload={
                    "round": round_i, "translation": current.translation,
                    "model": current.model, "error": current.error,
                }, latency_s=current.latency_s, tokens_in=current.tokens_in, tokens_out=current.tokens_out)
            if current.error:
                ev.log("translator.error", role="translator", payload={"round": round_i, "error": str(current.error)})
                result.final_translation = ""
                result.total_latency_s = round(time.time() - t_start, 3)
                ev.log("run.end", payload={"error": current.error})
                return result
            tokens["translator_in"] += current.tokens_in
            tokens["translator_out"] += current.tokens_out

            review = self._review_with_retry(
                source_text, current.translation, source_lang, target_lang,
                (guard_out or {}).get("terms"), ev, round_i,
            )
            ev.log("reviewer.review", role="reviewer", payload={
                "round": round_i, "scores": review.scores, "issues": [i.to_dict() for i in review.issues],
                "pass": review.passed, "parse_ok": review.parse_ok, "model": review.model, "error": review.error,
            }, latency_s=review.latency_s, tokens_in=review.tokens_in, tokens_out=review.tokens_out)
            tokens["reviewer_in"] += review.tokens_in
            tokens["reviewer_out"] += review.tokens_out

            result.rounds.append({
                "round": round_i,
                "translation": current.translation,
                "review": {k: v for k, v in review.to_dict().items() if k != "raw"},
            })
            if review.error:
                # reviewer errored mid-run -> degrade to local reflection for this pair
                ev.log("degraded.start", role="orchestrator", payload={"reason": f"reviewer error at round {round_i}: {review.error}", "via": "local self-reflection (existing mechanism)"})
                result.degraded = True
                result.degraded_reason = f"reviewer error at round {round_i}"
                fb = self._run_local_fallback(source_text, source_lang, target_lang, dry)
                result.final_translation = fb["text"]
                result.rounds += fb["rounds"]
                break

            if review.passed:
                ev.log("orchestrator.decision", role="orchestrator", payload={
                    "round": round_i, "action": "accept", "reason": "review.pass",
                })
                break
            if review.parse_ok is False:
                result.review_failed = True
                ev.log("orchestrator.decision", role="orchestrator", payload={
                    "round": round_i, "action": "accept", "reason": "review unparseable -> accepted WITHOUT review",
                })
                break
            if round_i == self.max_rounds:
                ev.log("orchestrator.decision", role="orchestrator", payload={"round": round_i, "action": "accept", "reason": "max rounds reached"})
                break

            prev_text = current.translation
            if self.span_rewrite:
                rewritten = self.translator.rewrite_spans(
                    target_lang, prev_text, review.issues, seed=self.seed,
                )
                if rewritten.meta:
                    ev.log("translator.span_rewrite", role="translator", payload={
                        "round": round_i, **rewritten.meta})
            else:
                rewritten = self.translator.rewrite(
                    source_text, target_lang, prev_text, review.issues, source_lang=source_lang, seed=self.seed,
                )
            if self.minimal_edit and not rewritten.error:
                from difflib import SequenceMatcher
                if is_broad_rewrite(prev_text, rewritten.translation, review.issues):
                    similarity = SequenceMatcher(None, prev_text, rewritten.translation).ratio()
                    span_ratio = sum(len(i.span) for i in review.issues if i.span) / max(len(prev_text), 1)
                    ev.log("translator.rewrite_rejected", role="orchestrator", payload={
                        "round": round_i, "similarity": round(similarity, 3),
                        "span_ratio": round(span_ratio, 3), "kept": prev_text,
                        "discarded": rewritten.translation,
                    })
                    rewritten = type(rewritten)(translation=prev_text, tokens_in=rewritten.tokens_in,
                                                tokens_out=rewritten.tokens_out, latency_s=rewritten.latency_s,
                                                model=rewritten.model, error=None)
            current = rewritten
            ev.log("translator.rewrite", role="translator", payload={
                "round": round_i, "translation": current.translation, "model": current.model, "error": current.error,
            }, latency_s=current.latency_s, tokens_in=current.tokens_in, tokens_out=current.tokens_out)
            tokens["translator_in"] += current.tokens_in
            tokens["translator_out"] += current.tokens_out
            if current.error:
                ev.log("translator.error", role="translator", payload={"round": round_i, "error": str(current.error)})
                break

        result.final_translation = current.translation if current else ""
        result.final_review = {k: v for k, v in review.to_dict().items() if k != "raw"} if review else None
        result.tokens = tokens
        result.total_latency_s = round(time.time() - t_start, 3)
        ev.log("run.end", payload={
            "final_latency_s": result.total_latency_s, "rounds": len(result.rounds),
            "tokens": tokens, "degraded": result.degraded,
            "final_tokens_o200k": count_tokens(result.final_translation),
        })
        if self.team_evaluator is not None:
            try:
                ev.log("team.evaluate", payload=redact(self.team_evaluator(source_text, result.final_translation, target_lang)))
            except Exception as e:
                ev.log("team.evaluate", payload={"error": str(e)})
        return result

    # -- degradation & dry-plan -------------------------------------------- #

    def _run_local_fallback(self, source_text, source_lang, target_lang, dry) -> dict:
        """Existing single-model self-reflection (translate_with_reflection L199)."""
        rounds = []
        text = ""
        if dry:
            ev_rec = self.event_log.log("local_fallback.planned", role="translator",
                                        payload={"mechanism": "translate_with_reflection(iterations=1)", "dry": True})
            return {"text": "", "rounds": [{"round": 1, "mechanism": "local self-reflection (dry)"}]}
        if self.local_fallback is None:
            self.event_log.log("degraded.failed", role="orchestrator", payload={"reason": "no local self-reflection mechanism attached"})
            return {"text": "", "rounds": rounds}
        try:
            res = self.local_fallback.translate_with_reflection(source_text, source_lang, target_lang,
                                                                model=self.translator.model, iterations=1)
            if res.success:
                text = res.data.get("text", "")
                for h in res.data.get("reflection_history", []):
                    rounds.append({
                        "round": h.get("iteration"),
                        "mechanism": "local self-reflection",
                        "reflection": str(h.get("reflection", ""))[:500],
                        "translation": h.get("improved_translation", ""),
                        "tokens_out": count_tokens(h.get("improved_translation", "")),
                    })
                self.event_log.log("local_fallback.done", role="translator", payload={
                    "mechanism": "translate_with_reflection(iterations=1)", "final_tokens_o200k": count_tokens(text),
                })
            else:
                self.event_log.log("local_fallback.failed", role="translator", payload={"error": str(res.error)})
        except Exception as e:
            self.event_log.log("local_fallback.failed", role="translator", payload={"error": redact(f"{type(e).__name__}: {e}")})
        return {"text": text, "rounds": rounds}

    def _plan_events(self, source_text: str, target_lang: str) -> List[dict]:
        plan = [
            {"step": 1, "role": "terminology_guard", "action": "inspect"},
            {"step": 2, "role": "translator", "action": "translate", "model": self.translator.model},
        ]
        for r in range(1, self.max_rounds + 1):
            plan.append({"step": 2 * r + 1, "role": "reviewer", "action": "review", "model": self.reviewer.model if self.reviewer else None})
            plan.append({"step": 2 * r + 2, "role": "orchestrator", "action": "review.pass? rewrite : accept"})
        plan.append({"step": 2 * self.max_rounds + 3, "role": "orchestrator", "action": "event log close"})
        return plan