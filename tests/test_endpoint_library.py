"""User endpoint library: import from JSON, manual entry, masking, permissions."""

import json
import os

import pytest

from transcoder import endpoints


@pytest.fixture(autouse=True)
def user_store(tmp_path, monkeypatch):
    path = tmp_path / "endpoints.json"
    monkeypatch.setattr(endpoints, "USER_ENDPOINTS_JSON", path)
    return path


def test_upsert_persists_masked_and_0600(user_store):
    endpoints.upsert_user_endpoint("mine", "https://example.com/v1", "sk-test-123456", ["m1", "m2"])
    data = json.loads(user_store.read_text(encoding="utf-8"))
    assert data["endpoints"]["mine"]["api_key"] == "sk-test-123456"
    assert data["endpoints"]["mine"]["models"] == ["m1", "m2"]
    assert oct(os.stat(user_store).st_mode & 0o777) == "0o600"

    eps = endpoints.discover_endpoints(user_json=user_store)
    ep = eps["mine"]
    assert ep.source == "user json"
    safe = json.dumps(ep.to_safe_dict())
    assert "sk-test-123456" not in safe
    assert "<hidden:" in safe


def test_empty_key_keeps_existing(user_store):
    endpoints.upsert_user_endpoint("mine", "https://example.com/v1", "sk-keep-me-123", ["m1"])
    endpoints.upsert_user_endpoint("mine", "https://example.com/v2", None, ["m2"])
    data = json.loads(user_store.read_text(encoding="utf-8"))
    assert data["endpoints"]["mine"]["api_key"] == "sk-keep-me-123"
    assert data["endpoints"]["mine"]["base_url"] == "https://example.com/v2"


def test_delete(user_store):
    endpoints.upsert_user_endpoint("mine", "https://example.com/v1", None, [])
    assert endpoints.delete_user_endpoint("mine") is True
    assert endpoints.delete_user_endpoint("mine") is False


def test_import_copies_discovered_endpoint(user_store):
    ep = endpoints.EndpointConfig(
        name="disc", base_url="https://disc.example/v1", api_key="sk-disc-key-1",
        models=["m"], source="opencode.json",
    )
    endpoints.import_endpoint("disc", {"disc": ep})
    eps = endpoints.discover_endpoints(user_json=user_store)
    assert eps["disc"].source == "user json"
    assert eps["disc"].api_key == "sk-disc-key-1"


def test_required_fields(user_store):
    with pytest.raises(ValueError):
        endpoints.upsert_user_endpoint("", "https://x/v1")
    with pytest.raises(ValueError):
        endpoints.upsert_user_endpoint("x", "")


class TestRoutes:
    @pytest.fixture
    def client(self):
        import transcoder.app as appmod

        return appmod.create_app({"TESTING": True}).test_client()

    def test_manual_add_then_listed_masked(self, client):
        resp = client.post("/api/endpoints/manual", json={
            "name": "ui-endpoint", "base_url": "https://ui.example/v1",
            "api_key": "sk-ui-secret-987", "models": "a, b",
        })
        assert resp.status_code == 200
        listed = client.get("/api/endpoints").get_json()["endpoints"]
        entry = next(e for e in listed if e["name"] == "ui-endpoint")
        assert entry["editable"] is True
        assert "api_key" not in entry
        assert "sk-ui-secret-987" not in json.dumps(listed)

    def test_import_unknown_is_400(self, client):
        resp = client.post("/api/endpoints/import", json={"name": "no-such-endpoint"})
        assert resp.status_code == 400

    def test_delete_manual(self, client):
        client.post("/api/endpoints/manual", json={
            "name": "tmp-endpoint", "base_url": "https://tmp.example/v1", "models": [],
        })
        assert client.delete("/api/endpoints/manual/tmp-endpoint").status_code == 200
        assert client.delete("/api/endpoints/manual/tmp-endpoint").status_code == 404
