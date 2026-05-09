"""Smoke-test each Gateway backend with a trivial 1-token prompt.

Usage:
    python scripts/gateway/smoke.py --backend anthropic
    python scripts/gateway/smoke.py --backend modal
    python scripts/gateway/smoke.py --backend qwen-local

Each invocation calls the backend directly (bypasses route() so we test
the low-level call, not the routing table) and prints the result envelope.
Anthropic cost should be < $0.001.  Modal / qwen-local are expected to
return explicit-failure envelopes when the server is not running.

Decision refs: slm-learning-208, 214-217.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Allow running as `python scripts/gateway/smoke.py` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Load .env if present so ANTHROPIC_API_KEY is available without
# needing a shell-level export.
_env_path = Path(__file__).resolve().parents[2] / ".env"
if _env_path.exists():
    with _env_path.open("r", encoding="utf-8-sig") as _fh:
        for _line in _fh:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

# Import after sys.path is set up.
from scripts.gateway.router import (  # noqa: E402
    _call_anthropic,
    _call_modal_vllm,
    _call_qwen_local,
)

SMOKE_PROMPT = "Say 'ok'"


def _run_anthropic() -> dict:
    t0 = time.perf_counter()
    try:
        output, latency, cost = _call_anthropic(
            model_id="claude-haiku-4-5",
            prompt=SMOKE_PROMPT,
            task_shape="gad_note",
            max_tokens=8,
        )
        return {
            "backend": "anthropic",
            "success": True,
            "output": output,
            "latency_s": round(latency, 3),
            "cost_usd": round(cost, 6),
            "model": "claude-haiku-4-5",
        }
    except Exception as exc:
        return {
            "backend": "anthropic",
            "success": False,
            "error": str(exc),
            "latency_s": round(time.perf_counter() - t0, 3),
        }


def _run_modal() -> dict:
    t0 = time.perf_counter()
    try:
        output, latency, cost = _call_modal_vllm(
            model_id="dr-stein-cli-v2",
            prompt=SMOKE_PROMPT,
        )
        return {
            "backend": "modal",
            "success": True,
            "output": output,
            "latency_s": round(latency, 3),
            "cost_usd": cost,
        }
    except Exception as exc:
        return {
            "backend": "modal",
            "success": False,
            "error_class": "modal_unavailable",
            "error": str(exc),
            "latency_s": round(time.perf_counter() - t0, 3),
            "remediation": "Deploy endpoint: modal deploy modal_app/serve_vllm.py",
        }


def _run_qwen_local() -> dict:
    t0 = time.perf_counter()
    try:
        output, latency, cost = _call_qwen_local(
            model_id="qwen2.5-coder-7b-instruct",
            prompt=SMOKE_PROMPT,
        )
        return {
            "backend": "qwen-local",
            "success": True,
            "output": output,
            "latency_s": round(latency, 3),
            "cost_usd": cost,
        }
    except Exception as exc:
        return {
            "backend": "qwen-local",
            "success": False,
            "error_class": "local_qwen_not_running",
            "error": str(exc),
            "latency_s": round(time.perf_counter() - t0, 3),
            "remediation": (
                "Start a local server first: "
                "python -m vllm.entrypoints.openai.api_server "
                "--model Qwen/Qwen2.5-Coder-7B-Instruct --port 8000  "
                "OR modal deploy modal_app/serve_vllm.py and set MODAL_VLLM_URL"
            ),
        }


_RUNNERS = {
    "anthropic": _run_anthropic,
    "modal": _run_modal,
    "qwen-local": _run_qwen_local,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Smoke-test a Gateway backend.")
    p.add_argument(
        "--backend",
        required=True,
        choices=list(_RUNNERS),
        help="Which backend to test: anthropic | modal | qwen-local",
    )
    args = p.parse_args(argv)

    result = _RUNNERS[args.backend]()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
