"""
TransCoder LLM Provider Abstraction Layer

Supports multiple LLM backends: Ollama (default), OpenAI, and more.
"""

import os
from abc import ABC, abstractmethod
from typing import List, Optional

_proxy_vars = ["ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"]
_saved_proxy = {}

for var in _proxy_vars:
    if var in os.environ:
        _saved_proxy[var] = os.environ[var]
        del os.environ[var]

try:
    import ollama
except ImportError:
    ollama = None

for var, value in _saved_proxy.items():
    os.environ[var] = value

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


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
    """Ollama LLM provider (default, local)."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        default_model: str = "qwen3:0.6b",
        use_proxy: bool = False,
        proxy_url: Optional[str] = None,
    ):
        self.host = host
        self.default_model = default_model
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url

        if ollama:
            if use_proxy and proxy_url:
                for var in _proxy_vars:
                    if var in os.environ:
                        del os.environ[var]
                if proxy_url.startswith("socks://"):
                    proxy_url = proxy_url.replace("socks://", "socks5://")
                os.environ["HTTPS_PROXY"] = proxy_url
                os.environ["HTTP_PROXY"] = proxy_url
            elif not use_proxy:
                for var in _proxy_vars:
                    if var in os.environ:
                        del os.environ[var]

            ollama.host = host

    def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """Generate text using Ollama."""
        if ollama is None:
            raise ImportError("ollama package not installed. Run: pip install ollama")

        model = model or self.default_model
        response = ollama.generate(model=model, prompt=prompt)
        return response.get("response", "").strip()

    def get_available_models(self) -> List[str]:
        """Get list of available Ollama models."""
        if ollama is None:
            return []
        try:
            models = ollama.list()
            return [m["model"] for m in models.get("models", [])]
        except Exception:
            return []

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        if ollama is None:
            return False
        try:
            ollama.list()
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


def create_provider(provider_type: str = "ollama", model: Optional[str] = None, **kwargs) -> LLMProvider:
    """
    Create an LLM provider instance.

    Args:
        provider_type: "ollama" or "openai"
        model: Default model to use
        **kwargs: Additional provider-specific arguments
            For Ollama: host, use_proxy, proxy_url
            For OpenAI: api_key, base_url

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

    else:
        raise ValueError(f"Unknown provider type: {provider_type}. Use 'ollama' or 'openai'.")
