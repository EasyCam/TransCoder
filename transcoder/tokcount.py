"""
True token counting with tiktoken o200k (P4).

Replaces the legacy estimate `word_count + char_count // 4`
(PERFORMANCE_METRICS_SUMMARY.md documents the old convention) with a real
tokenizer. o200k_base is used as the *uniform cross-model* accounting layer
for the paper: it is not every vendor's native tokenizer (DeepSeek/others
tokenize differently), so vendor invoices may differ slightly; the uniform
o200k count is what all cross-group comparisons use, and it is what makes
"online tokens <= 25% of G0" well-defined.

Fallback: if tiktoken is unavailable, raises at import of TokCount (tests and
orchestrator require it); a `estimator_word_count` legacy helper is retained
for the P4 comparison report (old vs new convention).
"""

import threading
from typing import Optional

_lock = threading.Lock()
_encoder = None


def _get_encoder():
    global _encoder
    with _lock:
        if _encoder is None:
            import tiktoken

            _encoder = tiktoken.get_encoding("o200k_base")
        return _encoder


def count_tokens(text: str) -> int:
    """Token count of text under o200k_base."""
    if text is None or text == "":
        return 0
    return len(_get_encoder().encode(text))


def count_chat(messages) -> int:
    """Token count for a list of {"role", "content"} chat messages.

    Convention (openai-style): each message adds 4 overhead tokens, and the
    conversation adds 3. Matches the tiktoken cookbook's non-chatml counting.
    """
    total = 3
    for m in messages or []:
        total += 4 + count_tokens(m.get("content", ""))
    return total


def estimate_tokens_legacy(text: str) -> int:
    """The legacy estimator kept ONLY for the P4 old-vs-new comparison table."""
    if text is None:
        return 0
    return len(text.split()) + len(text) // 4


class TokCount:
    """Structural wrapper used by agents/events; exposes method-style counting."""

    def __init__(self, encoding: str = "o200k_base", override_encoding: Optional[str] = None):
        self.encoding_name = encoding
        self._override = override_encoding
        self._enc = None

    @property
    def enc(self):
        if self._enc is None:
            import tiktoken

            self._enc = tiktoken.get_encoding(self.encoding_name)
        return self._enc

    def count(self, text: Optional[str]) -> int:
        return len(self.enc.encode(text)) if text else 0

    def method(self) -> str:
        return f"tiktoken/{self.encoding_name}"