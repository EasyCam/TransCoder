# -*- coding: utf-8 -*-
"""Wiring helper (P3): build the four-role team from locally configured endpoints.

Used by ``transcoder.cli`` (team mode), ``transcoder.app`` (Flask team route)
and ``run_experiment.py`` (P5/P6), so all entry points share one construction
path and semantics.

Endpoint names come from ``transcoder.endpoints.discover_endpoints()`` (the
pre-probed set; keys stay in memory, never serialized). An endpoint that is
not reachable at build time does not abort: the orchestrator's degradation
chain handles it (spec §2), and ``reviewer_available`` is re-checked per run.
"""

from typing import Any, Dict, Optional

from transcoder.agents import ReviewerAgent, TranslatorAgent, TerminologyGuardAgent
from transcoder.endpoints import discover_endpoints
from transcoder.orchestrator import EventLog, TeamOrchestrator
from transcoder.providers import ConfiguredEndpointProvider, LLMProvider

REACHABLE_DEFAULTS = {
    # Verified in RESULTS/probe.json (2026-10-19): chat ping ok.
    "reviewer_online": "deepseek",       # used by G0 / G5
    "reviewer_online_alt": "cycleuser-halogen",
}


def provider_for_endpoint(name: str, model: Optional[str] = None, endpoints: Optional[Dict] = None,
                          timeout: float = 60.0):
    """Build a provider bound to one configured endpoint (by name).

    The pseudo-endpoint ``edge-local`` resolves to the local transformers
    runtime (models from RESULTS/edge_download_log.json, offline weights);
    every other name must exist in the configured registry.
    """
    from transcoder.endpoints import EDGE_LOCAL_NAME, edge_model_path

    if name == EDGE_LOCAL_NAME:
        tag = model or "qwen3:0.6b"
        path = edge_model_path(tag)
        if path is None:
            raise ValueError(f"edge-local model not downloaded locally: {tag}")
        from transcoder.edge_local import EdgeTransformersProvider

        return EdgeTransformersProvider(model_path=path, model_tag=tag)
    eps = endpoints if endpoints is not None else discover_endpoints()
    if name not in eps:
        raise ValueError(f"endpoint not configured locally: {name}; known: {sorted(eps)}")
    return ConfiguredEndpointProvider(eps[name], default_model=model, timeout=timeout)


def endpoint_model_list(name: str, endpoints: Optional[Dict] = None) -> list:
    from transcoder.endpoints import EDGE_LOCAL_NAME, edge_models

    if name == EDGE_LOCAL_NAME:
        return edge_models()
    eps = endpoints if endpoints is not None else discover_endpoints()
    ep = eps.get(name)
    return list(ep.models) if ep else []


def build_team(
    translator_provider: Any = None,
    translator_model: Optional[str] = None,
    reviewer_provider: Any = None,
    reviewer_model: Optional[str] = None,
    reviewer_fallback_provider: Any = None,
    reviewer_fallback_model: Optional[str] = None,
    terminology_service=None,
    vector_db_service=None,
    local_fallback=None,
    max_rounds: int = 3,
    temperature: float = 0.3,
    event_log: Optional[EventLog] = None,
    seed: Optional[int] = None,
    pass_threshold: float = 7.0,
    pass_policy: str = "scores",
    minimal_edit: bool = False,
    span_rewrite: bool = False,
) -> TeamOrchestrator:
    """Assemble a TeamOrchestrator from explicit providers + services."""
    if translator_provider is None:
        raise ValueError("translator_provider is required")
    translator = TranslatorAgent(translator_provider, translator_model or translator_provider.default_model,
                                 temperature=temperature)
    reviewer = None
    if reviewer_provider is not None:
        reviewer = ReviewerAgent(reviewer_provider, reviewer_model or reviewer_provider.default_model,
                                 temperature=temperature, pass_threshold=pass_threshold,
                                 pass_policy=pass_policy)
    reviewer_fallback = None
    if reviewer_fallback_provider is not None:
        reviewer_fallback = ReviewerAgent(
            reviewer_fallback_provider,
            reviewer_fallback_model or reviewer_fallback_provider.default_model,
            temperature=temperature, pass_threshold=pass_threshold, pass_policy=pass_policy,
        )
    guard = None
    if terminology_service is not None or vector_db_service is not None:
        guard = TerminologyGuardAgent(terminology_service, vector_db_service)
    return TeamOrchestrator(
        translator=translator, reviewer=reviewer, reviewer_fallback=reviewer_fallback,
        guard=guard, max_rounds=max_rounds,
        event_log=event_log or EventLog(), local_fallback=local_fallback, seed=seed,
        minimal_edit=minimal_edit, span_rewrite=span_rewrite,
    )


def build_team_from_endpoints(
    translator_endpoint: Optional[str] = None,
    translator_model: Optional[str] = None,
    reviewer_endpoint: Optional[str] = None,
    reviewer_model: Optional[str] = None,
    reviewer_fallback_endpoint: Optional[str] = None,
    reviewer_fallback_model: Optional[str] = None,
    *,
    terminology_service=None,
    vector_db_service=None,
    local_fallback=None,
    max_rounds: int = 3,
    temperature: float = 0.3,
    event_log: Optional[EventLog] = None,
    seed: Optional[int] = None,
    endpoints: Optional[Dict] = None,
) -> TeamOrchestrator:
    """Convenience: resolve endpoint names -> providers -> orchestrator.

    ``reviewer_endpoint=None`` => no reviewer => guaranteed degraded (pure edge).
    """
    tp = provider_for_endpoint(translator_endpoint, translator_model, endpoints) if translator_endpoint else None
    if tp is None:
        raise ValueError("translator_endpoint is required")
    rp = provider_for_endpoint(reviewer_endpoint, reviewer_model, endpoints) if reviewer_endpoint else None
    rfp = (provider_for_endpoint(reviewer_fallback_endpoint, reviewer_fallback_model, endpoints)
           if reviewer_fallback_endpoint else None)
    return build_team(
        translator_provider=tp, translator_model=translator_model,
        reviewer_provider=rp, reviewer_model=reviewer_model,
        reviewer_fallback_provider=rfp, reviewer_fallback_model=reviewer_fallback_model,
        terminology_service=terminology_service, vector_db_service=vector_db_service,
        local_fallback=local_fallback, max_rounds=max_rounds,
        temperature=temperature, event_log=event_log, seed=seed,
    )


def team_result_to_dict(result) -> dict:
    """JSON-safe view of a TeamResult for API responses (already redacted at log time)."""
    return result.to_dict()