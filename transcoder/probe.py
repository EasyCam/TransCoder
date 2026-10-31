"""
Endpoint / edge-model probe for TransCoder-NEXT (P1).

Writes ``RESULTS/probe.json`` with:
- every locally configured endpoint: reachability + latency + model list +
  minimal chat ping (all redacted, never contains api_key);
- edge small-model candidates (<=1B) presence on ModelScope / HF mirror;
- machine fingerprint (chip / RAM / runtime versions) for honest reporting.

Usage:
    python -m transcoder.probe [--results-dir RESULTS] [--no-chat-ping]
"""

import json
import platform
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, Optional

from transcoder.endpoints import discover_endpoints, redact
from transcoder.providers import probe_endpoint

_EDGE_TIMEOUT = 10.0


def default_results_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "RESULTS"


def machine_fingerprint() -> dict:
    """Honest machine/runtime record for the edge-intelligence pillar."""
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
    }
    try:
        brand = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if brand:
            info["cpu_brand"] = brand
    except Exception:
        pass
    try:
        mem = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5).stdout.strip()
        if mem:
            info["ram_bytes"] = int(mem)
    except Exception:
        pass
    try:
        info["cpu_count_physical"] = subprocess.run(
            ["sysctl", "-n", "hw.physicalcpu"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except Exception:
        pass
    try:
        import torch

        info["torch"] = torch.__version__
        info["torch_threads_default"] = torch.get_num_threads()
    except Exception:
        info["torch"] = None
    try:
        import transformers

        info["transformers"] = transformers.__version__
    except Exception:
        info["transformers"] = None
    try:
        import ollama as _ollama  # noqa: F401

        info["ollama_python"] = True
    except Exception:
        info["ollama_python"] = False
    return info


def _modelscope_model_exists(repo: str) -> dict:
    """Direct presence check: GET /api/v1/models/{org}/{name}."""
    url = f"https://www.modelscope.cn/api/v1/models/{repo}"
    try:
        with urllib.request.urlopen(url, timeout=_EDGE_TIMEOUT) as r:
            body = json.loads(r.read().decode("utf-8"))
        available = bool(body.get("Data", {}).get("Id") or body.get("Code") == 200)
        return {"repo": repo, "http_status": 200, "available": available}
    except Exception as e:
        status = getattr(e, "code", None)
        return {"repo": repo, "http_status": status, "available": False, "error": f"{type(e).__name__}"}


def probe_edge_candidates() -> dict:
    """Check presence of the four edge candidates on ModelScope (direct API).

    A 200 here is *catalog* presence; the authoritative check is the actual
    config.json + weights download during P6 (recorded there).
    """
    # paper tag -> candidate repos ordered by preference
    checks = [
        ("lfm2.5-350m", ["LiquidAI/LFM2.5-350M", "LiquidAI/LFM2-350M"]),
        ("granite4:350m-h", ["ibm-granite/granite-4.0-h-350m", "ibm-granite/granite-4.0-350m"]),
        ("gemma3:270m", ["google/gemma-3-270m-it"]),
        ("qwen3:0.6b", ["Qwen/Qwen3-0.6B"]),
    ]
    out = {}
    for tag, repos in checks:
        results = [_modelscope_model_exists(repo) for repo in repos]
        entry = {"candidates_checked": results, "present": any(r["available"] for r in results)}
        chosen = next((r["repo"] for r in results if r["available"]), None)
        entry["proposed_repo"] = chosen
        out[tag] = entry
    return out


def probe_all(results_dir: Optional[Path] = None, chat_ping: bool = True) -> dict:
    """Probe every discovered endpoint + edge candidates; write probe.json."""
    results_dir = Path(results_dir) if results_dir else default_results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)

    endpoints = discover_endpoints()
    endpoint_records = []
    for name, ep in sorted(endpoints.items()):
        # Local runtime endpoints: plain reachability, no chat ping (no key).
        ping = chat_ping and not _is_local(ep.base_url)
        rec = probe_endpoint(ep, timeout=12.0, chat_ping=ping)
        if _is_local(ep.base_url) and rec["probe"].get("reachable"):
            # Native ollama endpoint check (GET /api/tags) as extra evidence.
            try:
                host = ep.base_url[: -len("/v1")] if ep.base_url.endswith("/v1") else ep.base_url
                url = host.replace("/v1", "") + "/api/tags"
                with urllib.request.urlopen(url, timeout=8.0) as r:
                    tags = json.loads(r.read().decode("utf-8"))
                rec["probe"]["native_api_tags"] = sorted(m.get("name", "") for m in tags.get("models", []))
            except Exception:
                rec["probe"]["native_api_tags"] = None
        endpoint_records.append(rec)

    edge = probe_edge_candidates()
    probe_doc = {
        "schema": "transcoder-next/probe/v1",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "machine": redact(machine_fingerprint()),
        "endpoints": endpoint_records,
        "edge_candidates": edge,
        "note": "api keys never serialized; masked_key shows length only",
    }
    out_path = results_dir / "probe.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(probe_doc, f, ensure_ascii=False, indent=2)
    return probe_doc


def _is_local(base_url: str) -> bool:
    b = base_url.lower()
    return "127.0.0.1" in b or "localhost" in b


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="transcoder-probe", description="Probe configured endpoints (P1)")
    parser.add_argument("--results-dir", default=None, help="Results directory (default: <repo>/RESULTS)")
    parser.add_argument("--no-chat-ping", action="store_true", help="Skip minimal chat completions")
    args = parser.parse_args()

    doc = probe_all(results_dir=Path(args.results_dir) if args.results_dir else None, chat_ping=not args.no_chat_ping)
    reached = [ep["name"] for ep in doc["endpoints"] if ep["probe"].get("reachable")]
    print(f"probe.json written; reachable endpoints: {reached or '(none)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())