"""Span-local rewrite: only quoted spans may change."""
from transcoder.agents import ReviewIssue, TranslatorAgent


class Fake(TranslatorAgent):
    def __init__(self, reply):
        self.reply = reply
        self.model = "fake"

    def _call(self, messages, seed=None):
        return {"text": self.reply, "tokens_in": 1, "tokens_out": 1, "latency_s": 0.0, "error": None}


TEXT = ("To hold and fill it is not as good as to let it be; gold and jade fill the hall, "
        "yet no one can guard them.")


def test_replaces_only_the_span():
    agent = Fake("to stop")
    out = agent.rewrite_spans("en", TEXT, [ReviewIssue(type="terminology", span="to let it be", advice="use 'to stop'")])
    assert out.translation == TEXT.replace("to let it be", "to stop")
    assert out.meta["applied"] and not out.meta["skipped"]


def test_missing_span_is_left_alone():
    agent = Fake("to stop")
    out = agent.rewrite_spans("en", TEXT, [ReviewIssue(type="terminology", span="not in the text", advice="x")])
    assert out.translation == TEXT
    assert out.meta["skipped"][0]["why"] == "not found"


def test_overlong_replacement_is_rejected():
    agent = Fake("a replacement clause that is far too long for the span it is meant to replace")
    out = agent.rewrite_spans("en", TEXT, [ReviewIssue(type="accuracy", span="gold and jade", advice="x")])
    assert out.translation == TEXT
    assert out.meta["skipped"][0]["why"] == "too_long"


def test_multiline_replacement_is_rejected():
    agent = Fake("line one\nline two")
    out = agent.rewrite_spans("en", TEXT, [ReviewIssue(type="accuracy", span="gold and jade", advice="x")])
    assert out.translation == TEXT
    assert out.meta["skipped"][0]["why"] == "multi_line"


def test_no_issues_returns_text():
    out = Fake("x").rewrite_spans("en", TEXT, [])
    assert out.translation == TEXT
