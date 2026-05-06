"""Runtime matrix probe: fixture-driven cross-runtime comparison.

Runs a normalized task fixture against each healthy runtime and emits comparable JSON:
{runtime_id, success, cost_estimate_usd, latency_ms, output_validity, output, errors}.

DEFAULT IS DRY-RUN. Real execution costs real money — pass --execute to fire.
Per slm-learning-042 step 1; no new training before this lands.

Task shapes (each maps to a fixture in fixtures/<shape>.json):
- trivial-question  : "What is 2+2?" smoke test
- doc-verify        : verify a single claim against repo
- code-edit         : tiny edit to a file (exec gated behind --execute)
- gad-cli-translate : "show me decisions" -> `gad decisions list`

Usage:
    python scripts/runtime/matrix.py --task-shape trivial-question --json
    python scripts/runtime/matrix.py --task-shape doc-verify --execute --json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# We don't import check.py to keep the contract surface small — but we mirror
# its runtime list so a missing runtime here is detected explicitly.
try:
    from .check import RUNTIME_PROBES, probe_runtime  # type: ignore
except ImportError:  # script invoked directly
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check import RUNTIME_PROBES, probe_runtime  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]

# Per-1k-token cost estimates as of 2026-05; treat as floor for dry-run scoring.
COST_PER_1K_INPUT_USD = {
    "claude-code": 0.003,   # Sonnet 4.6 input
    "codex-cli": 0.0025,    # GPT-5 input estimate
    "gemini-cli": 0.00125,  # Gemini 2.x Pro input
    "opencode": 0.0,        # local/free assumed
    "hf-jobs": 0.0,         # we own the spend separately ($0.80-1/hr)
    "local-slm": 0.0,
}
COST_PER_1K_OUTPUT_USD = {
    "claude-code": 0.015,
    "codex-cli": 0.01,
    "gemini-cli": 0.005,
    "opencode": 0.0,
    "hf-jobs": 0.0,
    "local-slm": 0.0,
}

FIXTURES = {
    "trivial-question": {
        "prompt": "What is 2+2? Reply with only the digit.",
        "expected_substring": "4",
        "input_tokens_est": 16,
        "output_tokens_est": 4,
    },
    "doc-verify": {
        "prompt": "Claim: README.md exists at the repo root. Status: verified|refuted|unknown. Reply JSON only.",
        "expected_substring": "verified",
        "input_tokens_est": 64,
        "output_tokens_est": 24,
    },
    "code-edit": {
        "prompt": "Add a trailing newline to README.md if missing. Reply 'ok' when done.",
        "expected_substring": "ok",
        "input_tokens_est": 80,
        "output_tokens_est": 8,
    },
    "gad-cli-translate": {
        "prompt": "Translate to a single gad CLI command: show me decisions for project slm-learning",
        "expected_substring": "gad decisions",
        "input_tokens_est": 48,
        "output_tokens_est": 16,
    },
}


def estimate_cost(runtime_id, fixture):
    cin = COST_PER_1K_INPUT_USD.get(runtime_id, 0.005)
    cout = COST_PER_1K_OUTPUT_USD.get(runtime_id, 0.015)
    return round(
        (fixture["input_tokens_est"] / 1000.0) * cin
        + (fixture["output_tokens_est"] / 1000.0) * cout,
        6,
    )


def execute_fixture(runtime_id, fixture):
    """Stub: real execution is gated behind concrete adapter wiring.

    Returns a tuple (success, output, latency_ms, errors).
    Until vLLM endpoint (SL-T-04-10) and runtime adapters are wired, this raises.
    """
    raise NotImplementedError(
        "Live --execute path requires runtime adapters (SL-T-04-10 vLLM bridge + "
        "per-runtime CLI shells). Re-run without --execute for dry-run scoring."
    )


def matrix_row(runtime_id, fixture, execute):
    health = probe_runtime(*next(p for p in RUNTIME_PROBES if p[0] == runtime_id))
    if health["status"] != "ok":
        return {
            "runtime_id": runtime_id,
            "skipped": True,
            "skip_reason": f"unhealthy: {health['status']}",
            "errors": health["errors"],
        }
    if not execute:
        return {
            "runtime_id": runtime_id,
            "skipped": False,
            "dry_run": True,
            "cost_estimate_usd": estimate_cost(runtime_id, fixture),
            "input_tokens_est": fixture["input_tokens_est"],
            "output_tokens_est": fixture["output_tokens_est"],
            "success": None,
            "latency_ms": None,
            "output_validity": None,
            "output": None,
            "errors": [],
        }
    t0 = time.time()
    try:
        success, output, latency_ms, errors = execute_fixture(runtime_id, fixture)
    except NotImplementedError as exc:
        return {
            "runtime_id": runtime_id,
            "skipped": True,
            "skip_reason": str(exc),
            "errors": [],
        }
    output_valid = bool(output) and (fixture["expected_substring"].lower() in output.lower())
    return {
        "runtime_id": runtime_id,
        "skipped": False,
        "dry_run": False,
        "cost_estimate_usd": estimate_cost(runtime_id, fixture),
        "input_tokens_est": fixture["input_tokens_est"],
        "output_tokens_est": fixture["output_tokens_est"],
        "success": success,
        "latency_ms": latency_ms,
        "output_validity": output_valid,
        "output": output,
        "errors": errors,
        "elapsed_s": round(time.time() - t0, 3),
    }


def main():
    parser = argparse.ArgumentParser(description="Cross-runtime fixture matrix probe.")
    parser.add_argument("--task-shape", required=True, choices=sorted(FIXTURES.keys()))
    parser.add_argument(
        "--runtimes",
        default=None,
        help="Comma-separated runtime ids; defaults to all known runtimes.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually run the fixture against each runtime (spends real money).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout.")
    parser.add_argument(
        "--serving-mode",
        choices=["own", "provider", "mixed"],
        default="provider",
        help="Where CLI is pointed: own (our vLLM endpoint), provider (native), or mixed.",
    )
    parser.add_argument(
        "--served-model",
        default=None,
        help="Adapter/base behind the endpoint (e.g. scrubster/dr-stein-colab-cli).",
    )
    args = parser.parse_args()

    fixture = FIXTURES[args.task_shape]
    if args.runtimes:
        wanted = {r.strip() for r in args.runtimes.split(",") if r.strip()}
        probes = [p for p in RUNTIME_PROBES if p[0] in wanted]
    else:
        probes = RUNTIME_PROBES

    rows = [matrix_row(p[0], fixture, args.execute) for p in probes]
    payload = {
        "schema_version": "slm-learning-runtime-matrix@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_shape": args.task_shape,
        "fixture": fixture,
        "execute": args.execute,
        "serving_mode": args.serving_mode,
        "served_model": args.served_model,
        "rows": rows,
    }

    if args.json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print(f"Matrix @ {payload['generated_at']} task_shape={args.task_shape} execute={args.execute}")
    print("-" * 90)
    print(
        f"{'runtime':<14} {'state':<10} {'cost$':<10} {'lat_ms':<8} {'valid':<6} {'note':<30}"
    )
    print("-" * 90)
    for r in rows:
        if r.get("skipped"):
            print(f"{r['runtime_id']:<14} {'skipped':<10} {'-':<10} {'-':<8} {'-':<6} {r['skip_reason'][:30]:<30}")
            continue
        state = "dry-run" if r.get("dry_run") else ("ok" if r.get("success") else "fail")
        cost = f"{r['cost_estimate_usd']:.4f}"
        lat = "-" if r.get("latency_ms") is None else str(r["latency_ms"])
        valid = "-" if r.get("output_validity") is None else ("yes" if r["output_validity"] else "no")
        print(f"{r['runtime_id']:<14} {state:<10} {cost:<10} {lat:<8} {valid:<6} {'':<30}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
