"""GAD Gateway router — task_shape -> model.

Per decision slm-learning-208 (Gateway scaffold; production usage NOW
with logging) + slm-learning-197 (teacher policy) + slm-learning-103
(compare-and-compete discipline).

v1 architecture (this file):
    1. Look up task_shape in routes.json
    2. If not found -> use the catchall route whose task_shape == "*"
    3. Walk [primary] + fallback_chain in order; first success wins
    4. Each call attempt writes ONE trace row (so fallbacks are visible)
    5. accepted_by defaults to "unverified" — verifier integration is
       future work (TODO(verifier))

Real model backends wired in v1.1 (decisions 214-217):
    - Anthropic SDK for claude-* models
    - HTTP (OpenAI-compat) for Modal vLLM endpoint
    - HTTP (OpenAI-compat) for local vLLM/llama.cpp endpoint
    Neither Modal nor local backends auto-fall-back to Anthropic —
    explicit-failure envelope is returned; caller decides fallback.
    See: slm-learning-214 (no silent paid fallback rule).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .trace_logger import write_trace

ROOT = Path(__file__).resolve().parents[2]
ROUTES_PATH = Path(__file__).resolve().parent / "routes.json"

# Sentinel used by routes.json to mark the catchall route.
WILDCARD_TASK_SHAPE = "*"

# ---------------------------------------------------------------------------
# Anthropic pricing (USD per 1M tokens, as of 2026-05)
# Update when Anthropic revises rates — these are hardcoded intentionally
# so cost math is transparent and auditable without SDK version churn.
# Sources: anthropic.com/pricing
# ---------------------------------------------------------------------------
_ANTHROPIC_PRICING: dict[str, dict[str, float]] = {
    # claude-haiku-4-5
    "claude-haiku-4-5":   {"input": 0.80,  "output": 4.00},
    # claude-sonnet-4-6
    "claude-sonnet-4-6":  {"input": 3.00,  "output": 15.00},
    # claude-opus-4-5
    "claude-opus-4-5":    {"input": 15.00, "output": 75.00},
    # claude-opus-4-7 (latest; same tier as opus-4-5 until official pricing publishes)
    "claude-opus-4-7":    {"input": 15.00, "output": 75.00},
}
_ANTHROPIC_DEFAULT_PRICING = {"input": 3.00, "output": 15.00}  # sonnet tier

# Task-shape -> preferred Anthropic model.
# Routing only fires when the primary route resolves to a claude-* model.
_ANTHROPIC_TASK_MODEL: dict[str, str] = {
    "gad_decision":              "claude-haiku-4-5",
    "gad_note":                  "claude-haiku-4-5",
    "routing_question":          "claude-haiku-4-5",
    "gad_handoff":               "claude-sonnet-4-6",
    "tool_action_json":          "claude-sonnet-4-6",
    "eval_summary":              "claude-sonnet-4-6",
    "code_function_completion":  "claude-sonnet-4-6",
    "code_repair":               "claude-opus-4-5",
}
_ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-6"

# Modal vLLM endpoint — OpenAI-compatible /v1/chat/completions
# Override via MODAL_VLLM_URL env var at runtime.
_MODAL_VLLM_URL_DEFAULT = (
    "https://b2gdevs--slm-learning-vllm-vllm-engine-serve.modal.run"
    "/v1/chat/completions"
)

# Local vLLM / llama.cpp endpoint — OpenAI-compatible.
# Override via LOCAL_QWEN_URL env var.  Default assumes vllm serve on :8000.
_LOCAL_QWEN_URL_DEFAULT = "http://localhost:8000/v1/chat/completions"


@dataclass
class RouterResult:
    task_shape: str
    route_id: str
    model_id: str
    tier: int
    fallback_chain: list[str]
    prompt: str
    output: str
    latency_seconds: float
    cost_usd: float
    accepted_by: str  # "unverified" in v1; verifier id once wired
    trace_row_id: str  # trace_id of the successful (or last) attempt
    attempts: list[dict] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

_ROUTES_CACHE: dict[str, Any] | None = None


def _load_routes(path: Path = ROUTES_PATH) -> dict:
    global _ROUTES_CACHE
    if _ROUTES_CACHE is None or _ROUTES_CACHE.get("__path__") != str(path):
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        data["__path__"] = str(path)
        _ROUTES_CACHE = data
    return _ROUTES_CACHE


def _select_route(task_shape: str, routes: dict) -> dict:
    """Find route for task_shape; fall back to wildcard '*' if not found."""
    catchall: dict | None = None
    for r in routes["routes"]:
        if r["task_shape"] == task_shape:
            return r
        if r["task_shape"] == WILDCARD_TASK_SHAPE:
            catchall = r
    if catchall is None:
        raise RuntimeError(
            f"No route for task_shape={task_shape!r} and no '*' catchall in routes.json"
        )
    return catchall


def _vendor_of(model_id: str) -> str:
    if model_id.startswith("claude-"):
        return "anthropic"
    if model_id.startswith("qwen") or "qwen" in model_id:
        return "qwen"
    if model_id.startswith("deepseek"):
        return "deepseek"
    if model_id.startswith("gpt-"):
        return "openai"
    if model_id.startswith("gemini"):
        return "google"
    return "unknown"


# ---------------------------------------------------------------------------
# Real backends (wired slm-learning-214..217)
# ---------------------------------------------------------------------------

def _call_anthropic(
    model_id: str,
    prompt: str,
    task_shape: str = "",
    max_tokens: int = 1024,
) -> tuple[str, float, float]:
    """Call Anthropic API via the official SDK.

    Model selection: task_shape wins over model_id if there is a
    preferred mapping in _ANTHROPIC_TASK_MODEL; otherwise model_id is
    used directly (falling back to _ANTHROPIC_DEFAULT_MODEL if blank).

    Raises EnvironmentError if ANTHROPIC_API_KEY is absent — the router's
    try/except will catch this and mark success=False in the trace row.
    Does NOT fall back silently to another provider (slm-learning-214).
    """
    try:
        import anthropic as _anthropic
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "anthropic SDK not installed. "
            "Run: pip install anthropic  (then restart)"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to your .env or export it before running the gateway."
        )

    # Resolve model: prefer task_shape mapping, then explicit model_id, then default.
    resolved_model = (
        _ANTHROPIC_TASK_MODEL.get(task_shape)
        or (model_id if model_id.startswith("claude-") else None)
        or _ANTHROPIC_DEFAULT_MODEL
    )

    client = _anthropic.Anthropic(api_key=api_key)
    t0 = time.perf_counter()
    response = client.messages.create(
        model=resolved_model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    latency = time.perf_counter() - t0

    output_text = response.content[0].text if response.content else ""
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens

    pricing = _ANTHROPIC_PRICING.get(resolved_model, _ANTHROPIC_DEFAULT_PRICING)
    cost_usd = (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000

    return output_text, latency, cost_usd


def _call_openai_compat_endpoint(
    endpoint_url: str,
    model_id: str,
    prompt: str,
    backend_name: str,
    unavailable_error_class: str,
    max_tokens: int = 512,
    temperature: float = 0.0,
    timeout_s: int = 30,
) -> tuple[str, float, float]:
    """Call an OpenAI-compatible /v1/chat/completions endpoint via requests.

    Returns (output_text, latency_s, cost_usd).
    On connection failure or non-200 response, raises RuntimeError with
    error_class metadata embedded — the router catches this and marks
    success=False.  Does NOT fall back silently (slm-learning-214).
    """
    import requests as _requests  # stdlib-adjacent; always available

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    t0 = time.perf_counter()
    try:
        resp = _requests.post(endpoint_url, json=payload, timeout=timeout_s)
    except _requests.exceptions.ConnectionError as exc:
        latency = time.perf_counter() - t0
        raise RuntimeError(
            f"error_class={unavailable_error_class} "
            f"endpoint={endpoint_url} "
            f"detail=ConnectionError after {latency:.2f}s: {exc}"
        ) from exc
    except _requests.exceptions.Timeout as exc:
        latency = time.perf_counter() - t0
        raise RuntimeError(
            f"error_class={unavailable_error_class} "
            f"endpoint={endpoint_url} "
            f"detail=Timeout after {latency:.2f}s"
        ) from exc

    latency = time.perf_counter() - t0

    if resp.status_code != 200:
        raise RuntimeError(
            f"error_class={unavailable_error_class} "
            f"endpoint={endpoint_url} "
            f"http_status={resp.status_code} "
            f"body_preview={resp.text[:200]}"
        )

    data = resp.json()
    output_text = data["choices"][0]["message"]["content"]
    # cost_usd: local/Modal inference billed by compute, not per-token.
    # We log $0 at the gateway boundary; Modal dashboard tracks real spend.
    cost_usd = 0.0
    return output_text, latency, cost_usd


def _call_modal_vllm(model_id: str, prompt: str) -> tuple[str, float, float]:
    """Call the Modal vLLM endpoint (OpenAI-compat).

    URL: MODAL_VLLM_URL env var, or the hardcoded default
    (b2gdevs--slm-learning-vllm...).  Returns explicit-failure
    RuntimeError if the endpoint is down — caller decides fallback.
    """
    url = os.environ.get("MODAL_VLLM_URL", _MODAL_VLLM_URL_DEFAULT)
    return _call_openai_compat_endpoint(
        endpoint_url=url,
        model_id=model_id,
        prompt=prompt,
        backend_name="modal_vllm",
        unavailable_error_class="modal_unavailable",
    )


def _call_qwen_local(model_id: str, prompt: str) -> tuple[str, float, float]:
    """Call a local vLLM / llama.cpp server (OpenAI-compat).

    URL: LOCAL_QWEN_URL env var, default localhost:8000.
    Returns explicit-failure RuntimeError if the server is not running —
    caller decides fallback.  Remediation hint: start scripts/serve/serve_adapter.py
    or modal_app/serve_vllm.py.
    """
    url = os.environ.get("LOCAL_QWEN_URL", _LOCAL_QWEN_URL_DEFAULT)
    return _call_openai_compat_endpoint(
        endpoint_url=url,
        model_id=model_id,
        prompt=prompt,
        backend_name="qwen_local",
        unavailable_error_class="local_qwen_not_running",
        timeout_s=60,  # local cold-start can be slow
    )


def _dispatch(
    model_id: str,
    prompt: str,
    task_shape: str = "",
) -> tuple[str, float, float]:
    """Dispatch to the real backend for model_id.

    Anthropic models call the Anthropic SDK.
    Qwen ≤7B calls the local vLLM server.
    Qwen 14B+ and all other open-weight models call the Modal vLLM endpoint.
    Neither non-Anthropic backend auto-falls-back to Anthropic on failure;
    they raise RuntimeError which the route() loop catches (slm-learning-214).
    """
    vendor = _vendor_of(model_id)
    if vendor == "anthropic":
        return _call_anthropic(model_id, prompt, task_shape=task_shape)
    if vendor == "qwen":
        # 7B and below run locally; 14B+ via Modal vLLM.
        big = any(tok in model_id for tok in ("14b", "32b", "70b", "80b", "120b"))
        if big:
            return _call_modal_vllm(model_id, prompt)
        return _call_qwen_local(model_id, prompt)
    # Other open-weight comparators go through Modal vLLM.
    return _call_modal_vllm(model_id, prompt)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route(
    task_shape: str,
    prompt: str,
    context: Optional[dict] = None,
    *,
    tier_hint: Optional[str] = None,
    dry_run: bool = False,
) -> RouterResult:
    """Route a prompt for ``task_shape`` to the first model that succeeds.

    Args:
        task_shape: matches a routes.json entry; falls back to '*' route
        prompt: user prompt to forward
        context: optional structured context dict (logged in the trace row)
        tier_hint: '0'|'1'|'2'|'3' to force a tier (v1: logged but not yet
                   used to override route selection; reserved for future
                   tier-aware routing)
        dry_run: if True, log routing decision only — no model call,
                 no trace row written

    Returns:
        RouterResult with the first-success output. ``accepted_by`` is
        'unverified' in v1 — verifier integration is future work.
    """
    routes = _load_routes()
    route_def = _select_route(task_shape, routes)

    chain = [route_def["primary"]] + list(route_def.get("fallback_chain") or [])
    fallback_chain = list(route_def.get("fallback_chain") or [])
    tier = int(route_def.get("tier", 0))

    if dry_run:
        return RouterResult(
            task_shape=task_shape,
            route_id=route_def["id"],
            model_id=chain[0],
            tier=tier,
            fallback_chain=fallback_chain,
            prompt=prompt,
            output="",
            latency_seconds=0.0,
            cost_usd=0.0,
            accepted_by="unverified",
            trace_row_id="",
            attempts=[{
                "model_id": chain[0],
                "would_call": True,
                "dry_run": True,
                "tier_hint": tier_hint,
            }],
            dry_run=True,
        )

    attempts: list[dict] = []
    last_trace_id = ""

    for idx, model_id in enumerate(chain):
        is_fallback = idx > 0
        t0 = time.perf_counter()
        success = False
        output = ""
        latency = 0.0
        cost = 0.0
        error: Optional[str] = None

        try:
            output, latency, cost = _dispatch(model_id, prompt, task_shape=task_shape)
            success = True
        except Exception as exc:  # noqa: BLE001  — last-resort guard
            error = f"{type(exc).__name__}: {exc}"
            latency = time.perf_counter() - t0

        # TODO(verifier): plug verifier into success determination.
        # For v1 every dispatched call is treated as success unless the
        # backend raised, and accepted_by stays 'unverified'.
        accepted_by = "unverified"

        row = {
            "task_shape": task_shape,
            "used_model": model_id,
            "tier": tier,
            "tier_hint": tier_hint,
            "route_id": route_def["id"],
            "is_fallback": is_fallback,
            "fallback_index": idx,
            "prompt_preview": prompt[:120],
            "prompt_chars": len(prompt),
            "output_chars": len(output),
            "latency_seconds": round(latency, 4),
            "cost": round(cost, 6),
            "success": success,
            "fallback_used": is_fallback,
            "accepted_by": accepted_by,
            "error": error,
            "context_keys": sorted((context or {}).keys()),
            "decision_refs": ["slm-learning-208"],
        }
        trace_id = write_trace(row)
        last_trace_id = trace_id
        attempts.append({
            "trace_id": trace_id,
            "model_id": model_id,
            "is_fallback": is_fallback,
            "success": success,
            "latency_seconds": round(latency, 4),
            "cost_usd": round(cost, 6),
            "error": error,
        })

        if success:
            return RouterResult(
                task_shape=task_shape,
                route_id=route_def["id"],
                model_id=model_id,
                tier=tier,
                fallback_chain=fallback_chain,
                prompt=prompt,
                output=output,
                latency_seconds=round(latency, 4),
                cost_usd=round(cost, 6),
                accepted_by=accepted_by,
                trace_row_id=trace_id,
                attempts=attempts,
                dry_run=False,
            )

    # All models failed.
    raise RuntimeError(
        f"All models in route {route_def['id']!r} failed for task_shape={task_shape!r}. "
        f"Attempts: {attempts}"
    )
