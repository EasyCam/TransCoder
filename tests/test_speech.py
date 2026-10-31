"""Read-aloud scoring: character alignment + speech routes."""

import io

import pytest

from transcoder.speech import score_reading


def test_exact_match_scores_full():
    r = score_reading("今天天气很好。", "今天天气很好。")
    assert r["accuracy"] == 100.0
    assert r["completeness"] == 100.0
    assert r["score"] == 10.0
    assert all(c["status"] == "correct" for c in r["chars"])


def test_missing_characters_are_marked():
    r = score_reading("今天天气很好", "今天天气好")
    missing = [c["text"] for c in r["chars"] if c["status"] == "missing"]
    assert missing == ["很"]
    assert r["completeness"] < 100.0


def test_wrong_character_is_marked():
    r = score_reading("我喜欢看书", "我喜欢砍书")
    wrong = [c for c in r["chars"] if c["status"] == "wrong"]
    assert wrong and wrong[0]["text"] == "看"


def test_punctuation_ignored():
    r = score_reading("你好，世界！", "你好世界")
    assert r["accuracy"] == 100.0
    assert len(r["chars"]) == 4


class TestRoutes:
    @pytest.fixture
    def client(self):
        import transcoder.app as appmod

        return appmod.create_app({"TESTING": True}).test_client()

    def test_tts_route(self, client, monkeypatch):
        import transcoder.speech as speech

        monkeypatch.setattr(speech, "synthesize", lambda *a, **k: {"file": "tts_" + "a" * 20 + ".m4a", "voice": "Tingting"})
        resp = client.post("/api/speech/tts", json={"text": "你好"})
        assert resp.status_code == 200
        assert resp.get_json()["url"].startswith("/api/speech/audio/")

    def test_tts_requires_text(self, client):
        assert client.post("/api/speech/tts", json={"text": ""}).status_code == 400

    def test_score_route(self, client, monkeypatch):
        import transcoder.speech as speech

        monkeypatch.setattr(speech, "transcribe", lambda *a, **k: {
            "text": "今天天气很好", "duration": 2.1, "language": "zh",
        })
        data = {
            "target_text": "今天天气很好",
            "file": (io.BytesIO(b"fake-audio"), "rec.webm"),
        }
        resp = client.post("/api/speech/score", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        result = resp.get_json()["result"]
        assert result["accuracy"] == 100.0
        assert result["duration"] == 2.1

    def test_score_requires_file(self, client):
        resp = client.post("/api/speech/score", data={"target_text": "你好"},
                           content_type="multipart/form-data")
        assert resp.status_code == 400


def test_traditional_transcript_matches_simplified_target():
    r = score_reading("今天天气很好，我们一起去公园散步", "今天天氣很好,我們一起去公園散步")
    assert r["accuracy"] == 100.0
    assert r["wrong"] == 0
