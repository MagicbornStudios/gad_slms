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

Real model backends are NOT wired in v1. Stubs return synthetic
output, latency, and cost so the routing + logging path can be
exercised end-to-end without spend. Real wiring is the next session
(TODO(real-backend)).
"""
from __future__ import annotations

import json
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
# Backend stubs (real wiring lands next session)
# ---------------------------------------------------------------------------

def _call_anthropic_stub(model_id: str, prompt: str) -> tuple[str, float, float]:
    """Synthetic Anthropic call. TODO(real-backend): bind anthropic SDK."""
    output = f"[ROUTED: {model_id} would handle: {prompt[:60]}...]"
    latency = 0.42
    # Synthetic cost: ~ Haiku/Sonnet/Opus tier guess based on id
    cost = 0.0008 if "haiku" in model_id else (0.005 if "sonnet" in model_id else 0.02)
    return output, latency, cost


def _call_qwen_local_stub(model_id: str, prompt: str) -> tuple[str, float, float]:
    """Synthetic local-Qwen call (vLLM/HF). TODO(real-backend): bind HTTP/vLLM."""
    output = f"[ROUTED: {model_id} would handle: {prompt[:60]}...]"
    latency = 0.18
    cost = 0.0  # local inference is free at the gateway boundary
    return output, latency, cost


def _call_modal_vllm_stub(model_id: str, prompt: str) -> tuple[str, float, float]:
    """Synthetic Modal-vLLM call for >7B Qwen sizes. TODO(real-backend)."""
    output = f"[ROUTED: {model_id} would handle: {prompt[:60]}...]"
    latency = 0.65
    cost = 0.001  # Modal compute approximation
    return output, latency, cost


def _dispatch(model_id: str, prompt: str) -> tuple[str, float, float]:
    """Pick a backend stub for the model. Real backends bind in next session."""
    vendor = _vendor_of(model_id)
    if vendor == "anthropic":
        return _call_anthropic_stub(model_id, prompt)
    if vendor == "qwen":
        # 7B and below run locally; 14B+ via Modal vLLM.
        # Heuristic on the size token in the id.
        big = any(tok in model_id for tok in ("14b", "32b", "70b", "80b", "120b"))
        if big:
            return _call_modal_vllm_stub(model_id, prompt)
        return _call_qwen_local_stub(model_id, prompt)
    # Default to Modal vLLM stub for other open-weight comparators.
    return _call_modal_vllm_stub(model_id, prompt)


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
            output, latency, cost = _dispatch(model_id, prompt)
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
