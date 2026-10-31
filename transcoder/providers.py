"""
TransCoder LLM Provider Abstraction Layer

Every backend speaks the OpenAI chat-completions wire format (one transport
for all): Ollama via its native ``/v1`` surface at a configurable local
address, OpenAI-compatible cloud endpoints, and locally configured endpoints
from :mod:`transcoder.endpoints`. The legacy native-``ollama``-package path
was removed (it used a different protocol and proxy-env juggling).
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def _is_local_url(base_url: Optional[str]) -> bool:
    """True when the endpoint is loopback (never route through a proxy)."""
    b = (base_url or "").lower()
    return ("127.0.0.1" in b) or ("localhost" in b) or ("[::1]" in b)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """Generate text from prompt."""
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Get list of available models."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available."""
        pass


class OllamaProvider(LLMProvider):
    """Ollama over the OpenAI-compatible ``/v1`` API at a configurable address.

    The address is fully configurable (``host``), e.g. the local default
    ``http://localhost:11434`` -> ``http://localhost:11434/v1`` or any remote
    ollama host. Loopback traffic bypasses system proxies via
    ``httpx.Client(trust_env=False)`` so a local ollama works even when global
    proxy env vars are set. ``use_proxy``/``proxy_url`` are accepted for
    signature compatibility but no longer needed for local endpoints.
    """

    def __init__(
        self,
        host: str = "http://localhost:11434",
        default_model: str = "qwen3:0.6b",
        use_proxy: bool = False,
        proxy_url: Optional[str] = None,
    ):
        base = (host or "http://localhost:11434").rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        self.host = base  # OpenAI-compatible base_url
        self.default_model = default_model
        self._client = None

    @property
    def client(self):
        if OpenAI is None:
            raise ImportError("openai package not installed. Run: pip install openai")

        if self._client is None:
            import httpx

            client_kwargs: Dict[str, Any] = {
                "api_key": os.getenv("OLLAMA_API_KEY") or "EMPTY",
                "base_url": self.host,
                "timeout": 60.0,
            }
            if _is_local_url(self.host):
                client_kwargs["http_client"] = httpx.Client(trust_env=False, timeout=60.0)
            self._client = OpenAI(**client_kwargs)
        return self._client

    def chat(self, messages: List[dict], model: Optional[str] = None, temperature: float = 0.3,
             max_tokens: Optional[int] = None, seed: Optional[int] = None):
        """OpenAI-format chat completions. Returns ``(text, usage_dict)``."""
        kwargs: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if seed is not None:
            kwargs["seed"] = seed
        response = self.client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        usage_dict = None
        if usage is not None:
            usage_dict = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            }
        return text, usage_dict

    def generate(self, prompt: str, model: Optional[str] = None, temperature: float = 0.3) -> str:
        """Generate text using Ollama (OpenAI-format transport)."""
        text, _ = self.chat([{"role": "user", "content": prompt}], model=model, temperature=temperature)
        return text.strip()

    def stream_generate(self, prompt: str, model: Optional[str] = None, temperature: float = 0.3):
        """Yield text deltas as they arrive (OpenAI-format streaming)."""
        stream = self.client.chat.completions.create(
            model=model or self.default_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            text = getattr(delta, "content", None) if delta is not None else None
            if text:
                yield text

    def get_available_models(self) -> List[str]:
        """Get list of available Ollama models (OpenAI-format /v1/models)."""
        try:
            models_response = self.client.models.list()
            return sorted([m.id for m in models_response.data])
        except Exception:
            return []

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(
        self, api_key: Optional[str] = None, base_url: Optional[str] = None, default_model: str = "gpt-4o-mini"
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.default_model = default_model
        self._client = None

    @property
    def client(self):
        """Lazy-loaded OpenAI client."""
        if OpenAI is None:
            raise ImportError("openai package not installed. Run: pip install openai")

        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key required. Set OPENAI_API_KEY environment variable or pass api_key parameter."
                )

            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url

            self._client = OpenAI(**client_kwargs)

        return self._client

    def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """Generate text using OpenAI API."""
        model = model or self.default_model

        response = self.client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}], temperature=0.3
        )

        return response.choices[0].message.content.strip()

    def get_available_models(self) -> List[str]:
        """Get list of available OpenAI models."""
        if not self.api_key:
            return []

        try:
            models_response = self.client.models.list()
            return sorted([m.id for m in models_response.data if "gpt" in m.id.lower()])
        except Exception:
            return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]

    def is_available(self) -> bool:
        """Check if OpenAI API is available."""
        if not self.api_key:
            return False
        try:
            self.client.models.list()
            return True
        except Exception:
            return False


class ConfiguredEndpointProvider(LLMProvider):
    """Provider bound to one locally configured endpoint (from endpoints.py).

    OpenAI-compatible (`chat.completions`); the endpoint's api_key lives only
    in memory (EndpointConfig holds it; serialization is always masked).
    """

    def __init__(self, endpoint: "EndpointConfig", default_model: Optional[str] = None, timeout: float = 60.0):
        self.endpoint = endpoint
        self.default_model = default_model or endpoint.default_model
        self.timeout = timeout
        self._client = None

    @property
    def client(self):
        if OpenAI is None:
            raise ImportError("openai package not installed. Run: pip install openai")
        if self._client is None:
            client_kwargs: Dict[str, Any] = {
                "api_key": self.endpoint.api_key or "EMPTY", "timeout": self.timeout
            }
            if self.endpoint.base_url:
                client_kwargs["base_url"] = self.endpoint.base_url
            if _is_local_url(self.endpoint.base_url):
                # Loopback endpoints never go through system proxies (works
                # even with ALL_PROXY/HTTP_PROXY pointing at a global proxy).
                import httpx

                client_kwargs["http_client"] = httpx.Client(trust_env=False, timeout=self.timeout)
            self._client = OpenAI(**client_kwargs)
        return self._client

    def chat(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
    ):
        """Chat-completions with usage. Returns ``(text, usage_dict)``.

        ``usage_dict`` carries the vendor's own prompt/completion token counts
        when the endpoint reports them; agents fall back to o200k counting when
        it is None.
        """
        model = model or self.default_model
        kwargs = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if seed is not None:
            kwargs["seed"] = seed
        response = self.client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        usage_dict = None
        if usage is not None:
            usage_dict = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            }
        return text, usage_dict

    def generate(self, prompt: str, model: Optional[str] = None, temperature: float = 0.3, max_tokens: Optional[int] = None):
        model = model or self.default_model
        response = self.client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}], temperature=temperature, max_tokens=max_tokens
        )
        return response.choices[0].message.content or ""

    def stream_generate(self, prompt: str, model: Optional[str] = None, temperature: float = 0.3):
        """Yield text deltas as they arrive (OpenAI-format streaming)."""
        stream = self.client.chat.completions.create(
            model=model or self.default_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            text = getattr(delta, "content", None) if delta is not None else None
            if text:
                yield text

    def get_available_models(self, raise_on_error: bool = False) -> List[str]:
        try:
            models_response = self.client.models.list()
            return sorted([m.id for m in models_response.data])
        except Exception:
            if raise_on_error:
                raise
            return list(self.endpoint.models)

    def is_available(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception:
            return False


def _default_results_dir():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "RESULTS"


def probe_endpoint(endpoint, timeout: float = 12.0, chat_ping: bool = False, ping_model: Optional[str] = None) -> dict:
    """Probe one endpoint: reachability + latency + model list (+ tiny chat).

    Returns a redacted, JSON-safe dict (never contains the api_key).
    """
    from transcoder.endpoints import redact

    record = dict(endpoint.to_safe_dict())
    record["probe"] = {"reachable": False}

    client = None
    try:
        if OpenAI is None:
            raise ImportError("openai package not installed")
        client_kwargs = {
            "api_key": endpoint.api_key or "EMPTY",
            "base_url": endpoint.base_url,
            "timeout": timeout,
            "max_retries": 0,
        }
        if _is_local_url(endpoint.base_url):
            import httpx

            client_kwargs["http_client"] = httpx.Client(trust_env=False, timeout=timeout)
        client = OpenAI(**client_kwargs)
    except Exception as e:
        record["probe"]["error"] = redact(str(e))
        return record

    # 1) GET /models
    t0 = time.time()
    try:
        models_response = client.models.list()
        latency_ms = round((time.time() - t0) * 1000, 1)
        ids = sorted([m.id for m in models_response.data])
        record["probe"] = {"reachable": True, "latency_ms": latency_ms, "http_status": 200, "models": ids}
        if endpoint.models and not ids:
            record["probe"]["configured_models"] = list(endpoint.models)
    except Exception as e:
        record["probe"] = {
            "reachable": False,
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "error": redact(f"{type(e).__name__}: {e}"),
        }
        if chat_ping:
            return record

    # 2) Optional minimal chat completion (auth + full path verification).
    if chat_ping:
        model = ping_model or endpoint.default_model
        if not model:
            record["probe"]["chat_ping"] = {"ok": False, "error": "no model id available"}
        else:
            t1 = time.time()
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=8,
                    temperature=0.0,
                )
                sample = (resp.choices[0].message.content or "").strip()[:24]
                record["probe"]["chat_ping"] = {
                    "ok": True,
                    "model": model,
                    "latency_ms": round((time.time() - t1) * 1000, 1),
                    "sample": redact(sample),
                }
            except Exception as e:
                lat = round((time.time() - t1) * 1000, 1)
                # 401/403 with reachable network still proves reachability.
                status = getattr(getattr(e, "status_code", None), "value", None) or getattr(e, "status_code", None)
                record["probe"]["chat_ping"] = {
                    "ok": False,
                    "model": model,
                    "latency_ms": lat,
                    "http_status": status if isinstance(status, int) else None,
                    "error": redact(f"{type(e).__name__}: {e}"),
                }
    return record


def create_provider(provider_type: str = "ollama", model: Optional[str] = None, **kwargs) -> LLMProvider:
    """
    Create an LLM provider instance.

    Args:
        provider_type: "ollama" (OpenAI-format transport at a configurable
            local address), "openai", or "openai-compat" (alias: "configured")
            which resolves a locally configured endpoint by name — any
            OpenAI-compatible backend, local or remote.
        model: Default model to use
        **kwargs: Additional provider-specific arguments
            For Ollama: host (default http://localhost:11434, `/v1` is
                auto-appended), use_proxy, proxy_url (compat, ignored for
                loopback)
            For OpenAI: api_key, base_url
            For openai-compat: endpoint_name (e.g. "deepseek", "ollama-local"), or
                an explicit `endpoint: EndpointConfig` instance.

    Returns:
        LLMProvider instance
    """
    provider_type = provider_type.lower()

    if provider_type == "ollama":
        return OllamaProvider(
            host=kwargs.get("host", "http://localhost:11434"),
            default_model=model or "qwen3:0.6b",
            use_proxy=kwargs.get("use_proxy", False),
            proxy_url=kwargs.get("proxy_url"),
        )

    elif provider_type == "openai":
        return OpenAIProvider(
            api_key=kwargs.get("api_key"), base_url=kwargs.get("base_url"), default_model=model or "gpt-4o-mini"
        )

    elif provider_type in ("openai-compat", "configured"):
        endpoint = kwargs.get("endpoint")
        if endpoint is None:
            from transcoder.endpoints import discover_endpoints

            endpoint_name = kwargs.get("endpoint_name")
            if not endpoint_name:
                raise ValueError("openai-compat provider requires `endpoint_name` or `endpoint`")
            endpoints = discover_endpoints()
            if endpoint_name not in endpoints:
                raise ValueError(f"endpoint not found in local configs: {endpoint_name}")
            endpoint = endpoints[endpoint_name]
        return ConfiguredEndpointProvider(
            endpoint, default_model=model, timeout=kwargs.get("timeout", 60.0)
        )

    else:
        raise ValueError(f"Unknown provider type: {provider_type}. Use 'ollama', 'openai' or 'openai-compat'.")
