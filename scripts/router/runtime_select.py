"""Rule-based runtime router with decision logging.

Phase 1 of SL-T-04-08: pure rules + telemetry. NO ML yet — collect labels first
(decision slm-learning-039). Phase 2 will train a logistic/SVM classifier on the
JSONL stream this writer emits.

Decision log schema (per directive + slm-learning-041):
    {
      "ts": "<ISO8601>",
      "task": "<freeform task description>",
      "task_shape": "<canonical shape id>",
      "chosen_runtime": "<runtime_id>",
      "chosen_agent": "<agent_id or null>",
      "chosen_model": "<model id or null>",
      "reasons": ["<rule-id>: <explanation>", ...],
      "outcome": "<success|failure|unknown>",
      "cost_estimate_usd": <float>,
      "latency_ms": <int or null>,
      "project_id": "<project>",
      "schema_version": "slm-learning-routing@1"
    }

Output stream: .planning/.gad-log/<YYYY-MM-DD>-routing.jsonl
This co-locates with the gad-monorepo schema (commit 60d0a948) so framework
phase 140 can consume the same file.

Usage:
    # decide route only (dry-run)
    python scripts/router/runtime_select.py \
        --task "verify claim that scripts/runtime/check.py exists" \
        --task-shape doc-verify --json

    # decide + log
    python scripts/router/runtime_select.py \
        --task "edit README.md to add a TOC" \
        --task-shape code-edit --log

    # log an outcome after the fact
    python scripts/router/runtime_select.py \
        --record-outcome <decision_id> --outcome success --latency-ms 4200
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
GAD_LOG_DIR = REPO_ROOT / ".planning" / ".gad-log"
PROJECT_ID = "slm-learning"
SCHEMA_VERSION = "slm-learning-routing@1"

TASK_SHAPES = [
    "trivial-question",   # smoke / arithmetic / "is this true"
    "doc-verify",         # claim verification
    "code-edit",          # multi-file or local edit
    "code-explain",       # explain code without changing it
    "gad-cli-translate",  # natural lang -> gad CLI command
    "research-deep",      # multi-source synthesis
    "summary",            # codebase / repo / session summary
    "tool-use-pair",      # specialist GAD tool-call
    "math-reasoning",     # math word problems
    "unknown",
]

# (rule_id, predicate(task_shape, task_text) -> bool, route).
# Ordered by specificity — first match wins. `route` is a dict; merged into output.
def _kw(text, *needles):
    t = text.lower()
    return any(n in t for n in needles)


RULES = [
    (
        "R01-trivial-haiku",
        lambda shape, text: shape == "trivial-question",
        {
            "chosen_runtime": "claude-code",
            "chosen_agent": None,
            "chosen_model": "claude-haiku-4-5",
            "reasons": ["trivial questions go to cheapest frontier (haiku-4-5)"],
            "cost_estimate_usd": 0.0001,
        },
    ),
    (
        "R02-doc-verify-local-slm",
        lambda shape, text: shape == "doc-verify",
        {
            "chosen_runtime": "local-slm",
            "chosen_agent": "gad-doc-verifier",
            "chosen_model": "scrubster/dr-stein-doc-verifier",  # not yet trained — falls through to fallback
            "reasons": [
                "doc-verify is first-wave SLM target (decision slm-learning-038)",
                "fallback to claude-code if local-slm endpoint unhealthy",
            ],
            "cost_estimate_usd": 0.0,
            "fallback_runtime": "claude-code",
            "fallback_agent": "gad-doc-verifier",
        },
    ),
    (
        "R03-cli-translate-local-cli-adapter",
        lambda shape, text: shape == "gad-cli-translate",
        {
            "chosen_runtime": "local-slm",
            "chosen_agent": "gad-cli-translator",
            "chosen_model": "scrubster/dr-stein-colab-cli",  # adapter v2 30/30
            "reasons": [
                "CLI translation saturated at 30/30 on dr-stein-colab-cli adapter",
                "adapter live on HF Hub; falls back to claude-code on serving failure",
            ],
            "cost_estimate_usd": 0.0,
            "fallback_runtime": "claude-code",
            "fallback_agent": None,
        },
    ),
    (
        "R04-math-reasoning-local-slm",
        lambda shape, text: shape == "math-reasoning",
        {
            "chosen_runtime": "local-slm",
            "chosen_agent": None,
            "chosen_model": "scrubster/dr-stein-colab-math-1p5b",
            "reasons": [
                "math 1.5B adapter at 25/50 GSM8K (decision slm-learning-035)",
                "fallback to claude-code for problems where SLM falters",
            ],
            "cost_estimate_usd": 0.0,
            "fallback_runtime": "claude-code",
        },
    ),
    (
        "R05-tool-use-claude-then-7b",
        lambda shape, text: shape == "tool-use-pair",
        {
            "chosen_runtime": "claude-code",
            "chosen_agent": None,
            "chosen_model": "claude-sonnet-4-6",
            "reasons": [
                "tool-use 7B coder not yet trained (SL-T-04-06 gated)",
                "use claude-code until 7B QLoRA lands",
            ],
            "cost_estimate_usd": 0.005,
        },
    ),
    (
        "R06-research-deep-frontier",
        lambda shape, text: shape == "research-deep",
        {
            "chosen_runtime": "claude-code",
            "chosen_agent": None,
            "chosen_model": "claude-opus-4-7",
            "reasons": [
                "deep research deferred from local SLM (decision slm-learning-038)",
                "frontier opus reserved for synthesis-heavy tasks",
            ],
            "cost_estimate_usd": 0.05,
        },
    ),
    (
        "R07-code-edit-default",
        lambda shape, text: shape in ("code-edit", "code-explain", "summary"),
        {
            "chosen_runtime": "claude-code",
            "chosen_agent": None,
            "chosen_model": "claude-sonnet-4-6",
            "reasons": [
                "code-edit/code-explain/summary default to claude-code sonnet",
            ],
            "cost_estimate_usd": 0.01,
        },
    ),
    (
        "R99-fallback",
        lambda shape, text: True,
        {
            "chosen_runtime": "claude-code",
            "chosen_agent": None,
            "chosen_model": "claude-sonnet-4-6",
            "reasons": ["fallback: no rule matched"],
            "cost_estimate_usd": 0.01,
        },
    ),
]


def decide(task_text, task_shape):
    if task_shape not in TASK_SHAPES:
        task_shape = "unknown"
    for rule_id, pred, route in RULES:
        if pred(task_shape, task_text):
            decision = {
                "rule_id": rule_id,
                "task": task_text,
                "task_shape": task_shape,
                "chosen_runtime": route["chosen_runtime"],
                "chosen_agent": route.get("chosen_agent"),
                "chosen_model": route.get("chosen_model"),
                "reasons": [f"{rule_id}: {r}" for r in route["reasons"]],
                "fallback_runtime": route.get("fallback_runtime"),
                "fallback_agent": route.get("fallback_agent"),
                "cost_estimate_usd": route["cost_estimate_usd"],
                "latency_ms": None,
                "outcome": "unknown",
                "project_id": PROJECT_ID,
                "schema_version": SCHEMA_VERSION,
            }
            decision["decision_id"] = (
                hashlib.sha256(
                    f"{time.time_ns()}-{task_text}-{task_shape}".encode()
                ).hexdigest()[:16]
            )
            decision["ts"] = datetime.now(timezone.utc).isoformat()
            return decision
    raise RuntimeError("router fell off the end (no fallback hit) — should never happen")


def log_path():
    GAD_LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return GAD_LOG_DIR / f"{today}-routing.jsonl"


def append_log(record):
    with log_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")


def find_decision(decision_id):
    """Walk recent routing logs in reverse to find a decision_id."""
    GAD_LOG_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(GAD_LOG_DIR.glob("*-routing.jsonl"), reverse=True):
        try:
            with path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            continue
        for i in range(len(lines) - 1, -1, -1):
            try:
                rec = json.loads(lines[i])
            except json.JSONDecodeError:
                continue
            if rec.get("decision_id") == decision_id:
                return path, i, lines
    return None, None, None


def record_outcome(decision_id, outcome, latency_ms):
    path, idx, lines = find_decision(decision_id)
    if path is None:
        raise SystemExit(f"decision {decision_id} not found in routing log")
    rec = json.loads(lines[idx])
    rec["outcome"] = outcome
    rec["latency_ms"] = latency_ms
    rec["outcome_recorded_at"] = datetime.now(timezone.utc).isoformat()
    lines[idx] = json.dumps(rec, separators=(",", ":")) + "\n"
    with path.open("w", encoding="utf-8") as f:
        f.writelines(lines)
    return rec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", help="Task text to route.")
    parser.add_argument("--task-shape", default="unknown", choices=TASK_SHAPES)
    parser.add_argument("--log", action="store_true", help="Append decision to routing JSONL.")
    parser.add_argument("--json", action="store_true", help="Emit decision JSON to stdout.")
    parser.add_argument("--record-outcome", help="decision_id to update with --outcome / --latency-ms.")
    parser.add_argument("--outcome", choices=["success", "failure", "unknown"])
    parser.add_argument("--latency-ms", type=int, default=None)
    args = parser.parse_args()

    if args.record_outcome:
        rec = record_outcome(args.record_outcome, args.outcome or "unknown", args.latency_ms)
        if args.json:
            json.dump(rec, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            print(f"recorded outcome={rec['outcome']} latency_ms={rec['latency_ms']} for {args.record_outcome}")
        return 0

    if not args.task:
        parser.error("--task is required unless --record-outcome is used")

    decision = decide(args.task, args.task_shape)
    if args.log:
        append_log(decision)
    if args.json:
        json.dump(decision, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"[{decision['decision_id']}] {decision['rule_id']}")
        print(f"  task_shape : {decision['task_shape']}")
        print(f"  runtime    : {decision['chosen_runtime']}")
        print(f"  agent      : {decision['chosen_agent']}")
        print(f"  model      : {decision['chosen_model']}")
        print(f"  cost_est$  : {decision['cost_estimate_usd']}")
        print(f"  reasons    :")
        for r in decision["reasons"]:
            print(f"    - {r}")
        if args.log:
            print(f"  logged to  : {log_path()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
