"""Local teaching store: human submissions, annotations, and telemetry events.

Everything is append-only JSONL under ``data/teaching/`` (override with
``TRANSCODER_TEACHING_DIR``). No database, no network, no secrets.
"""

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()
SUBMISSIONS = "submissions.jsonl"
ANNOTATIONS = "annotations.jsonl"
TELEMETRY = "telemetry.jsonl"


def store_root() -> Path:
    env = os.getenv("TRANSCODER_TEACHING_DIR")
    return Path(env) if env else Path(__file__).resolve().parent.parent / "data" / "teaching"


def _append_jsonl(filename: str, record: Dict[str, Any]) -> Dict[str, Any]:
    path = store_root() / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    record.setdefault("id", uuid.uuid4().hex[:12])
    record.setdefault("ts", round(time.time(), 3))
    line = json.dumps(record, ensure_ascii=False, default=str)
    with _LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return record


def _read_jsonl(filename: str) -> List[Dict[str, Any]]:
    path = store_root() / filename
    if not path.exists():
        return []
    rows = []
    with _LOCK:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return rows


# --------------------------------------------------------------------------- #
# submissions (human translation + optional AI grade)
# --------------------------------------------------------------------------- #
def add_submission(
    source_text: str,
    translation: str,
    source_lang: str = "",
    target_lang: str = "",
    grade: Optional[Dict[str, Any]] = None,
    polish: Optional[Dict[str, Any]] = None,
    endpoint: Optional[str] = None,
    model: Optional[str] = None,
    author: Optional[str] = None,
) -> Dict[str, Any]:
    return _append_jsonl(SUBMISSIONS, {
        "source_text": source_text,
        "translation": translation,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "grade": grade,
        "polish": polish,
        "endpoint": endpoint,
        "model": model,
        "author": author,
    })


def list_submissions(limit: int = 50) -> List[Dict[str, Any]]:
    rows = _read_jsonl(SUBMISSIONS)
    return rows[-limit:][::-1]


# --------------------------------------------------------------------------- #
# annotations (span-level marking on a translation)
# --------------------------------------------------------------------------- #
def add_annotation(
    submission_id: str,
    quote: str = "",
    note: str = "",
    kind: str = "note",
    start: Optional[int] = None,
    end: Optional[int] = None,
    target_lang: Optional[str] = None,
    author: Optional[str] = None,
    src_quote: Optional[str] = None,
    src_start: Optional[int] = None,
    src_end: Optional[int] = None,
) -> Dict[str, Any]:
    return _append_jsonl(ANNOTATIONS, {
        "submission_id": submission_id,
        "quote": (quote or "")[:300],
        "note": (note or "")[:1000],
        "kind": kind or "note",
        "start": start,
        "end": end,
        "target_lang": target_lang,
        "author": author,
        "src_quote": (src_quote or "")[:300] or None,
        "src_start": src_start,
        "src_end": src_end,
    })


def list_annotations(submission_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    rows = _read_jsonl(ANNOTATIONS)
    if submission_id:
        rows = [r for r in rows if r.get("submission_id") == submission_id]
    return rows[-limit:][::-1]


def delete_annotation(annotation_id: str) -> bool:
    path = store_root() / ANNOTATIONS
    if not path.exists():
        return False
    with _LOCK:
        rows = _read_jsonl(ANNOTATIONS)
        kept = [r for r in rows if r.get("id") != annotation_id]
        if len(kept) == len(rows):
            return False
        with open(path, "w", encoding="utf-8") as f:
            for r in kept:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return True


# --------------------------------------------------------------------------- #
# telemetry (teaching analytics)
# --------------------------------------------------------------------------- #
def record_event(event: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _append_jsonl(TELEMETRY, {"event": (event or "unknown")[:64], "payload": payload or {}})


def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def telemetry_summary(days: int = 7) -> Dict[str, Any]:
    cutoff = time.time() - max(1, int(days)) * 86400
    events = [e for e in _read_jsonl(TELEMETRY) if float(e.get("ts", 0)) >= cutoff]
    subs = [s for s in _read_jsonl(SUBMISSIONS) if float(s.get("ts", 0)) >= cutoff]
    anns = [a for a in _read_jsonl(ANNOTATIONS) if float(a.get("ts", 0)) >= cutoff]

    by_event: Dict[str, int] = {}
    by_day: Dict[str, int] = {}
    for e in events:
        name = str(e.get("event", "unknown"))
        by_event[name] = by_event.get(name, 0) + 1
        d = _day(float(e.get("ts", 0)))
        by_day[d] = by_day.get(d, 0) + 1

    overalls = [
        s["grade"]["overall"] for s in subs
        if isinstance(s.get("grade"), dict) and isinstance(s["grade"].get("overall"), (int, float))
    ]
    polish_edits = [
        len(s["polish"].get("edits") or []) for s in subs
        if isinstance(s.get("polish"), dict)
    ]
    return {
        "window_days": int(days),
        "events_total": len(events),
        "events_by_type": by_event,
        "events_by_day": by_day,
        "submissions": len(subs),
        "annotations": len(anns),
        "graded": len(overalls),
        "avg_overall_score": round(sum(overalls) / len(overalls), 2) if overalls else None,
        "polished": len(polish_edits),
        "avg_polish_edits": round(sum(polish_edits) / len(polish_edits), 2) if polish_edits else None,
    }
