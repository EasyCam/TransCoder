"""Regression tests for reviewer-reply validation and the pass policy.

The paper claims that a review which does not parse can never be counted as a
pass. The pass *policy* is a separate decision: by default the rubric scores
decide (the scores are the contract), and the model's own ``pass`` flag is
advisory; ``policy="model"`` restores the old behaviour.
"""
from transcoder.agents import validate_review_json

FULL = ('{"pass": true, "scores": {"adequacy": 9, "terminology": 9, "fluency": 9, '
        '"culture": 9}, "issues": []}')


def test_full_rubric_passes():
    r = validate_review_json(FULL)
    assert r.parse_ok and r.passed


def test_missing_rubric_cannot_pass():
    r = validate_review_json('{"pass": true, "issues": []}')
    assert not r.parse_ok and not r.passed


def test_empty_object_cannot_pass():
    r = validate_review_json("{}")
    assert not r.parse_ok and not r.passed


def test_scores_policy_ignores_model_flag():
    r = validate_review_json(FULL.replace('"pass": true', '"pass": "false"'))
    assert r.parse_ok and r.passed  # scores are the contract under the default policy


def test_model_policy_respects_flag():
    r = validate_review_json(FULL.replace('"pass": true', '"pass": "false"'), policy="model")
    assert r.parse_ok and not r.passed


def test_threshold_changes_verdict():
    raw = FULL.replace('"adequacy": 9', '"adequacy": 6.5')
    assert validate_review_json(raw, threshold=6.0).passed
    assert not validate_review_json(raw, threshold=7.0).passed


def test_low_score_cannot_pass():
    r = validate_review_json(FULL.replace('"adequacy": 9', '"adequacy": 3'))
    assert r.parse_ok and not r.passed


def test_blocking_issue_cannot_pass():
    r = validate_review_json(FULL.replace(
        '"issues": []', '"issues": [{"type": "accuracy", "span": "x", "advice": "y"}]'))
    assert r.parse_ok and not r.passed


def test_empty_span_issue_does_not_block():
    raw = FULL.replace('"issues": []', '"issues": [{"type": "accuracy", "span": "", "advice": "x"}]')
    r = validate_review_json(raw)
    assert r.parse_ok and r.passed


def test_quoted_span_issue_blocks():
    raw = FULL.replace('"issues": []',
                       '"issues": [{"type": "accuracy", "span": "the good is like water", "advice": "x"}]')
    r = validate_review_json(raw)
    assert r.parse_ok and not r.passed
