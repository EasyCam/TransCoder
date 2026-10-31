"""
Configured endpoint discovery (read-only).

Discovers locally configured OpenAI-compatible endpoints (one wire format for
every backend, ollama included via its native ``/v1`` surface) from:

- environment variables (highest precedence):
  ``TRANSCODER_ENDPOINT_<NAME>_BASE_URL`` + ``_API_KEY`` + ``_MODEL`` /
  ``_MODELS`` (comma list), and legacy ``OPENAI_BASE_URL`` / ``OPENAI_API_KEY``;
- ``<repo>/transcoder.endpoints.json`` (key ``endpoints``; see
  ``transcoder.endpoints.json.example``): repo-scoped endpoints, e.g. a local
  ollama at a configurable address;
- ``~/.config/opencode/opencode.json`` (key ``provider``): e.g. deepseek /
  cycleuser-halogen / cycleuser-strata / moxing / tencent;
- ``~/.pi/agent/models.json`` (key ``providers``): ollama-cloud / ollama-local /
  cycleuser-halogen / cycleuser-strata.

Ollama integration: any entry whose base URL points at ollama's native port
(``:11434``) or that declares ``api: ollama`` is normalized to
``<host>/v1`` so OpenAI-format clients work unchanged. When nothing defines a
local ollama, a default ``ollama-local`` entry at ``http://127.0.0.1:11434/v1``
is synthesized — start the ollama service and the models configured in it are
usable immediately (models list refreshes from GET /models at call time).

SECRET RULE (this module is the only place keys are ever read):
API keys are read into memory, are never written to disk or logs by this
module, and every serialized form (repr / dict / JSON) goes through
:meth:`EndpointConfig.to_dict` or :func:`redact`, which masks them.
A CI/acceptance check (`python -m transcoder.security_check` and
tests/test_endpoints.py) greps the tree for plaintext keys.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Field names whose values must never be serialized in clear text.
SECRET_FIELD_NAMES = frozenset(
    {"api_key", "apiKey", "api-key", "apikey", "token", "secret", "password", "authorization", "auth"}
)

# Strings that look like bearer/API keys when they appear in free text.
_KEY_LOOKALIKE_PATTERNS = [
    re.compile(r"sk[-_][A-Za-z0-9]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{8,}", re.I),
]

OPENCODE_CONFIG_PATH = Path.home() / ".config" / "opencode" / "opencode.json"
PI_MODELS_PATH = Path.home() / ".pi" / "agent" / "models.json"
# Repo-local endpoint config (this repo): <repo>/transcoder.endpoints.json
REPO_ENDPOINTS_JSON = Path(__file__).resolve().parent.parent / "transcoder.endpoints.json"
# Endpoints added/imported from the UI live OUTSIDE the repo (keys on disk,
# mode 0600), so the repo tree never contains plaintext secrets.
USER_ENDPOINTS_JSON = Path(
    os.getenv("TRANSCODER_USER_ENDPOINTS", str(Path.home() / ".config" / "transcoder" / "endpoints.json"))
).expanduser()

# Precedence order, highest first. When the same endpoint name appears in
# several sources the higher-precedence entry wins (and its source is noted):
# env > repo json > opencode.json > pi models.json > synthesized default
# (the local ollama default is constructed in :func:`discover_endpoints`
# because EndpointConfig is defined below).
_SOURCE_PRECEDENCE = {
    "env": 5,
    "repo json": 4,
    "user json": 3,
    "opencode.json": 2,
    "pi models.json": 1,
    "default (ollama)": 0,
}


def mask_key(key: Optional[str]) -> str:
    """Mask representation of an API key. Never returns any key characters."""
    if not key:
        return ""
    return f"<hidden:{len(key)} chars>"


def redact(obj: Any) -> Any:
    """Recursively strip secret-looking values from any structure.

    - Mapping keys in :data:`SECRET_FIELD_NAMES` have their values masked;
    - anywhere else, strings matching key lookalike patterns (sk-…, Bearer …)
      are masked before serialization.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in SECRET_FIELD_NAMES:
                out[k] = mask_key(str(v)) if v else ""
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        text = obj
        for pat in _KEY_LOOKALIKE_PATTERNS:
            text = pat.sub(lambda m: "<redacted:%d chars>" % len(m.group(0)), text)
        return text
    return obj


def _looks_like_key(text: str) -> bool:
    return any(pat.search(text) for pat in _KEY_LOOKALIKE_PATTERNS)


@dataclass
class EndpointConfig:
    """One locally configured, OpenAI-compatible endpoint (key kept in memory)."""

    name: str
    base_url: str
    api_key: Optional[str] = None
    api: str = "openai-completions"
    models: List[str] = field(default_factory=list)
    source: str = "unknown"  # "env" | "opencode.json" | "pi models.json"
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def default_model(self) -> Optional[str]:
        return self.models[0] if self.models else None

    @property
    def key_repr(self) -> str:
        return mask_key(self.api_key)

    def to_safe_dict(self) -> Dict[str, Any]:
        """Serialize WITHOUT the key. Safe for RESULTS/ JSON files."""
        return {
            "name": self.name,
            "base_url": self.base_url,
            "api": self.api,
            "models": list(self.models),
            "source": self.source,
            "has_api_key": bool(self.api_key),
            "masked_key": mask_key(self.api_key),
        }

    def __repr__(self) -> str:  # pragma: no cover - defensive masking
        return "EndpointConfig(name=%r, base_url=%r, api_key=%s, source=%r)" % (
            self.name,
            self.base_url,
            mask_key(self.api_key),
            self.source,
        )


def _parse_opencode(path: Path) -> Dict[str, EndpointConfig]:
    """Parse opencode.json ``provider`` section."""
    out: Dict[str, EndpointConfig] = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for name, entry in (data.get("provider") or {}).items():
        options = (entry or {}).get("options") or {}
        base_url = options.get("baseURL") or ""
        if not base_url:
            continue
        models = sorted((entry.get("models") or {}).keys())
        out[name] = EndpointConfig(
            name=name,
            base_url=base_url,
            api_key=options.get("apiKey") or None,
            api="openai-completions",
            models=models,
            source="opencode.json",
            extra={"npm": entry.get("npm")},
        )
    return out


def _parse_pi(path: Path) -> Dict[str, EndpointConfig]:
    """Parse pi agent models.json ``providers`` section."""
    out: Dict[str, EndpointConfig] = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for name, entry in (data.get("providers") or {}).items():
        base_url = (entry or {}).get("baseUrl") or ""
        if not base_url:
            continue
        model_ids = []
        for m in entry.get("models") or []:
            mid = m.get("id") if isinstance(m, dict) else str(m)
            if mid:
                model_ids.append(mid)
        out[name] = EndpointConfig(
            name=name,
            base_url=base_url,
            api_key=entry.get("apiKey") or None,
            api=entry.get("api") or "openai-completions",
            models=model_ids,
            source="pi models.json",
            extra={"compat": entry.get("compat") or {}},
        )
    return out


def _parse_repo(path: Path) -> Dict[str, EndpointConfig]:
    """Parse <repo>/transcoder.endpoints.json ``endpoints`` section.

    Schema (see transcoder.endpoints.json.example):

        {"endpoints": {"ollama-local": {"base_url": "http://127.0.0.1:11434/v1",
                                        "models": ["qwen3:0.6b"]}}}

    ``api_key`` optional (local endpoints need none); if present it stays in
    memory and is masked in every serialized view.
    """
    out: Dict[str, EndpointConfig] = {}
    if not path.exists():
        return out
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return out
    for name, entry in (data.get("endpoints") or {}).items():
        base_url = (entry or {}).get("base_url") or ""
        if not base_url:
            continue
        models = [str(m) for m in entry.get("models") or []]
        out[name] = EndpointConfig(
            name=name,
            base_url=base_url,
            api_key=entry.get("api_key") or None,
            api=entry.get("api") or "openai-completions",
            models=models,
            source="repo json",
        )
    return out


def _parse_env(env: Optional[Dict[str, str]] = None) -> Dict[str, EndpointConfig]:
    """Env overrides: TRANSCODER_ENDPOINT_<NAME>_BASE_URL/_API_KEY/_MODEL(S)."""
    environ = dict(os.environ if env is None else env)
    out: Dict[str, EndpointConfig] = {}

    prefix = "TRANSCODER_ENDPOINT_"
    names: Dict[str, Dict[str, str]] = {}
    for k, v in environ.items():
        if not k.startswith(prefix) or not v:
            continue
        rest = k[len(prefix):]
        if rest.endswith("_BASE_URL"):
            names.setdefault(rest[: -len("_BASE_URL")], {})["base_url"] = v
        elif rest.endswith("_API_KEY"):
            names.setdefault(rest[: -len("_API_KEY")], {})["api_key"] = v
        elif rest.endswith("_MODELS"):
            names.setdefault(rest[: -len("_MODELS")], {})["models"] = v
        elif rest.endswith("_MODEL"):
            names.setdefault(rest[: -len("_MODEL")], {})["model"] = v

    for name, kv in names.items():
        if "base_url" in kv:
            if kv.get("models"):
                models = [s.strip() for s in kv["models"].split(",") if s.strip()]
            elif kv.get("model"):
                models = [kv["model"]]
            else:
                models = []
            # 环境变量段名下划线 → 端点名连字符（与 pi/opencode 配置命名一致：
            # TRANSCODER_ENDPOINT_OLLAMA_LOCAL_* ↔ "ollama-local"）
            out[name.lower().replace("_", "-")] = EndpointConfig(
                name=name.lower().replace("_", "-"),
                base_url=kv["base_url"],
                api_key=kv.get("api_key"),
                models=models,
                source="env",
            )

    # Legacy single openai-compatible endpoint.
    base = environ.get("OPENAI_BASE_URL")
    if base:
        out["env-openai"] = EndpointConfig(
            name="env-openai",
            base_url=base,
            api_key=environ.get("OPENAI_API_KEY"),
            source="env",
        )
    return out


def _normalize_ollama(ep: EndpointConfig) -> EndpointConfig:
    """Route ollama through its OpenAI-compatible ``/v1`` surface.

    One wire format for everything: an ollama-style base URL (native port or
    ``api: ollama``) gets ``/v1`` appended so OpenAI-format clients work
    everywhere, including locally configured models.
    """
    base = ep.base_url.rstrip("/")
    ollamaish = (ep.api or "").lower() == "ollama" or base.endswith(":11434")
    if ollamaish and not base.endswith("/v1"):
        return EndpointConfig(
            name=ep.name, base_url=base + "/v1", api_key=ep.api_key,
            api="openai-completions", models=list(ep.models),
            source=ep.source, extra=dict(ep.extra),
        )
    return ep



def _parse_user(path: Optional[Path] = None) -> Dict[str, EndpointConfig]:
    """Parse the user endpoint library written from the settings UI."""
    p = Path(path) if path is not None else USER_ENDPOINTS_JSON
    out = _parse_repo(p)
    for ep in out.values():
        ep.source = "user json"
    return out


def load_user_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Read the raw user endpoint file (``{"endpoints": {...}}``)."""
    p = Path(path) if path is not None else USER_ENDPOINTS_JSON
    if not p.exists():
        return {"endpoints": {}}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"endpoints": {}}
        data.setdefault("endpoints", {})
        return data
    except (OSError, ValueError):
        return {"endpoints": {}}


def save_user_config(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Atomically write the user endpoint file with 0600 permissions."""
    p = Path(path) if path is not None else USER_ENDPOINTS_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def upsert_user_endpoint(name: str, base_url: str, api_key: Optional[str] = None,
                          models: Optional[List[str]] = None,
                          api: str = "openai-completions") -> Dict[str, Any]:
    """Add or update one endpoint in the user library. Empty api_key keeps the old one."""
    name = (name or "").strip()
    base_url = (base_url or "").strip()
    if not name or not base_url:
        raise ValueError("name and base_url are required")
    data = load_user_config()
    endpoints = data["endpoints"]
    entry = dict(endpoints.get(name) or {})
    entry["base_url"] = base_url
    entry["models"] = [str(m).strip() for m in (models or []) if str(m).strip()]
    entry["api"] = api or "openai-completions"
    if api_key:
        entry["api_key"] = api_key
    endpoints[name] = entry
    save_user_config(data)
    return {"ok": True, "name": name}


def delete_user_endpoint(name: str) -> bool:
    data = load_user_config()
    if name not in data["endpoints"]:
        return False
    del data["endpoints"][name]
    save_user_config(data)
    return True


def import_endpoint(name: str, endpoints: Optional[Dict[str, EndpointConfig]] = None) -> EndpointConfig:
    """Copy a discovered endpoint (including its key) into the user library."""
    eps = endpoints if endpoints is not None else discover_endpoints()
    ep = eps.get(name)
    if ep is None:
        raise ValueError(f"unknown endpoint: {name}")
    upsert_user_endpoint(ep.name, ep.base_url, ep.api_key, ep.models, ep.api)
    return ep


def discover_endpoints(
    opencode_json: Optional[Path] = None,
    pi_models_json: Optional[Path] = None,
    repo_json: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    user_json: Optional[Path] = None,
) -> Dict[str, EndpointConfig]:
    """Discover all configured endpoints. Read-only. Keys stay in memory.

    Sources, highest precedence first (name collisions resolve downward):
    env > <repo>/transcoder.endpoints.json > user library > opencode.json > pi models.json
    > synthesized ``ollama-local`` default. Every entry is normalized to the
    OpenAI chat-completions wire format (ollama native URLs gain ``/v1``).
    """
    merged: Dict[str, EndpointConfig] = {}
    for source_fn in (
        _parse_env(env),
        _parse_repo(repo_json or REPO_ENDPOINTS_JSON),
        _parse_user(user_json),
        _parse_opencode(opencode_json or OPENCODE_CONFIG_PATH),
        _parse_pi(pi_models_json or PI_MODELS_PATH),
    ):
        for name, ep in source_fn.items():
            existing = merged.get(name)
            if existing is None or _SOURCE_PRECEDENCE.get(ep.source, 0) > _SOURCE_PRECEDENCE.get(existing.source, 0):
                merged[name] = ep
    merged = {name: _normalize_ollama(ep) for name, ep in merged.items()}
    if "ollama-local" not in merged:
        # Ollama speaks OpenAI-compatible chat completions at ``<host>/v1``;
        # with no config source defining a local ollama, synthesize the
        # default so a running ollama service is immediately usable.
        merged["ollama-local"] = EndpointConfig(
            name="ollama-local", base_url="http://127.0.0.1:11434/v1",
            api_key=None, api="openai-completions", models=[],
            source="default (ollama)",
        )
    return merged


def filter_endpoints(
    endpoints: Dict[str, EndpointConfig], include_local: bool = True
) -> Dict[str, EndpointConfig]:
    """Optionally drop loopback-only endpoints (for pure-online experiments)."""
    if include_local:
        return dict(endpoints)
    return {
        name: ep for name, ep in endpoints.items() if not _is_local_base(ep.base_url)
    }


def _is_local_base(base_url: str) -> bool:
    b = base_url.lower()
    return ("127.0.0.1" in b) or ("localhost" in b) or b.startswith("http://[::1]")


EDGE_LOCAL_NAME = "edge-local"


def edge_model_path(tag: str) -> Optional[str]:
    """Local path of a downloaded edge (local-transformers) model, or None.

    Resolution source is the experiment download log
    (RESULTS/edge_download_log.json); returns None when the tag was never
    downloaded or the download failed.
    """
    log_path = Path(__file__).resolve().parent.parent / "RESULTS" / "edge_download_log.json"
    if not log_path.exists():
        return None
    try:
        log = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entry = log.get(tag) or {}
    path = entry.get("path")
    if entry.get("ok") and path and Path(path).exists():
        return path
    return None


def edge_models() -> List[str]:
    """Locally available edge model tags (successful download-log entries)."""
    log_path = Path(__file__).resolve().parent.parent / "RESULTS" / "edge_download_log.json"
    if not log_path.exists():
        return []
    try:
        log = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [tag for tag, entry in log.items() if entry.get("ok") and edge_model_path(tag)]