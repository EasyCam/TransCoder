"""Auto-sync the real exam library from GitHub.

Runs at startup in a daemon thread (throttled to once per 24h) and imports
every available year of 考研英语一/二 plus CET-4/6 sessions. Users never have to
pick or click: the catalog is filled automatically.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List

CONFIG_DIR = Path.home() / ".config" / "transcoder"
MARKER = CONFIG_DIR / "real_sync.json"
THROTTLE_SECONDS = 24 * 3600


def _load_marker() -> Dict[str, Any]:
    try:
        return json.loads(MARKER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_marker(data: Dict[str, Any]) -> None:
    try:
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _existing_keys() -> set:
    from transcoder.reading_store import list_user_articles

    return {(a.get("exam"), str(a.get("year")), a.get("title")) for a in list_user_articles()}


def sync_all(force: bool = False) -> Dict[str, Any]:
    """Import every missing real paper; returns counts. Never raises."""
    marker = _load_marker()
    if not force and time.time() - float(marker.get("ts", 0)) < THROTTLE_SECONDS:
        return {"skipped": "throttled", "ts": marker.get("ts")}

    from transcoder.reading_store import add_user_article
    from transcoder.real_exams import fetch_cet, fetch_kaoyan

    existing = _existing_keys()
    summary: Dict[str, Any] = {"imported": 0, "exam1": 0, "exam2": 0, "cet4": 0, "cet6": 0, "errors": []}
    plans = [
        ("exam1", lambda: fetch_kaoyan("english-i")),
        ("exam2", lambda: fetch_kaoyan("english-ii")),
        ("cet4", lambda: fetch_cet("CET4")),
        ("cet6", lambda: fetch_cet("CET6")),
    ]
    for name, fetch in plans:
        try:
            articles = fetch()
        except Exception as e:  # network / repo change
            summary["errors"].append(f"{name}: {e}")
            continue
        n = 0
        for a in articles:
            key = (a.get("exam"), str(a.get("year")), a.get("title"))
            if key in existing:
                continue
            try:
                add_user_article(a)
                existing.add(key)
                n += 1
                summary["imported"] += 1
            except ValueError:
                continue
        summary[name] = n

    summary["ts"] = time.time()
    _save_marker(summary)
    return summary


def start_background_sync() -> None:
    """Kick off a throttled sync without blocking the web server."""
    import os
    import threading

    if os.getenv("TRANSCODER_AUTO_SYNC", "1") == "0":
        return

    def _run():
        try:
            sync_all()
        except Exception:
            pass

    threading.Thread(target=_run, name="real-sync", daemon=True).start()
