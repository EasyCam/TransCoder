"""Unified content library import/export: reading articles, writing prompts,
speech passages. User content lives outside the repo under ~/.config/transcoder.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

CONFIG_DIR = Path(os.getenv("TRANSCODER_CONFIG_DIR", str(Path.home() / ".config" / "transcoder"))).expanduser()
WRITING_PATH = CONFIG_DIR / "writing_prompts.json"
SPEECH_PATH = CONFIG_DIR / "speech_passages.json"


def _load(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# --------------------------------------------------------------------------- #
# writing prompts
# --------------------------------------------------------------------------- #
def user_writing_prompts() -> List[Dict[str, Any]]:
    return _load(WRITING_PATH)


def add_writing_prompt(payload: Dict[str, Any]) -> Dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    prompt = str(payload.get("prompt") or "").strip()
    if not title or not prompt:
        raise ValueError("title and prompt are required")
    entry = {
        "id": str(payload.get("id") or f"user-{abs(hash((title, prompt))) % 10**10}"),
        "level": str(payload.get("level") or "自定义"),
        "title": title,
        "prompt": prompt,
        "lang": str(payload.get("lang") or "zh"),
    }
    rows = [r for r in _load(WRITING_PATH) if r.get("id") != entry["id"] and r.get("title") != title]
    rows.append(entry)
    _save(WRITING_PATH, rows)
    return entry


# --------------------------------------------------------------------------- #
# speech passages
# --------------------------------------------------------------------------- #
def user_speech_passages() -> List[Dict[str, Any]]:
    return _load(SPEECH_PATH)


def add_speech_passage(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = str(payload.get("text") or "").strip()
    if not text:
        raise ValueError("text is required")
    entry = {
        "id": str(payload.get("id") or f"user-{abs(hash(text)) % 10**10}"),
        "level": str(payload.get("level") or "自定义"),
        "text": text,
        "lang": str(payload.get("lang") or "zh"),
    }
    rows = [r for r in _load(SPEECH_PATH) if r.get("id") != entry["id"] and r.get("text") != text]
    rows.append(entry)
    _save(SPEECH_PATH, rows)
    return entry


# --------------------------------------------------------------------------- #
# export / import
# --------------------------------------------------------------------------- #
def export_content(kind: str) -> Dict[str, Any]:
    if kind == "reading":
        from transcoder.reading_bank import _all_articles

        return {"kind": "reading", "version": 1, "items": [
            {
                "exam": a.get("exam", ""), "year": a.get("year", ""), "paper": a.get("paper", ""),
                "title": a.get("title", ""), "passage": a.get("passage", ""),
                "questions": [
                    {"q": q.get("q", ""), "options": list(q.get("options") or []),
                     "answer": q.get("answer", -1), "explain": q.get("explain", "")}
                    for q in (a.get("questions") or [])
                ],
            }
            for a in _all_articles()
        ]}
    if kind == "writing":
        from transcoder.writing_prompts import PROMPTS_BY_LANG

        items = []
        for lang, bank in PROMPTS_BY_LANG.items():
            for p in bank:
                items.append(dict(p, lang=lang))
        items += user_writing_prompts()
        return {"kind": "writing", "version": 1, "items": items}
    if kind == "speech":
        from transcoder.speech import PASSAGES_BY_LANG

        items = []
        for lang, bank in PASSAGES_BY_LANG.items():
            for p in bank:
                items.append(dict(p, lang=lang))
        items += user_speech_passages()
        return {"kind": "speech", "version": 1, "items": items}
    raise ValueError(f"unknown content kind: {kind}")


def import_content(kind: str, payload: Any) -> Dict[str, int]:
    if isinstance(payload, dict):
        items = payload.get("items")
    else:
        items = payload
    if not isinstance(items, list):
        raise ValueError("payload must contain an items array")

    imported = 0
    skipped = 0
    if kind == "reading":
        from transcoder.reading_bank import ARTICLES
        from transcoder.reading_store import add_user_article

        builtin_keys = {(a.get("exam"), a.get("title"), a.get("passage")) for a in ARTICLES}
        for it in items:
            if not isinstance(it, dict):
                skipped += 1
                continue
            if (it.get("exam"), it.get("title"), it.get("passage")) in builtin_keys:
                skipped += 1
                continue
            try:
                add_user_article(it)
                imported += 1
            except ValueError:
                skipped += 1
        return {"imported": imported, "skipped": skipped}

    if kind == "writing":
        for it in items:
            try:
                add_writing_prompt(it)
                imported += 1
            except (ValueError, TypeError):
                skipped += 1
        return {"imported": imported, "skipped": skipped}

    if kind == "speech":
        for it in items:
            try:
                add_speech_passage(it)
                imported += 1
            except (ValueError, TypeError):
                skipped += 1
        return {"imported": imported, "skipped": skipped}

    raise ValueError(f"unknown content kind: {kind}")
