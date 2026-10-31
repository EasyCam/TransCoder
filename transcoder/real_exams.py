"""Fetch real exam papers from public GitHub repositories into the local library.

Sources:
- 考研英语一/二 (2010-2026): Echo1LZJY/echo-kaoyan-english-skill — full papers with
  the official objective answer key.
- CET-4 / CET-6 (2023.06, 2023.12): wamich/english-exem-md — Markdown papers.

Nothing is bundled into the repo: fetching happens on demand and lands in the
local reading library. GitHub is often unreachable on mainland networks, so a
local proxy (7897/1080/...) is tried automatically.
"""

import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional

KAOYAN_REPO = "Echo1LZJY/echo-kaoyan-english-skill"
KAOYAN_BRANCH = "main"
KAOYAN_DIR = "skills/kaoyan-english/references/papers"

CET_REPO = "wamich/english-exem-md"
CET_BRANCH = "main"

_TIMEOUT = 45


def _opener() -> urllib.request.OpenerDirector:
    proxies = []
    for env_key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.getenv(env_key)
        if v:
            proxies.append(v)
    proxies += ["http://127.0.0.1:7897", "http://127.0.0.1:1080", "http://127.0.0.1:8080"]
    # urllib only supports one proxy; first candidate wins, callers may retry.
    proxy = proxies[0] if proxies else None
    handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    return urllib.request.build_opener(handler)


def _http(url: str, retries: int = 3) -> str:
    last = None
    for i in range(retries):
        try:
            with _opener().open(url, timeout=_TIMEOUT) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:  # try the next proxy on the next attempt
            last = e
            if i == 1:
                # switch to the next candidate by dropping env proxy
                os.environ.pop("HTTPS_PROXY", None)
                os.environ.pop("https_proxy", None)
                os.environ.pop("HTTP_PROXY", None)
                os.environ.pop("http_proxy", None)
    raise RuntimeError(f"fetch failed: {url}: {last}")


def _raw(repo: str, branch: str, path: str) -> str:
    return _http(f"https://raw.githubusercontent.com/{repo}/{branch}/{path}")


def _tree(repo: str, branch: str) -> List[str]:
    data = json.loads(_http(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"))
    if "tree" not in data:
        raise RuntimeError(f"github tree error: {data.get('message', 'no tree')}")
    return [t["path"] for t in data.get("tree", []) if t.get("type") == "blob"]


# --------------------------------------------------------------------------- #
# listing
# --------------------------------------------------------------------------- #
def list_options() -> Dict[str, List[str]]:
    """Available years / sessions per source (network required)."""
    out: Dict[str, List[str]] = {"kaoyan": [], "cet4": [], "cet6": []}
    try:
        kaoyan_paths = _tree(KAOYAN_REPO, KAOYAN_BRANCH)
        years = set()
        for p in kaoyan_paths:
            m = re.search(rf"{re.escape(KAOYAN_DIR)}/english-(i|ii)/(\d{{4}})/paper\.md$", p)
            if m:
                years.add(m.group(2))
        out["kaoyan"] = sorted(years)
    except Exception:
        pass
    try:
        cet_paths = _tree(CET_REPO, CET_BRANCH)
        for level in ("cet4", "cet6"):
            sessions = set()
            for p in cet_paths:
                m = re.match(rf"{level.upper()}/(\d{{4}}\.\d{{2}})/", p, re.I)
                if m:
                    sessions.add(m.group(1))
            out[level] = sorted(sessions)
    except Exception:
        pass
    return out


# --------------------------------------------------------------------------- #
# Kaoyan parser
# --------------------------------------------------------------------------- #
_OPT = re.compile(r"^\[([A-G])\]\s*(.*)$")
_Q = re.compile(r"^(\d{1,2})\.\s+(.*)$")


def parse_kaoyan_paper(md: str, answers: Dict[str, Any], year: str, paper_label: str) -> List[Dict[str, Any]]:
    """Split one full paper into per-Text reading articles (with answer key)."""
    articles: List[Dict[str, Any]] = []
    heads = list(re.finditer(r"^Text\s+(\d+)\s*$", md, re.M))
    for idx, head in enumerate(heads):
        n = head.group(1)
        end = heads[idx + 1].start() if idx + 1 < len(heads) else len(md)
        block = md[head.end():end]
        lines = block.splitlines()
        passage_lines: List[str] = []
        questions: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        for line in lines:
            qm = _Q.match(line.strip())
            om = _OPT.match(line.strip())
            if qm and not om:
                current = {"q": qm.group(2).strip(), "options": [], "num": qm.group(1)}
                questions.append(current)
                continue
            if om and current is not None:
                current["options"].append(om.group(2).strip())
                continue
            if current is None:
                passage_lines.append(line)
        if len(questions) < 3:
            continue
        key = (answers.get("answers") or {}).get(f"reading-text-{n}") or {}
        if key:
            # drop trailing questions that belong to the next section (e.g. Part B)
            questions = [q for q in questions if str(int(q["num"])) in key]
        clean_qs = []
        for q in questions:
            letter = str(key.get(str(int(q["num"])), "")).upper()
            ans = ord(letter) - 65 if letter and "A" <= letter <= "G" else -1
            if ans < 0 or ans >= len(q["options"]):
                ans = -1
            clean_qs.append({
                "q": q["q"],
                "options": q["options"],
                "answer": ans,
                "explain": f"官方答案：{letter}" if ans >= 0 else "官方答案未收录",
            })
        articles.append({
            "exam": "kaoyan",
            "year": year,
            "paper": paper_label,
            "title": f"{year} {paper_label} Text {n}",
            "passage": "\n".join(passage_lines).strip(),
            "questions": clean_qs,
        })
    return articles


def fetch_kaoyan(paper: str = "english-i", years: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Fetch + parse real Kaoyan papers. paper: english-i | english-ii."""
    label = "英语一" if paper == "english-i" else "英语二"
    paths = _tree(KAOYAN_REPO, KAOYAN_BRANCH)
    year_dirs = set()
    for p in paths:
        m = re.search(rf"{re.escape(KAOYAN_DIR)}/{paper}/(\d{{4}})/paper\.md$", p)
        if m:
            year_dirs.add(m.group(1))
    if years:
        year_dirs = {y for y in year_dirs if y in set(years)}
    out: List[Dict[str, Any]] = []
    for year in sorted(year_dirs):
        base = f"{KAOYAN_DIR}/{paper}/{year}"
        try:
            md = _raw(KAOYAN_REPO, KAOYAN_BRANCH, f"{base}/paper.md")
            answers = json.loads(_raw(KAOYAN_REPO, KAOYAN_BRANCH, f"{base}/answers.json"))
        except Exception:
            continue
        out.extend(parse_kaoyan_paper(md, answers, year, label))
    return out


# --------------------------------------------------------------------------- #
# CET parser
# --------------------------------------------------------------------------- #
_CET_OPT = re.compile(r"^[A-D]\)\s*(.*)$")
_CET_Q = re.compile(r"^(\d{2})\.\s*(.*)$")


def parse_cet_paper(md: str, level: str, session: str, variant: str) -> List[Dict[str, Any]]:
    """Extract the two Section C reading passages (questions, no official key)."""
    start = md.find("Part III")
    if start < 0:
        return []
    sec = md[md.find("### Section C", start):]
    chunks = re.split(r"^####\s+Passage\s+(One|Two)\s*$", sec, flags=re.M)
    articles: List[Dict[str, Any]] = []
    for i in range(1, len(chunks), 2):
        name = chunks[i]
        body = chunks[i + 1] if i + 1 < len(chunks) else ""
        lines = body.splitlines()
        passage_lines: List[str] = []
        questions: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        for line in lines:
            s = line.strip()
            qm = _CET_Q.match(s)
            om = _CET_OPT.match(s)
            if qm:
                current = {"q": qm.group(2).strip(), "options": [], "num": qm.group(1)}
                questions.append(current)
                continue
            if om and current is not None:
                current["options"].append(om.group(1).strip())
                continue
            if current is None and s and not s.startswith("**Questions") and not s.startswith("**Directions"):
                passage_lines.append(line)
        if len(questions) < 3:
            continue
        articles.append({
            "exam": level.lower(),
            "year": session,
            "paper": f"{session} 卷{variant}",
            "title": f"{level.upper()} {session} 卷{variant} Passage {name}",
            "passage": "\n".join(passage_lines).strip(),
            "questions": [{
                "q": q["q"],
                "options": q["options"],
                "answer": -1,
                "explain": "官方答案未收录（该来源仅提供题面）",
            } for q in questions if len(q["options"]) >= 2],
            "has_key": False,
        })
    return articles


def fetch_cet(level: str = "CET4", session: Optional[str] = None) -> List[Dict[str, Any]]:
    level_dir = level.upper()
    paths = _tree(CET_REPO, CET_BRANCH)
    files = [p for p in paths if re.match(rf"{level_dir}/", p) and p.endswith(".md")]
    if session:
        files = [p for p in files if f"/{session}/" in p]
    out: List[Dict[str, Any]] = []
    for p in sorted(files):
        m = re.match(rf"{level_dir}/([\d.]+)/([^/]+)\.md$", p)
        if not m:
            continue
        sess, fname = m.group(1), m.group(2)
        variant = fname.split("-")[-1]
        try:
            md = _raw(CET_REPO, CET_BRANCH, p)
        except Exception:
            continue
        out.extend(parse_cet_paper(md, level_dir, sess, variant))
    return out
