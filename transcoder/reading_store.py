"""User-imported reading articles (real exam papers, teacher materials).

Stored outside the repo at ``~/.config/transcoder/reading.json`` so imported
copyrighted exam texts never land in version control.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

STORE_PATH = Path(
    os.getenv("TRANSCODER_READING_STORE", str(Path.home() / ".config" / "transcoder" / "reading.json"))
).expanduser()


def _load() -> List[Dict[str, Any]]:
    if not STORE_PATH.exists():
        return []
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(rows: List[Dict[str, Any]]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STORE_PATH)


def list_user_articles() -> List[Dict[str, Any]]:
    return _load()


def delete_user_article(article_id: str) -> bool:
    rows = _load()
    kept = [r for r in rows if r.get("id") != article_id]
    if len(kept) == len(rows):
        return False
    _save(kept)
    return True


def add_user_article(payload: Dict[str, Any]) -> Dict[str, Any]:
    exam = str(payload.get("exam") or "").strip()
    title = str(payload.get("title") or "").strip()
    passage = str(payload.get("passage") or "").strip()
    questions = payload.get("questions") or []
    if not exam or not title or not passage:
        raise ValueError("exam, title and passage are required")
    if not isinstance(questions, list) or not questions:
        raise ValueError("questions must be a non-empty list")

    clean_questions = []
    for q in questions:
        if not isinstance(q, dict):
            raise ValueError("each question must be an object")
        text = str(q.get("q") or "").strip()
        options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        answer = q.get("answer")
        if not text or len(options) < 2:
            raise ValueError("each question needs text and at least two options")
        if answer is None or answer == "":
            answer = -1  # key not available (e.g. CET source without answers)
        try:
            answer = int(answer)
        except (TypeError, ValueError):
            raise ValueError("answer must be an index or -1")
        if answer >= len(options):
            raise ValueError("answer index out of range")
        clean_questions.append({
            "q": text,
            "options": options,
            "answer": answer,
            "explain": str(q.get("explain") or "").strip(),
        })

    digest = hashlib.sha1(f"{exam}|{title}|{passage}".encode("utf-8")).hexdigest()[:12]
    article = {
        "id": "user-" + digest,
        "exam": exam,
        "year": str(payload.get("year") or "自定义").strip() or "自定义",
        "paper": str(payload.get("paper") or "导入").strip() or "导入",
        "title": title,
        "passage": passage,
        "questions": clean_questions,
        "has_key": all(q["answer"] >= 0 for q in clean_questions),
    }
    rows = [r for r in _load() if r.get("id") != article["id"]]
    rows.append(article)
    _save(rows)
    return article
