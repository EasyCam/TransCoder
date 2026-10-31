"""Minimal-edit guard: reject rewrites that change text no issue quotes."""
from transcoder.agents import ReviewIssue
from transcoder.orchestrator import is_broad_rewrite

OLD = ("To hold and fill it is not as good as to let it be; to measure and sharpen it is not "
       "to be able to sustain it; gold and jade fill the hall, yet no one can guard them.")

def test_small_edit_with_short_span_is_allowed():
    new = OLD.replace("to let it be", "to stop")
    issues = [ReviewIssue(type="terminology", span="to let it be", advice="use 'to stop'")]
    assert not is_broad_rewrite(OLD, new, issues)

def test_whole_text_rewrite_with_short_span_is_rejected():
    new = ("Hold rather than overfill; sharpen rather than preserve; wealth and honour invite "
           "ruin; withdraw when the work is done.")
    issues = [ReviewIssue(type="terminology", span="to let it be", advice="use 'to stop'")]
    assert is_broad_rewrite(OLD, new, issues)

def test_broad_span_justifies_broad_edit():
    issues = [ReviewIssue(type="accuracy", span=OLD[:150], advice="restructure")]
    assert not is_broad_rewrite(OLD, "Completely different text about vessels and jade.", issues)

def test_no_issues_and_identical_text_is_not_rejected():
    assert not is_broad_rewrite(OLD, OLD, [])
