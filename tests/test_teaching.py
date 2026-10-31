"""Tests for the teaching layer: human grading/polishing, annotations, telemetry."""

import json

import pytest

from transcoder import teaching_store
from transcoder.human_workbench import grade, polish

FIXED_REVIEW = json.dumps({
    "scores": {"adequacy": 8, "terminology": 7, "fluency": 9, "culture": 8},
    "issues": [{"type": "terminology", "span": "LLM", "advice": "use 大语言模型"}],
    "pass": False,
})

FIXED_POLISH = json.dumps({
    "polished": "The cat sat on the mat.",
    "edits": [{"type": "grammar", "original": "cat sit", "revised": "cat sat", "reason": "tense"}],
    "summary": "Fix verb tense.",
})


class FakeProvider:
    def __init__(self, reply: str):
        self.reply = reply

    def chat(self, messages, model=None, temperature=0.3, seed=None):
        return self.reply, {"prompt_tokens": 10, "completion_tokens": 5}

    def generate(self, prompt, model=None, temperature=0.3):
        return self.reply

    def get_available_models(self):
        return ["fake"]


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCODER_TEACHING_DIR", str(tmp_path))
    return tmp_path


# --------------------------------------------------------------------------- #
# pure modules
# --------------------------------------------------------------------------- #
def test_grade_parses_scores_and_issues():
    out = grade(FakeProvider(FIXED_REVIEW), "fake", "源文", "LLM translation", target_lang="en")
    assert out["scores"] == {"adequacy": 8.0, "terminology": 7.0, "fluency": 9.0, "culture": 8.0}
    assert out["overall"] == 8.0
    assert out["passed"] is False
    assert out["parse_ok"] is True
    assert len(out["issues"]) == 1 and out["issues"][0]["type"] == "terminology"


def test_grade_handles_unparseable_reply():
    out = grade(FakeProvider("I cannot help"), "fake", "源文", "译文", target_lang="en")
    assert out["parse_ok"] is False
    assert out["scores"] == {}
    assert out["overall"] is None


def test_polish_extracts_edits():
    out = polish(FakeProvider(FIXED_POLISH), "fake", "源文", "The cat sit on the mat.", target_lang="en")
    assert out["parse_ok"] is True
    assert out["polished"] == "The cat sat on the mat."
    assert out["edits"][0]["type"] == "grammar"
    assert out["edits"][0]["revised"] == "cat sat"


def test_polish_unknown_edit_type_normalized():
    reply = json.dumps({
        "polished": "x",
        "edits": [{"type": "punctuation", "original": "a", "revised": "b", "reason": "r"}],
    })
    out = polish(FakeProvider(reply), "fake", "s", "t", target_lang="en")
    assert out["edits"][0]["type"] == "other"


def test_polish_parse_failure_is_reported():
    out = polish(FakeProvider("not json at all"), "fake", "s", "t", target_lang="en")
    assert out["parse_ok"] is False
    assert out["error"]
    assert out["polished"] == ""


# --------------------------------------------------------------------------- #
# store
# --------------------------------------------------------------------------- #
def test_submission_annotation_roundtrip():
    sub = teaching_store.add_submission(
        source_text="源文", translation="译文", source_lang="zh-cn", target_lang="en",
        grade={"overall": 8.0, "scores": {"adequacy": 8.0}}, author="张三",
    )
    assert sub["id"]
    assert teaching_store.list_submissions()[0]["translation"] == "译文"

    ann = teaching_store.add_annotation(sub["id"], quote="译", note="用词不当", kind="terminology")
    rows = teaching_store.list_annotations(sub["id"])
    assert len(rows) == 1 and rows[0]["note"] == "用词不当"
    assert teaching_store.delete_annotation(ann["id"]) is True
    assert teaching_store.list_annotations(sub["id"]) == []


def test_telemetry_summary_aggregates():
    teaching_store.record_event("page.view", {})
    teaching_store.record_event("translate.done", {"ok": True})
    teaching_store.record_event("translate.done", {"ok": False})
    teaching_store.add_submission("s", "t", target_lang="en", grade={"overall": 7.0})
    teaching_store.add_submission("s2", "t2", target_lang="en", grade={"overall": 9.0})
    summary = teaching_store.telemetry_summary(days=1)
    assert summary["events_total"] == 3
    assert summary["events_by_type"]["translate.done"] == 2
    assert summary["submissions"] == 2
    assert summary["graded"] == 2
    assert summary["avg_overall_score"] == 8.0


# --------------------------------------------------------------------------- #
# Flask routes
# --------------------------------------------------------------------------- #
class TestRoutes:
    @pytest.fixture
    def client(self):
        import transcoder.app as appmod

        return appmod.create_app({"TESTING": True}).test_client()

    def test_grade_route_persists_submission(self, client, monkeypatch):
        import transcoder.human_workbench as hw

        monkeypatch.setattr(hw, "grade", lambda *a, **k: {
            "scores": {"adequacy": 8.0}, "overall": 8.0, "issues": [], "passed": True,
            "parse_ok": True, "model": "fake", "error": None,
        })
        resp = client.post("/api/human/grade", json={
            "source_text": "源文", "translation": "译文", "target_lang": "en", "author": "李四",
        })
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["success"] is True
        assert payload["grade"]["overall"] == 8.0
        assert payload["submission_id"]
        subs = teaching_store.list_submissions()
        assert subs[0]["author"] == "李四"

    def test_grade_route_requires_text(self, client):
        resp = client.post("/api/human/grade", json={"source_text": "", "translation": "x"})
        assert resp.status_code == 400

    def test_annotation_routes(self, client):
        sub = teaching_store.add_submission("s", "t")
        resp = client.post("/api/human/annotations", json={
            "submission_id": sub["id"], "quote": "t", "note": "n", "kind": "grammar",
        })
        assert resp.status_code == 200
        ann_id = resp.get_json()["annotation"]["id"]

        listed = client.get("/api/human/annotations", query_string={"submission_id": sub["id"]}).get_json()
        assert len(listed["annotations"]) == 1

        assert client.delete(f"/api/human/annotations/{ann_id}").status_code == 200
        assert client.delete(f"/api/human/annotations/{ann_id}").status_code == 404

    def test_telemetry_routes(self, client):
        assert client.post("/api/telemetry", json={"event": "page.view"}).status_code == 200
        assert client.post("/api/telemetry", json={}).status_code == 400
        summary = client.get("/api/telemetry/summary").get_json()["summary"]
        assert summary["events_total"] >= 1

    def test_polish_route(self, client, monkeypatch):
        import transcoder.human_workbench as hw

        monkeypatch.setattr(hw, "polish", lambda *a, **k: {
            "polished": "fixed", "edits": [], "summary": "", "parse_ok": True,
            "model": "fake", "error": None,
        })
        resp = client.post("/api/human/polish", json={
            "source_text": "s", "translation": "t", "target_lang": "en",
        })
        assert resp.status_code == 200
        assert resp.get_json()["polish"]["polished"] == "fixed"


# --------------------------------------------------------------------------- #
# automatic alignment
# --------------------------------------------------------------------------- #
def test_align_texts_matches_semantic_pairs():
    import numpy as np

    from transcoder.aligner import align_texts

    vocab = {"猫": [1.0, 0.0, 0.0], "cat": [0.98, 0.02, 0.0],
             "狗": [0.0, 1.0, 0.0], "dog": [0.02, 0.98, 0.0]}

    def embed(texts):
        arr = np.array([vocab.get(t, [0.0, 0.0, 1.0]) for t in texts], dtype=float)
        arr /= np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12
        return arr

    res = align_texts("猫 狗", "cat dog", embed=embed)
    pairs = {p["src"]: p["tgt"] for p in res["pairs"]}
    assert pairs.get("猫") == "cat"
    assert pairs.get("狗") == "dog"
    for p in res["pairs"]:
        assert p["src_end"] > p["src_start"]
        assert p["tgt_end"] > p["tgt_start"]
