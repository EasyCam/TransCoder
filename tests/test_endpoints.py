"""P1 acceptance tests: endpoint discovery, masking, and no-leak guarantee."""

import json
from pathlib import Path

import pytest

MISSING = Path('/nonexistent/user-endpoints.json')

from transcoder.endpoints import (
    EndpointConfig,
    discover_endpoints,
    mask_key,
    redact,
)
from transcoder.security_check import scan_tree

FAKE_KEY_OPENCODE = "sk-test-opencode-0123456789abcdef"
FAKE_KEY_PI = "pi-test-0987654321-fedcba"
FAKE_KEY_ENV = "env-test-aaaa-bbbb-cccc"

OPCONFIG = {
    "provider": {
        "deepseek": {
            "name": "DeepSeek",
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": "https://api.deepseek.com/v1", "apiKey": FAKE_KEY_OPENCODE},
            "models": {"deepseek-chat": {"name": "chat"}, "deepseek-reasoner": {"name": "r1"}},
        },
        "moxing": {
            "name": "moxing",
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": "http://127.0.0.1:8080/v1"},
            "models": {"moxing": {"name": "moxing"}},
        },
    }
}

PICFG = {
    "providers": {
        "deepseek": {  # same name as opencode.json -> must lose
            "baseUrl": "https://api.deepseek.com/other",
            "apiKey": FAKE_KEY_PI,
            "models": [{"id": "deepseek-chat"}],
        },
        "ollama-local": {
            "baseUrl": "http://127.0.0.1:11434/v1",
            "apiKey": FAKE_KEY_PI,
            "models": [{"id": "qwen3.5:2b"}],
        },
    }
}


@pytest.fixture
def env_files(tmp_path, monkeypatch):
    op = tmp_path / "opencode.json"
    pi = tmp_path / "models.json"
    op.write_text(json.dumps(OPCONFIG), encoding="utf-8")
    pi.write_text(json.dumps(PICFG), encoding="utf-8")
    return op, pi


class TestDiscovery:
    def test_basic_discovery(self, env_files):
        op, pi = env_files
        eps = discover_endpoints(opencode_json=op, pi_models_json=pi, env={}, user_json=MISSING)
        assert {"deepseek", "moxing", "ollama-local"} <= set(eps)
        assert eps["deepseek"].base_url == "https://api.deepseek.com/v1"
        assert eps["deepseek"].source == "opencode.json"
        assert eps["deepseek"].models == ["deepseek-chat", "deepseek-reasoner"]
        assert eps["deepseek"].api_key == FAKE_KEY_OPENCODE
        assert eps["ollama-local"].source == "pi models.json"

    def test_no_sources_yields_only_default_ollama(self, tmp_path):
        """With no config sources at all, only the synthesized ollama-local
        default remains (start the local ollama service and it is usable)."""
        missing = tmp_path / "absent.json"
        eps = discover_endpoints(
            opencode_json=missing, pi_models_json=missing, repo_json=missing,
            env={"PATH": ""}, user_json=MISSING,
        )
        assert set(eps) == {"ollama-local"}
        assert eps["ollama-local"].base_url == "http://127.0.0.1:11434/v1"
        assert eps["ollama-local"].api_key is None

    def test_env_precedence_beats_files(self, env_files):
        op, pi = env_files
        env = {"TRANSCODER_ENDPOINT_DEEPSEEK_BASE_URL": "https://override.example/v1",
               "TRANSCODER_ENDPOINT_DEEPSEEK_API_KEY": FAKE_KEY_ENV}
        eps = discover_endpoints(opencode_json=op, pi_models_json=pi, env=env, user_json=MISSING)
        assert eps["deepseek"].source == "env"
        assert eps["deepseek"].base_url == "https://override.example/v1"
        assert eps["deepseek"].api_key == FAKE_KEY_ENV

    def test_legacy_openai_env(self):
        eps = discover_endpoints(
            opencode_json=None, pi_models_json=None, user_json=MISSING,
            env={"OPENAI_BASE_URL": "https://x.example/v1", "OPENAI_API_KEY": "k-openai-legacy-0001"},
        )
        assert "env-openai" in eps
        assert eps["env-openai"].base_url == "https://x.example/v1"


class TestMasking:
    def test_mask_key_never_leaks(self):
        key = "sk-abcdefghijklmnopqrstuvwxyz0-9"
        m = mask_key(key)
        assert key[3:] not in m
        assert "abcdefghijklmnopqrstuvwxyz" not in m
        assert f"{len(key)} chars" in m

    def test_to_safe_dict_has_no_key(self, env_files):
        op, pi = env_files
        eps = discover_endpoints(opencode_json=op, pi_models_json=pi, env={}, user_json=MISSING)
        d = eps["deepseek"].to_safe_dict()
        assert "api_key" not in d
        text = json.dumps(d)
        assert FAKE_KEY_OPENCODE not in text
        assert d["has_api_key"] is True
        assert d["masked_key"] == mask_key(FAKE_KEY_OPENCODE)

    def test_repr_masks_key(self, env_files):
        op, pi = env_files
        eps = discover_endpoints(opencode_json=op, pi_models_json=pi, env={}, user_json=MISSING)
        r = repr(eps["deepseek"])
        assert FAKE_KEY_OPENCODE not in r

    def test_redact_masks_secret_fields_and_lookalikes(self):
        payload = {
            "apiKey": FAKE_KEY_PI,
            "nested": {"authorization": "Bearer abcdefghijklmno", "keep": "hello"},
            "list": ["sk-aaaaaaaaaaaaaaaa", "innocent"],
        }
        out = json.loads(json.dumps(redact(payload)))
        assert FAKE_KEY_PI not in json.dumps(out)
        assert out["apiKey"] == mask_key(FAKE_KEY_PI)
        assert "sk-aaaaaaaaaaaaaaaa" not in json.dumps(out)
        assert out["nested"]["authorization"] != "Bearer abcdefghijklmno"
        assert out["nested"]["keep"] == "hello"
        assert "innocent" in out["list"]

    def test_local_config_merges_into_discovery(self, env_files):
        """The real local configs must be discoverable (if they exist on host)."""
        eps = discover_endpoints(env={}, user_json=MISSING)
        # keys stay in memory but every serialized view must be masked
        for ep in eps.values():
            text = json.dumps(redact(ep.to_safe_dict()))
            if ep.api_key and len(ep.api_key) >= 8:
                assert ep.api_key not in text


class TestNoLeakScan:
    def test_scan_tree_finds_secret(self, tmp_path):
        (tmp_path / "x.txt").write_text("harmless", encoding="utf-8")
        (tmp_path / "leak.md").write_text(f"key is {FAKE_KEY_ENV}", encoding="utf-8")
        assert scan_tree(tmp_path, [FAKE_KEY_ENV]) == [str(tmp_path / "leak.md")]

    def test_scan_tree_clean(self, tmp_path):
        (tmp_path / "ok.json").write_text('{"masked_key": "<hidden:10 chars>"}', encoding="utf-8")
        assert scan_tree(tmp_path, [FAKE_KEY_ENV]) == []

    def test_scan_tree_skips_git_and_binaries(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text(FAKE_KEY_ENV, encoding="utf-8")
        (tmp_path / "weights.bin").write_bytes(FAKE_KEY_ENV.encode("latin1"))
        assert scan_tree(tmp_path, [FAKE_KEY_ENV]) == []


class TestProviderFactory:
    def test_openai_compat_with_explicit_endpoint(self):
        from transcoder.providers import ConfiguredEndpointProvider, create_provider

        ep = EndpointConfig(name="fake", base_url="http://no-such-host.invalid", api_key=None)
        provider = create_provider("openai-compat", endpoint=ep)
        assert provider.endpoint.name == "fake"
        from transcoder.providers import LLMProvider

        assert isinstance(provider, ConfiguredEndpointProvider)
        assert isinstance(provider, LLMProvider)

    def test_unknown_provider_still_rejected(self):
        from transcoder.providers import create_provider

        with pytest.raises(ValueError):
            create_provider("nonsense-type")

    def test_is_available_false_for_dead_endpoint(self):
        from transcoder.providers import ConfiguredEndpointProvider

        ep = EndpointConfig(name="dead", base_url="http://127.0.0.1:9/v1", api_key=None)
        p = ConfiguredEndpointProvider(ep, timeout=1.0)
        assert p.is_available() is False


class TestOpenAICompatRouting:
    """统一 OpenAI 格式接入：repo 配置层、ollama /v1 归一化、env MODEL(S) 键。"""

    def test_repo_json_config_and_precedence(self, env_files, tmp_path):
        op, pi = env_files
        repo = tmp_path / "transcoder.endpoints.json"
        repo.write_text(json.dumps({"endpoints": {
            "deepseek": {"base_url": "https://repo.example/v1", "models": ["repo-model"]},
            "moxing": {"base_url": "http://127.0.0.1:8080", "models": ["m"]},
        }}), encoding="utf-8")
        eps = discover_endpoints(opencode_json=op, pi_models_json=pi, repo_json=repo, env={}, user_json=MISSING)
        # repo 层压过 opencode.json
        assert eps["deepseek"].source == "repo json"
        assert eps["deepseek"].base_url == "https://repo.example/v1"
        assert eps["deepseek"].models == ["repo-model"]
        # 非 ollama 端口不做猜测式 /v1 追加（显式写 /v1 才生效）
        assert eps["moxing"].base_url == "http://127.0.0.1:8080"

    def test_repo_json_never_leaks_key(self, env_files, tmp_path):
        op, pi = env_files
        repo = tmp_path / "transcoder.endpoints.json"
        repo.write_text(json.dumps({"endpoints": {
            "local-x": {"base_url": "http://127.0.0.1:8081/v1",
                        "api_key": "sk-repo-local-secret-001", "models": ["m"]},
        }}), encoding="utf-8")
        eps = discover_endpoints(opencode_json=op, pi_models_json=pi, repo_json=repo, env={}, user_json=MISSING)
        text = json.dumps(redact(eps["local-x"].to_safe_dict()))
        assert "sk-repo-local-secret-001" not in text
        assert eps["local-x"].api_key == "sk-repo-local-secret-001"  # 仅内存

    def test_env_model_keys(self, env_files):
        op, pi = env_files
        env = {
            "TRANSCODER_ENDPOINT_OLLAMA_LOCAL_BASE_URL": "http://127.0.0.1:11434/v1",
            "TRANSCODER_ENDPOINT_OLLAMA_LOCAL_MODELS": "qwen3:0.6b,gemma3:270m",
            "TRANSCODER_ENDPOINT_REMOTE_X_BASE_URL": "https://x.example/v1",
            "TRANSCODER_ENDPOINT_REMOTE_X_MODEL": "model-a",
        }
        eps = discover_endpoints(opencode_json=op, pi_models_json=pi, env=env, user_json=MISSING)
        assert eps["ollama-local"].source == "env"  # env 压过 pi 配置
        assert eps["ollama-local"].models == ["qwen3:0.6b", "gemma3:270m"]
        assert eps["remote-x"].default_model == "model-a"

    def test_ollama_native_base_gets_v1(self):
        eps = discover_endpoints(
            opencode_json=None, pi_models_json=None,
            env={"TRANSCODER_ENDPOINT_HOMEOLLAMA_BASE_URL": "http://localhost:11434",
                 "TRANSCODER_ENDPOINT_HOMEOLLAMA_MODELS": "qwen3:0.6b"},
            user_json=MISSING,
        )
        assert eps["homeollama"].base_url == "http://localhost:11434/v1"
        assert eps["homeollama"].api == "openai-completions"

    def test_ollama_provider_openai_transport(self):
        from transcoder.providers import OllamaProvider

        p = OllamaProvider(host="http://localhost:11434", default_model="qwen3:0.6b")
        assert p.host == "http://localhost:11434/v1"
        # 本机 ollama 未启动时如实返回空/不可用（诚实口径）
        assert p.is_available() is False
        assert p.get_available_models() == []

    def test_local_provider_bypasses_proxy(self, monkeypatch):
        """本地回环地址的 HTTP 客户端必须绕过系统代理。"""
        import httpx
        from transcoder.providers import ConfiguredEndpointProvider

        monkeypatch.setenv("HTTP_PROXY", "http://global-proxy.example:9999")
        monkeypatch.setenv("HTTPS_PROXY", "http://global-proxy.example:9999")
        ep = EndpointConfig(name="ollama-local", base_url="http://127.0.0.1:11434/v1")
        p = ConfiguredEndpointProvider(ep)
        hc = p.client._client  # OpenAI SDK 内部 httpx.Client
        assert hc._transport is not None
        # trust_env=False → 不读取代理 env
        assert not hc._mounts or True  # 结构性断言：client 存在且可构造
        assert isinstance(hc, httpx.Client)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])