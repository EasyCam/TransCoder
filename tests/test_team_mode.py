# -*- coding: utf-8 -*-
"""P3 acceptance tests: team mode wiring (CLI + Flask), event flow, degradation."""

import json
from pathlib import Path

import pytest

from transcoder.agents import ReviewerAgent, TranslationOutput
from transcoder.orchestrator import EventLog, TeamOrchestrator


class FakeProvider:
    """Fake provider with the `chat` interface; records prompts."""

    def __init__(self, replies, fail_review=False):
        self.replies = list(replies)
        self.default_model = "fake-model"
        self.calls = []
        self.fail_review = fail_review

    def chat(self, messages, model=None, temperature=0.3, seed=None):
        self.calls.append(messages[-1]["content"][:50])
        if self.fail_review and "reviewer" in messages[0]["content"].lower():
            raise RuntimeError("reviewer down")
        text = self.replies.pop(0) if self.replies else "fallback reply"
        return text, {"prompt_tokens": 10, "completion_tokens": 5}

    def generate(self, prompt, model=None):
        text, _ = self.chat([{"role": "user", "content": prompt}])
        return text

    def is_available(self):
        return False  # force degradation when probed


class AvailFakeProvider(FakeProvider):
    def is_available(self):
        return True


REVIEW_JSON = (
    '{"scores": {"adequacy": 8, "terminology": 8, "fluency": 8, "culture": 7}, '
    '"issues": [{"type": "fluency", "span": "x", "advice": "y"}], "pass": true}'
)
BLOCKING_JSON = (
    '{"scores": {"adequacy": 6, "terminology": 5, "fluency": 8, "culture": 7}, '
    '"issues": [{"type": "accuracy", "span": "term", "advice": "wrong term"}], "pass": false}'
)


def build(tmp_path, reviewer_provider, max_rounds=3):
    from transcoder.team_setup import build_team

    translator = FakeProvider(["T1", "T2", "T3"])
    ev = EventLog(path=tmp_path / "events.jsonl")
    orch = build_team(
        translator_provider=translator,
        reviewer_provider=reviewer_provider,
        max_rounds=max_rounds,
        event_log=ev,
        seed=42,
    )
    # Replace translator agent's provider object keep; build_team wraps it.
    orch.event_log = ev
    return orch


class TestTeamProtocol:
    def test_pass_on_first_round(self, tmp_path):
        reviewer = AvailFakeProvider([REVIEW_JSON])
        orch = build(tmp_path, reviewer)
        result = orch.run("hello", "en", "zh-cn")
        assert result.final_translation == "T1"
        assert len(result.rounds) == 1
        assert result.rounds[0]["review"]["passed"] is True
        assert result.degraded is False
        assert result.tokens["translator_out"] > 0

    def test_rewrite_then_accept(self, tmp_path):
        reviewer = AvailFakeProvider([BLOCKING_JSON, REVIEW_JSON])
        orch = build(tmp_path, reviewer)
        result = orch.run("hello", "en", "zh-cn")
        assert len(result.rounds) == 2
        assert result.rounds[0]["review"]["passed"] is False
        assert result.rounds[1]["translation"] == "T2"  # rewrite consumed second reply
        assert result.final_review["passed"] is True

    def test_max_rounds_then_accept(self, tmp_path):
        reviewer = AvailFakeProvider([BLOCKING_JSON, BLOCKING_JSON, BLOCKING_JSON])
        orch = build(tmp_path, reviewer, max_rounds=2)
        result = orch.run("hello", "en", "zh-cn")
        assert len(result.rounds) == 2  # 1st review, rewrite, 2nd review; max reached
        assert result.final_review["passed"] is False

    def test_review_json_fenced_text(self, tmp_path):
        reviewer = AvailFakeProvider([f"```json\n{REVIEW_JSON}\n```"])
        orch = build(tmp_path, reviewer)
        result = orch.run("hi", "en", "zh")
        assert result.rounds[0]["review"]["parse_ok"] is True

    def test_no_reviewer_degrades(self, tmp_path):
        orch = build(tmp_path, None)
        result = orch.run("hi", "en", "zh", dry=True)
        assert result.degraded is True
        assert result.degraded_reason == "no reviewer configured"

    def test_unavailable_reviewer_degrades(self, tmp_path):
        reviewer = FakeProvider([])  # is_available() -> False
        orch = build(tmp_path, reviewer)
        result = orch.run("hi", "en", "zh", dry=True)
        assert result.degraded is True
        assert "unreachable" in (result.degraded_reason or "")

    def test_events_written_and_redacted(self, tmp_path):
        reviewer = AvailFakeProvider([REVIEW_JSON])
        orch = build(tmp_path, reviewer)
        orch.run("hello", "en", "zh-cn")
        events = orch.event_log.read_events()
        kinds = [e["event"] for e in events]
        assert "run.start" in kinds and "translator.translate" in kinds
        assert "reviewer.review" in kinds and "run.end" in kinds
        for e in events:
            assert json.dumps(e).count("api_key") == 0


class TestTeamSetupHelpers:
    def test_provider_for_endpoint_unknown(self):
        from transcoder.team_setup import provider_for_endpoint

        with pytest.raises(ValueError):
            provider_for_endpoint("definitely-not-configured-xyz", endpoints={})

    def test_build_team_requires_translator(self):
        from transcoder.team_setup import build_team

        with pytest.raises(ValueError):
            build_team(translator_provider=None)


class TestCLI:
    def test_parser_accepts_team_flags(self):
        from transcoder.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            ["cli", "-i", "in.txt", "-t", "en", "--mode", "team",
             "--translator-endpoint", "ollama-local", "--reviewer-endpoint", "deepseek",
             "--translator-model", "qwen3:0.6b", "--reviewer-model", "deepseek-chat",
             "--team-rounds", "2", "--seed", "7", "--dry"]
        )
        assert args.run_mode == "team"
        assert args.reviewer_endpoint == "deepseek"
        assert args.team_rounds == 2
        assert args.dry is True
        assert args.seed == 7

    def test_parser_legacy_backcompat(self):
        from transcoder.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["cli", "-i", "in.txt", "-t", "en", "--mode-type", "reflect"])
        assert args.mode_type == "reflect"
        assert args.run_mode is None

    def test_run_team_cli_dry_writes_events(self, tmp_path, monkeypatch, capsys):
        """--dry end-to-end through run_team_cli: no model call, events written."""
        import transcoder.cli as cli
        from transcoder.endpoints import EndpointConfig

        ep = EndpointConfig(name="fake-ep", base_url="http://127.0.0.1:9/v1", api_key=None, models=["m1"])
        dead_provider = AvailFakeProvider([])

        class Buildable:
            endpoint_name = "fake-ep"

        def fake_provider_for(name, model=None, endpoints=None, timeout=60.0):
            if name == "fake-ep":
                return dead_provider
            raise ValueError("unknown")

        import transcoder.team_setup as ts

        monkeypatch.setattr(ts, "provider_for_endpoint", fake_provider_for)
        event_path = tmp_path / "dry_events.jsonl"
        args = cli.create_parser().parse_args(
            ["-q", "cli", "-i", "x.txt", "-t", "en", "--mode", "team", "--translator-endpoint", "fake-ep",
             "--reviewer-endpoint", "fake-ep", "--dry", "--events", str(event_path)]
        )
        # fake-ep base_url is unreachable -> is_available False -> degraded chain expected
        rc = cli.run_team_cli(args, "hello", ["en"])
        assert rc == 0
        assert event_path.exists()
        events = [json.loads(l) for l in event_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert any(e["event"] == "run.start" for e in events)

    def test_run_team_cli_dry_with_reviewer_reachable(self, tmp_path, monkeypatch):
        """--dry with a 'reachable' fake reviewer: dry plan events, no translate call."""
        import time as _time

        import transcoder.cli as cli

        calls = {"n": 0}

        class ReachableProvider(FakeProvider):
            def is_available(self):
                return True

            def chat(self, *a, **k):  # must never be called in --dry
                calls["n"] += 1
                raise AssertionError("dry mode must not call the model")

        reviewer = ReachableProvider([])
        translator = ReachableProvider([])
        import transcoder.team_setup as ts

        monkeypatch.setattr(ts, "provider_for_endpoint",
                            lambda name, model=None, endpoints=None, timeout=60.0: (
                                translator if name == "t-ep" else reviewer))
        event_path = tmp_path / "dry_events2.jsonl"
        args = cli.create_parser().parse_args(
            ["-q", "cli", "-i", "x.txt", "-t", "en", "--mode", "team", "--translator-endpoint", "t-ep",
             "--reviewer-endpoint", "t-ep", "--team-rounds", "1", "--dry", "--events", str(event_path)]
        )
        rc = cli.run_team_cli(args, "hello", ["en"])
        assert rc == 0
        assert calls["n"] == 0
        events = [json.loads(l) for l in event_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        kinds = [e["event"] for e in events]
        assert "dry.plan" in kinds
        assert "translator.translate" not in kinds


class TestFlask:
    @pytest.fixture
    def client(self, monkeypatch):
        """Flask test client with the team route monkeypatched to a fake orchestrator."""
        monkeypatch.setenv("LLM_PROVIDER", "ollama")

        import transcoder.app as appmod

        flask_app = appmod.create_app({"TESTING": True})
        return flask_app.test_client()

    def test_team_endpoints_safe(self, client):
        import re

        resp = client.get("/api/team/endpoints")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["endpoints"], "expected at least one locally configured endpoint"
        for ep in payload["endpoints"]:
            assert "api_key" not in ep
            assert not ep.get("api_key")
            assert re.fullmatch(r"(|<hidden:\d+ chars>)", ep.get("masked_key") or "")
            assert ep.get("has_api_key") in (True, False)

    def test_team_translate_requires_text(self, client):
        resp = client.post("/api/translate/team", json={"source_text": "", "target_lang": "en",
                                                        "translator_endpoint": "x"})
        assert resp.status_code == 400

    def test_team_translate_requires_translator_endpoint(self, client):
        resp = client.post("/api/translate/team", json={"source_text": "hi", "target_lang": "en"})
        assert resp.status_code == 400

    def test_team_translate_unknown_endpoint_400(self, client):
        resp = client.post("/api/translate/team", json={
            "source_text": "hi", "target_lang": "en", "translator_endpoint": "no-such-endpoint-xyz"})
        assert resp.status_code == 400

    def test_team_translate_dry(self, client, monkeypatch, tmp_path):
        """Full team route with a fake orchestrator (dry) — verifies response shape."""
        import transcoder.team_setup as ts

        class DummyResult:
            def __init__(self):
                from transcoder.orchestrator import TeamResult

                self._r = TeamResult(final_translation="X", degraded=False, run_id="abc123")

            def to_dict(self):
                return self._r.to_dict()

        def fake_build(**kwargs):
            return Orch

        class Orch:
            def run(self, *a, **k):
                return DummyResult()._r

        monkeypatch.setattr(ts, "build_team_from_endpoints", lambda **kw: Orch())
        # the route imported build_team_from_endpoints when registering... ensure patch applies
        resp = client.post("/api/translate/team", json={
            "source_text": "hi there", "target_lang": "en",
            "translator_endpoint": "whatever", "dry": True, "team_rounds": 1})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["team"]["final_translation"] == "X"
        assert body["team"]["run_id"] == "abc123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# --------------------------------------------------------------------------- #
# reviewer reliability: strict retry + cloud-first / local-fallback
# --------------------------------------------------------------------------- #
GOOD_REVIEW = (
    '{"scores": {"adequacy": 9, "terminology": 9, "fluency": 9, "culture": 9}, '
    '"issues": [], "pass": true}'
)


class ScriptedProvider:
    def __init__(self, reply, record=None):
        self.reply = reply
        self.calls = 0
        self.record = record if record is not None else []

    def chat(self, messages, model=None, temperature=0.3, seed=None):
        self.calls += 1
        self.record.append({"messages": messages, "temperature": temperature})
        return self.reply, {"prompt_tokens": 5, "completion_tokens": 5}

    def generate(self, prompt, model=None, temperature=0.3):
        self.calls += 1
        return self.reply

    def is_available(self):
        return True


def _team(modes, fallback=None, events_path=None):
    from transcoder.orchestrator import EventLog
    from transcoder.team_setup import build_team

    translator = ScriptedProvider("translated text")
    reviewer = ScriptedProvider("I cannot review this.")
    fb = ScriptedProvider(GOOD_REVIEW) if fallback else None
    team = build_team(
        translator_provider=translator, translator_model="t",
        reviewer_provider=reviewer, reviewer_model="r-bad",
        reviewer_fallback_provider=fb, reviewer_fallback_model="r-local" if fb else None,
        max_rounds=2, event_log=EventLog(path=events_path) if events_path else EventLog(),
        seed=1,
    )
    return team, reviewer, fb


def test_unparseable_review_is_not_a_pass(tmp_path):
    log = tmp_path / "events.jsonl"
    team, reviewer, _ = _team(None, fallback=False, events_path=log)
    result = team.run("source", "zh-cn", "en")
    assert result.review_failed is True
    assert reviewer.calls >= 2, "expected a strict retry"
    events = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    kinds = [e["event"] for e in events]
    assert "reviewer.retry" in kinds
    decision = [e for e in events if e["event"] == "orchestrator.decision"][-1]
    assert "WITHOUT review" in decision["payload"]["reason"]


def test_strict_retry_uses_low_temperature_and_hint(tmp_path):
    from transcoder.agents import ReviewerAgent

    provider = ScriptedProvider("still not json")
    agent = ReviewerAgent(provider, "r")
    out = agent.review("src", "tgt", "zh-cn", "en", strict=True)
    assert out.parse_ok is False
    call = provider.record[-1]
    assert call["temperature"] == 0.0
    assert "STRICT MODE" in call["messages"][0]["content"]


def test_local_fallback_reviewer_is_used(tmp_path):
    log = tmp_path / "events.jsonl"
    team, reviewer, fb = _team(None, fallback=True, events_path=log)
    result = team.run("source", "zh-cn", "en")
    assert result.review_failed is False
    assert result.final_review and result.final_review["parse_ok"] is True
    assert reviewer.calls == 2 and fb.calls >= 1
    events = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    kinds = [e["event"] for e in events]
    assert "reviewer.fallback" in kinds
    fb_event = [e for e in events if e["event"] == "reviewer.fallback"][0]
    assert fb_event["payload"]["to"] == "r-local"
