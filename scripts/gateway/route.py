"""Model gateway — one OpenAI-compatible interface for local/remote/frontier.

Per decision `slm-learning-085`. Single client that routes requests
to the right backend based on intent + risk lane + cost. K0 ships
with rule-based routing; learned router classifier (Phase 05 SLM
target) replaces the rules later.

Usage (Python lib):

    from scripts.gateway.route import gateway_complete, RoutingPolicy

    response = gateway_complete(
        prompt="take a note about the build",
        intent="cli_translation",
        risk="low",
    )

Usage (CLI):

    .venv/Scripts/python.exe scripts/gateway/route.py \\
        --prompt "take a note about the build" \\
        --intent cli_translation \\
        --risk low

Routing policy (matches `slm-learning-085`):

    intent              | risk | backend
    --------------------|------|------------------------------------------
    cli_translation     | low  | local v2 SLM (scripts/serve/start_v2.sh)
    classification      | low  | local classifier (heuristic v1, SLM later)
    summarize           | low  | local 1.5B
    draft_email         | medium | remote 7B/14B (when available) else frontier
    draft_email         | high | frontier + human approval
    deep_reasoning      | -    | frontier (Opus / GPT-5 / Gemini Pro)
    browser_action      | high | remote 7B/14B for plan + Playwright + approval
    publish/deploy/buy  | high | refused — operator stamp required

Decision refs: slm-learning-051, slm-learning-085, slm-learning-086.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


ROOT = Path(__file__).resolve().parents[2]
TRACE_PATH = ROOT / ".planning" / ".trace-events.jsonl"

LOCAL_ENDPOINT = os.environ.get("GAD_LOCAL_ENDPOINT", "http://127.0.0.1:8000/v1/chat/completions")
LOCAL_MODEL = os.environ.get("GAD_LOCAL_MODEL", "adapter")
REMOTE_ENDPOINT = os.environ.get("GAD_REMOTE_ENDPOINT", "")  # e.g. HF Inference Endpoint
REMOTE_MODEL = os.environ.get("GAD_REMOTE_MODEL", "")
FRONTIER_PROVIDER = os.environ.get("GAD_FRONTIER_PROVIDER", "anthropic")  # anthropic|openai|google


Risk = Literal["low", "medium", "high"]
Intent = Literal[
    "cli_translation", "classification", "summarize",
    "draft_email", "draft_message",
    "deep_reasoning", "code_generation", "code_repair",
    "browser_action", "publish", "deploy", "purchase",
    "unknown",
]


@dataclass
class RoutingDecision:
    intent: Intent
    risk: Risk
    backend: str  # "local-v2" | "local-base" | "remote-7b" | "frontier" | "refused"
    model_id: str
    endpoint: str
    cost_estimate_usd: float = 0.0
    requires_approval: bool = False
    reason: list[str] = field(default_factory=list)


def decide(intent: str, risk: str = "low") -> RoutingDecision:
    """Rule-based routing. Replace with learned classifier in Phase 05."""
    reason: list[str] = []

    if intent in {"publish", "deploy", "purchase"}:
        reason.append(f"{intent} requires operator stamp per slm-learning-085")
        return RoutingDecision(
            intent=intent,  # type: ignore[arg-type]
            risk="high",  # type: ignore[arg-type]
            backend="refused",
            model_id="-",
            endpoint="-",
            requires_approval=True,
            reason=reason,
        )

    if intent == "browser_action":
        reason.append("browser action -> remote 7B/14B + Playwright + approval")
        return RoutingDecision(
            intent="browser_action",
            risk="high",
            backend="remote-or-frontier",
            model_id=REMOTE_MODEL or "frontier",
            endpoint=REMOTE_ENDPOINT or "frontier-api",
            requires_approval=True,
            reason=reason,
        )

    if intent in {"cli_translation", "classification", "summarize"} and risk in {"low"}:
        reason.append("low-risk narrow shape -> local v2 SLM (30/30 GAD-tools)")
        return RoutingDecision(
            intent=intent,  # type: ignore[arg-type]
            risk=risk,  # type: ignore[arg-type]
            backend="local-v2",
            model_id=LOCAL_MODEL,
            endpoint=LOCAL_ENDPOINT,
            cost_estimate_usd=0.0,
            requires_approval=False,
            reason=reason,
        )

    if intent in {"draft_email", "draft_message"} and risk == "low":
        if REMOTE_ENDPOINT:
            reason.append("draft (low-risk) -> remote 7B/14B")
            return RoutingDecision(
                intent=intent,  # type: ignore[arg-type]
                risk="low",
                backend="remote-7b",
                model_id=REMOTE_MODEL,
                endpoint=REMOTE_ENDPOINT,
                cost_estimate_usd=0.001,
                requires_approval=True,  # outbound = approval still
                reason=reason,
            )
        reason.append("draft (low-risk) but no remote configured -> frontier fallback")
        return RoutingDecision(
            intent=intent,  # type: ignore[arg-type]
            risk="low",
            backend="frontier",
            model_id=f"frontier:{FRONTIER_PROVIDER}",
            endpoint="frontier-api",
            cost_estimate_usd=0.05,
            requires_approval=True,
            reason=reason,
        )

    if intent in {"draft_email", "draft_message"} and risk in {"medium", "high"}:
        reason.append("draft (medium/high) -> frontier + human approval")
        return RoutingDecision(
            intent=intent,  # type: ignore[arg-type]
            risk=risk,  # type: ignore[arg-type]
            backend="frontier",
            model_id=f"frontier:{FRONTIER_PROVIDER}",
            endpoint="frontier-api",
            cost_estimate_usd=0.10,
            requires_approval=True,
            reason=reason,
        )

    if intent in {"deep_reasoning", "code_generation", "code_repair"}:
        reason.append("deep reasoning / code -> frontier (Opus/GPT-5/Gemini Pro)")
        return RoutingDecision(
            intent=intent,  # type: ignore[arg-type]
            risk=risk,  # type: ignore[arg-type]
            backend="frontier",
            model_id=f"frontier:{FRONTIER_PROVIDER}",
            endpoint="frontier-api",
            cost_estimate_usd=0.20,
            requires_approval=False,
            reason=reason,
        )

    reason.append("unknown intent -> defer to frontier with logged uncertainty")
    return RoutingDecision(
        intent="unknown",
        risk=risk,  # type: ignore[arg-type]
        backend="frontier",
        model_id=f"frontier:{FRONTIER_PROVIDER}",
        endpoint="frontier-api",
        cost_estimate_usd=0.10,
        requires_approval=False,
        reason=reason,
    )


def call_local(prompt: str, system: str | None = None,
               max_tokens: int = 256, endpoint: str = LOCAL_ENDPOINT,
               model: str = LOCAL_MODEL) -> str:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": model,
        "messages": msgs,
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"local endpoint {endpoint} unreachable: {e}")
    return payload["choices"][0]["message"]["content"].strip()


def log_decision(decision: RoutingDecision, prompt_preview: str) -> None:
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": "gateway",
        "kind": "routing_decision",
        "intent": decision.intent,
        "risk": decision.risk,
        "backend": decision.backend,
        "model_id": decision.model_id,
        "cost_estimate_usd": decision.cost_estimate_usd,
        "requires_approval": decision.requires_approval,
        "reason": decision.reason,
        "prompt_preview": prompt_preview[:120],
        "decision_refs": ["slm-learning-085", "slm-learning-086"],
    }
    with TRACE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--system", default=None)
    parser.add_argument("--intent", default="unknown")
    parser.add_argument("--risk", default="low", choices=["low", "medium", "high"])
    parser.add_argument("--no-execute", action="store_true",
                        help="Print routing decision; do not call backend")
    args = parser.parse_args()

    decision = decide(args.intent, args.risk)
    log_decision(decision, args.prompt)

    print("[gateway] routing decision:")
    print(json.dumps({
        "intent": decision.intent,
        "risk": decision.risk,
        "backend": decision.backend,
        "model_id": decision.model_id,
        "endpoint": decision.endpoint,
        "cost_estimate_usd": decision.cost_estimate_usd,
        "requires_approval": decision.requires_approval,
        "reason": decision.reason,
    }, indent=2))

    if args.no_execute or decision.backend == "refused":
        return 0

    if decision.backend in {"local-v2", "local-base"}:
        try:
            out = call_local(args.prompt, system=args.system,
                             endpoint=decision.endpoint,
                             model=decision.model_id)
            print("\n[gateway] response:")
            print(out)
            return 0
        except RuntimeError as e:
            print(f"\n[gateway] LOCAL FAILED: {e}")
            print("[gateway] hint: bash scripts/serve/start_v2.sh first")
            return 1

    print("\n[gateway] backend not yet wired for direct execution. "
          "Routing decision logged; call your backend manually.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
