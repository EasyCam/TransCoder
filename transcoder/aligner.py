"""Automatic word/phrase correspondence between a source text and its translation.

Fully automatic: tokenise both sides, embed every token with the same
multilingual encoder used for semantic scoring, solve an optimal one-to-one
matching (Hungarian algorithm) over cosine similarity, and keep pairs above a
threshold. No user selection is required.
"""

import re
from typing import Any, Dict, List, Optional

import numpy as np

from transcoder.semantic_scorer import get_scorer

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-яЁё'’\-]+|\d+")
_NOISE = set("，。、；：？！“”‘’（）()[]{}<>《》〈〉,.!?;:\"'—–…·")


def _cjk_tokens(text: str) -> List[Dict[str, Any]]:
    """Non-overlapping CJK bigrams (single char when isolated) with offsets."""
    out: List[Dict[str, Any]] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if _CJK.match(ch):
            j = i + 1
            if j < n and _CJK.match(text[j]):
                out.append({"text": text[i:j + 1], "start": i, "end": j + 1})
                i = j + 1
            else:
                out.append({"text": ch, "start": i, "end": i + 1})
                i += 1
        else:
            i += 1
    return out


def _latin_tokens(text: str) -> List[Dict[str, Any]]:
    return [{"text": m.group(0), "start": m.start(), "end": m.end()} for m in _LATIN.finditer(text)]


def _tokens(text: str) -> List[Dict[str, Any]]:
    """Latin word tokens plus CJK segment tokens, in text order."""
    tokens = _latin_tokens(text) + _cjk_tokens(text)
    tokens = [t for t in tokens if t["text"] not in _NOISE and t["text"].strip()]
    return sorted(tokens, key=lambda t: t["start"])


def _segment(text: str) -> List[Dict[str, Any]]:
    """Prefer jieba for Chinese when available (much better word boundaries)."""
    try:
        import jieba  # type: ignore

        out = []
        for word, start, end in jieba.tokenize(text):
            word = word.strip()
            if not word or word in _NOISE:
                continue
            out.append({"text": word, "start": start, "end": end})
        if out:
            return out
    except Exception:
        pass
    return _tokens(text)


def align_texts(source_text: str, translation: str, max_pairs: int = 60,
                threshold: float = 0.42, embed=None) -> Dict[str, Any]:
    """Return automatic token-level correspondences with character offsets."""
    source_text = source_text or ""
    translation = translation or ""
    src_tokens = _segment(source_text)[:80]
    tgt_tokens = _segment(translation)[:80]
    if not src_tokens or not tgt_tokens:
        return {"pairs": [], "count": 0, "note": "empty side"}

    scorer_embed = embed or get_scorer().embed
    texts = [t["text"] for t in src_tokens] + [t["text"] for t in tgt_tokens]
    emb = np.asarray(scorer_embed(texts), dtype=float)

    m, n = len(src_tokens), len(tgt_tokens)
    src_emb, tgt_emb = emb[:m], emb[m:]
    sim = src_emb @ tgt_emb.T

    pairs: List[Dict[str, Any]] = []
    try:
        from scipy.optimize import linear_sum_assignment

        rows, cols = linear_sum_assignment(-sim)
        for r, c in zip(rows, cols):
            score = float(sim[r, c])
            if score < threshold:
                continue
            pairs.append({
                "src": src_tokens[r]["text"], "src_start": src_tokens[r]["start"],
                "src_end": src_tokens[r]["end"],
                "tgt": tgt_tokens[c]["text"], "tgt_start": tgt_tokens[c]["start"],
                "tgt_end": tgt_tokens[c]["end"],
                "score": round(score, 4),
            })
    except Exception:
        # Fallback: greedy best match per source token.
        used = set()
        for r in range(m):
            order = np.argsort(-sim[r])
            for c in order:
                c = int(c)
                if c in used or sim[r, c] < threshold:
                    continue
                used.add(c)
                pairs.append({
                    "src": src_tokens[r]["text"], "src_start": src_tokens[r]["start"],
                    "src_end": src_tokens[r]["end"],
                    "tgt": tgt_tokens[c]["text"], "tgt_start": tgt_tokens[c]["start"],
                    "tgt_end": tgt_tokens[c]["end"],
                    "score": round(float(sim[r, c]), 4),
                })
                break

    pairs.sort(key=lambda p: p["src_start"])
    pairs = pairs[:max_pairs]
    return {
        "pairs": pairs,
        "count": len(pairs),
        "source_tokens": len(src_tokens),
        "target_tokens": len(tgt_tokens),
        "threshold": threshold,
    }
