"""Writing workspace: rubric grading, correction, prompt bank, routes."""

import json

import pytest

from transcoder import teaching_store
from transcoder.writing import grade_writing, polish_writing
from transcoder.writing_prompts import PROMPTS, random_prompt

GRADE_REPLY = json.dumps({
    "scores": {"content": 8, "organization": 7, "grammar": 6, "vocabulary": 7, "coherence": 8},
    "issues": [
        {"type": "grammar", "span": "我昨天去学校学习", "advice": "时态和地点顺序可更自然"},
        {"type": "punctuation", "span": "很好。但是", "advice": "分句更清晰"},
    ],
    "comment": "内容完整，表达基本清楚，注意语法细节。",
    "level": "HSK 4",
})

POLISH_REPLY = json.dumps({
    "polished": "我昨天去学校学习汉语，收获很大。",
    "edits": [
        {"type": "grammar", "original": "昨天我去学校学习汉语很大收获", "revised": "我昨天去学校学习汉语，收获很大", "reason": "语序与标点"},
    ],
    "summary": "整体不错，语序需要调整。",
})


class FakeProvider:
    def __init__(self, reply):
        self.reply = reply

    def chat(self, messages, model=None, temperature=0.3, seed=None):
        return self.reply, {"prompt_tokens": 12, "completion_tokens": 8}

    def generate(self, prompt, model=None, temperature=0.3):
        return self.reply


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCODER_TEACHING_DIR", str(tmp_path))


def test_grade_parses_rubric():
    out = grade_writing(FakeProvider(GRADE_REPLY), "fake", "题目", "作文正文", length_hint="150 字")
    assert out["parse_ok"] is True
    assert set(out["scores"]) == {"content", "organization", "grammar", "vocabulary", "coherence"}
    assert out["overall"] == 7.2
    assert len(out["issues"]) == 2
    assert out["level"] == "HSK 4"
    assert "内容完整" in out["comment"]


def test_grade_handles_unparseable():
    out = grade_writing(FakeProvider("抱歉"), "fake", "题目", "作文")
    assert out["parse_ok"] is False
    assert out["overall"] is None


def test_polish_extracts_edits():
    out = polish_writing(FakeProvider(POLISH_REPLY), "fake", "题目", "原文")
    assert out["parse_ok"] is True
    assert out["polished"].startswith("我昨天")
    assert out["edits"][0]["type"] == "grammar"


def test_prompt_bank_shape():
    assert len(PROMPTS) >= 10
    for p in PROMPTS:
        assert p["title"] and p["prompt"] and p["level"]
    assert random_prompt()["id"]


class TestRoutes:
    @pytest.fixture
    def client(self):
        import transcoder.app as appmod

        return appmod.create_app({"TESTING": True}).test_client()

    def test_prompt_route(self, client):
        resp = client.get("/api/writing/prompt")
        assert resp.status_code == 200
        assert resp.get_json()["prompt"]["title"]

    def test_grade_route_persists(self, client, monkeypatch):
        import transcoder.writing as w

        monkeypatch.setattr(w, "grade_writing", lambda *a, **k: {
            "scores": {"content": 8.0}, "overall": 8.0, "issues": [], "comment": "好",
            "level": "HSK 3", "parse_ok": True, "model": "fake", "error": None,
        })
        resp = client.post("/api/writing/grade", json={
            "prompt": "题目", "essay": "作文内容", "author": "学生A",
        })
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["submission_id"]
        subs = teaching_store.list_submissions()
        assert subs[0]["author"] == "学生A"
        assert subs[0]["target_lang"] == "zh-cn"

    def test_grade_route_requires_essay(self, client):
        assert client.post("/api/writing/grade", json={"prompt": "p", "essay": ""}).status_code == 400


# --------------------------------------------------------------------------- #
# reading comprehension
# --------------------------------------------------------------------------- #
class TestReading:
    @pytest.fixture
    def client(self):
        import transcoder.app as appmod

        return appmod.create_app({"TESTING": True}).test_client()

    def test_random_hides_answers(self, client):
        payload = client.get("/api/reading/random", query_string={"exam": "cet4"}).get_json()["article"]
        assert payload["exam"] == "cet4"
        assert payload["passage"] and payload["questions"]
        assert all("answer" not in q for q in payload["questions"])

    def test_check_scores_correctly(self, client):
        from transcoder.reading_bank import ARTICLES

        article = ARTICLES[0]
        answers = [q["answer"] for q in article["questions"]]
        result = client.post("/api/reading/check", json={"id": article["id"], "answers": answers}).get_json()["result"]
        assert result["score"] == result["total"] == len(answers)
        assert result["percent"] == 100.0
        assert all(d["correct"] for d in result["details"])

    def test_check_marks_wrong(self, client):
        from transcoder.reading_bank import ARTICLES

        article = ARTICLES[0]
        answers = [(q["answer"] + 1) % len(q["options"]) for q in article["questions"]]
        result = client.post("/api/reading/check", json={"id": article["id"], "answers": answers}).get_json()["result"]
        assert result["score"] == 0
        assert all(not d["correct"] for d in result["details"])

    def test_exams_exist(self):
        from transcoder.reading_bank import ARTICLES

        exams = {a["exam"] for a in ARTICLES}
        assert {"cet4", "cet6", "kaoyan"} <= exams
        for a in ARTICLES:
            assert len(a["questions"]) >= 4
            for q in a["questions"]:
                assert 0 <= q["answer"] < len(q["options"])


class TestReadingLibrary:
    @pytest.fixture(autouse=True)
    def _store(self, tmp_path, monkeypatch):
        import transcoder.reading_store as rs

        monkeypatch.setattr(rs, "STORE_PATH", tmp_path / "reading.json")

    @pytest.fixture
    def client(self):
        import transcoder.app as appmod

        return appmod.create_app({"TESTING": True}).test_client()

    def test_catalog_lists_metadata(self, client):
        items = client.get("/api/reading/catalog").get_json()["items"]
        assert items
        assert all({"id", "exam", "year", "paper", "title"} <= set(i) for i in items)
        assert {"cet4", "jlpt", "hsk"} <= {i["exam"] for i in items}

    def test_import_then_select_by_year_and_check(self, client):
        article = {
            "exam": "cet4", "year": "2023", "paper": "2023年12月",
            "title": "Imported real paper", "passage": "Some passage text.",
            "questions": [
                {"q": "Q1?", "options": ["A", "B", "C", "D"], "answer": 2, "explain": "因为 A"},
                {"q": "Q2?", "options": ["A", "B"], "answer": 0, "explain": "因为 B"},
            ],
        }
        resp = client.post("/api/reading/import", json=article)
        assert resp.status_code == 200
        aid = resp.get_json()["article"]["id"]

        catalog = client.get("/api/reading/catalog").get_json()["items"]
        entry = next(i for i in catalog if i["id"] == aid)
        assert entry["year"] == "2023" and entry["paper"] == "2023年12月"
        assert entry["source"] == "user"

        picked = client.get("/api/reading/article", query_string={"id": aid}).get_json()["article"]
        assert all("answer" not in q for q in picked["questions"])

        result = client.post("/api/reading/check", json={"id": aid, "answers": [2, 0]}).get_json()["result"]
        assert result["score"] == 2 and result["percent"] == 100.0

        assert client.delete(f"/api/reading/import/{aid}").status_code == 200
        assert client.delete(f"/api/reading/import/{aid}").status_code == 404

    def test_random_filters_by_year(self, client):
        client.post("/api/reading/import", json={
            "exam": "kaoyan", "year": "2024", "paper": "英语一", "title": "T",
            "passage": "P", "questions": [{"q": "q", "options": ["a", "b"], "answer": 1}],
        })
        article = client.get("/api/reading/random",
                             query_string={"exam": "kaoyan", "year": "2024"}).get_json()["article"]
        assert article["year"] == "2024"

    def test_import_rejects_bad_payload(self, client):
        assert client.post("/api/reading/import", json={"exam": "cet4"}).status_code == 400
        bad = {"exam": "cet4", "title": "t", "passage": "p",
               "questions": [{"q": "q", "options": ["a"], "answer": 0}]}
        assert client.post("/api/reading/import", json=bad).status_code == 400


class TestRealExamParsers:
    def test_kaoyan_parser_extracts_texts_and_keys(self):
        from transcoder.real_exams import parse_kaoyan_paper

        md = """# Paper
Text 1
Passage one body.
21. Question one?
[A] alpha
[B] beta
[C] gamma
[D] delta
22. Question two?
[A] a
[B] b
[C] c
[D] d
23. Question three?
[A] a
[B] b
[C] c
[D] d
Text 2
Second passage.
26. Q?
[A] a
[B] b
[C] c
[D] d
27. Q2?
[A] a
[B] b
[C] c
[D] d
28. Q3?
[A] a
[B] b
[C] c
[D] d
"""
        answers = {"answers": {
            "reading-text-1": {"21": "C", "22": "A", "23": "D"},
            "reading-text-2": {"26": "B", "27": "B", "28": "A"},
        }}
        arts = parse_kaoyan_paper(md, answers, "2024", "英语一")
        assert len(arts) == 2
        assert arts[0]["title"] == "2024 英语一 Text 1"
        assert [q["answer"] for q in arts[0]["questions"]] == [2, 0, 3]
        assert arts[0]["passage"].strip() == "Passage one body."
        assert arts[1]["questions"][0]["answer"] == 1

    def test_cet_parser_marks_missing_key(self):
        from transcoder.real_exams import parse_cet_paper

        md = """Part III Reading Comprehension
### Section C
#### Passage One
Some passage text.
46. Q one?
A) aa
B) bb
C) cc
D) dd
47. Q two?
A) aa
B) bb
C) cc
D) dd
48. Q three?
A) aa
B) bb
C) cc
D) dd
"""
        arts = parse_cet_paper(md, "CET4", "2023.06", "1")
        assert len(arts) == 1
        assert arts[0]["has_key"] is False
        assert all(q["answer"] == -1 for q in arts[0]["questions"])


class TestContentLibrary:
    @pytest.fixture(autouse=True)
    def _isolated(self, tmp_path, monkeypatch):
        import transcoder.content_store as cs
        import transcoder.reading_store as rs

        monkeypatch.setattr(cs, "WRITING_PATH", tmp_path / "writing.json")
        monkeypatch.setattr(cs, "SPEECH_PATH", tmp_path / "speech.json")
        monkeypatch.setattr(rs, "STORE_PATH", tmp_path / "reading.json")

    @pytest.fixture
    def client(self):
        import transcoder.app as appmod

        return appmod.create_app({"TESTING": True}).test_client()

    def test_writing_and_speech_roundtrip(self, client):
        writing = {"kind": "writing", "items": [
            {"title": "My topic", "prompt": "Write 200 words.", "level": "CET-4", "lang": "en"},
        ]}
        speech = {"kind": "speech", "items": [
            {"text": "Practice makes perfect.", "level": "PETS-5", "lang": "en"},
        ]}
        assert client.post("/api/content/import/writing", json=writing).get_json()["imported"] == 1
        assert client.post("/api/content/import/speech", json=speech).get_json()["imported"] == 1

        exported_w = client.get("/api/content/export/writing").get_json()
        assert any(i["title"] == "My topic" for i in exported_w["items"])
        exported_s = client.get("/api/content/export/speech").get_json()
        assert any(i["text"] == "Practice makes perfect." for i in exported_s["items"])

    def test_reading_export_contains_answers(self, client):
        data = client.get("/api/content/export/reading").get_json()
        assert data["kind"] == "reading" and data["items"]
        assert all("answer" in q for it in data["items"] for q in it["questions"])

    def test_reading_import_skips_builtins(self, client):
        from transcoder.reading_bank import ARTICLES

        payload = {"kind": "reading", "items": [{
            "exam": ARTICLES[0]["exam"], "year": ARTICLES[0]["year"], "paper": ARTICLES[0]["paper"],
            "title": ARTICLES[0]["title"], "passage": ARTICLES[0]["passage"],
            "questions": ARTICLES[0]["questions"],
        }]}
        result = client.post("/api/content/import/reading", json=payload).get_json()
        assert result["imported"] == 0 and result["skipped"] == 1
