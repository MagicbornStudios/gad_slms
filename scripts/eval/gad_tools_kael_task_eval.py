"""GAD-Tools / Kael-Task eval — domain-specific eval for GAD CLI tool use.

Per slm-learning-103 (compare-and-compete) and 2026-05-09 operator direction to
include Hermes/NousCoder models as first-class comparators. HumanEval + MBPP are
upstream and shared; this eval is the one domain area where kael-14b adapters can
demonstrate dominance over Hermes/NousCoder.

Task files: slm_learning/data/eval/kael_task_eval/<id>.json
Schema per each task file:
    {
      "schema_v": 1,
      "id": str,              # e.g. "kt-001"
      "title": str,
      "category": str,        # gad-handoff-management, gad-planning-query, gad-mlops, ...
      "difficulty": str,      # easy | medium | hard
      "prompt": str,
      "expected_tool_calls": [...],
      "expected_outputs": {...},
      "eval_rubric": {
        "tool_call_correctness": {"weight": float, "criteria": [...]},
        "output_relevance": {"weight": float, "criteria": [...]}
      }
    }

Scoring:
    score = tool_call_correctness (0-1) * tc_weight
          + output_relevance      (0-1) * or_weight
    where tc_weight + or_weight = 1.0 per rubric entry.

Output: slm_learning/runs/eval/gad_tools_kael_task/<run_id>/results.json

Run (DO NOT FIRE until handoff is claimed and rung endpoints are live):
    .venv/Scripts/python.exe scripts/eval/gad_tools_kael_task_eval.py \\
        --rungs nous-hermes-4-14b,nous-nouscoder-14b,qwen-2.5-coder-14b-base \\
        --task-dir data/eval/kael_task_eval \\
        --out-dir runs/eval/gad_tools_kael_task \\
        --judge-model claude-haiku-4-5 \\
        [--dry-run]

Decision refs: slm-learning-097, 103, 210.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import uuid
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TASK_DIR = REPO_ROOT / "data" / "eval" / "kael_task_eval"
DEFAULT_OUT_DIR = REPO_ROOT / "runs" / "eval" / "gad_tools_kael_task"
RUNG_REGISTRY = REPO_ROOT / "data" / "registry" / "benchmark_target_rungs.toml"
GATEWAY_SCRIPT = REPO_ROOT / "scripts" / "gateway" / "router.py"

# ---------------------------------------------------------------------------
# Rung metadata — matches benchmark_target_rungs.toml comparator rungs
# ---------------------------------------------------------------------------
RUNG_META: dict[str, dict[str, Any]] = {
    "nous-hermes-4-14b": {
        "hf_id": "NousResearch/Hermes-3-Llama-3.1-8B",
        "serving": "modal_h100",
        "estimated_cost_usd": 3.0,
        "task_shape": "tool-action",
    },
    "nous-nouscoder-14b": {
        "hf_id": "NousResearch/NousCoder-14B",
        "serving": "modal_h100",
        "estimated_cost_usd": 3.0,
        "task_shape": "code-generation",
    },
    "nous-hermes-4-70b": {
        "hf_id": "NousResearch/Hermes-3-Llama-3.1-8B",
        "serving": "modal_h100x2",
        "estimated_cost_usd": 6.0,
        "task_shape": "tool-action",
    },
    "qwen-2.5-coder-7b-stein-canonical": {
        "hf_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "serving": "modal_a100",
        "estimated_cost_usd": 1.0,
        "task_shape": "code-generation",
    },
    "qwen-2.5-coder-14b-base": {
        "hf_id": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "serving": "modal_a100",
        "estimated_cost_usd": 2.0,
        "task_shape": "code-generation",
    },
}


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

def load_tasks(task_dir: Path) -> list[dict]:
    """Load all .json task files from the kael_task_eval directory."""
    tasks = []
    for path in sorted(task_dir.glob("*.json")):
        try:
            with path.open() as f:
                task = json.load(f)
            if task.get("schema_v") != 1:
                print(f"[WARN] {path.name}: unexpected schema_v={task.get('schema_v')}, skipping")
                continue
            tasks.append(task)
        except json.JSONDecodeError as e:
            print(f"[ERROR] {path.name}: JSON parse error: {e}", file=sys.stderr)
    return tasks


# ---------------------------------------------------------------------------
# Gateway call
# ---------------------------------------------------------------------------

def call_gateway(rung_slug: str, prompt: str, dry_run: bool = False) -> dict:
    """Route a prompt through the GAD gateway router and return the response.

    In dry-run mode, returns a stub response without hitting any API.
    In live mode, imports and calls the gateway router directly via Python
    (avoids subprocess overhead for 30-50 prompts per rung).
    """
    if dry_run:
        return {
            "model": rung_slug,
            "content": f"[DRY RUN] stub response for rung={rung_slug}",
            "tool_calls": [],
            "latency_ms": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": 0.0,
        }

    # Live path — import gateway router
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from gateway.router import route  # type: ignore[import]
        meta = RUNG_META.get(rung_slug, {})
        task_shape = meta.get("task_shape", "tool-action")
        result = route(task_shape=task_shape, prompt=prompt, model_override=rung_slug)
        return {
            "model": rung_slug,
            "content": result.get("content", ""),
            "tool_calls": result.get("tool_calls", []),
            "latency_ms": result.get("latency_ms", 0),
            "tokens_in": result.get("tokens_in", 0),
            "tokens_out": result.get("tokens_out", 0),
            "cost_usd": result.get("cost_usd", 0.0),
        }
    except ImportError as e:
        raise RuntimeError(
            f"Gateway router not importable from {REPO_ROOT}/scripts/gateway/router.py: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Scoring — LLM-as-judge
# ---------------------------------------------------------------------------

def score_response(
    task: dict,
    response: dict,
    judge_model: str,
    dry_run: bool = False,
) -> dict[str, float]:
    """Judge tool_call_correctness and output_relevance for one response.

    Scoring is delegated to an LLM judge (claude-haiku-4-5 by default) that
    reads the rubric criteria and returns 0.0-1.0 per axis.

    In dry-run mode, returns mid-range stubs so aggregation logic can be
    exercised without API spend.
    """
    rubric = task.get("eval_rubric", {})
    tc_rubric = rubric.get("tool_call_correctness", {"weight": 0.6, "criteria": []})
    or_rubric = rubric.get("output_relevance", {"weight": 0.4, "criteria": []})

    if dry_run:
        return {
            "tool_call_correctness": 0.5,
            "output_relevance": 0.5,
            "tc_weight": tc_rubric.get("weight", 0.6),
            "or_weight": or_rubric.get("weight", 0.4),
            "composite": 0.5,
            "judge": "dry-run-stub",
        }

    # Build judge prompt
    judge_prompt = (
        "You are a strict evaluator. Score the following model response on two axes.\n\n"
        f"TASK: {task['prompt']}\n\n"
        f"EXPECTED TOOL CALLS: {json.dumps(task.get('expected_tool_calls', []), indent=2)}\n\n"
        f"EXPECTED OUTPUTS: {json.dumps(task.get('expected_outputs', {}), indent=2)}\n\n"
        f"MODEL RESPONSE:\n{response.get('content', '')}\n\n"
        f"MODEL TOOL CALLS: {json.dumps(response.get('tool_calls', []), indent=2)}\n\n"
        "RUBRIC:\n"
        f"  tool_call_correctness criteria: {tc_rubric.get('criteria', [])}\n"
        f"  output_relevance criteria: {or_rubric.get('criteria', [])}\n\n"
        "Return a JSON object with exactly these keys:\n"
        '  {"tool_call_correctness": <0.0-1.0>, "output_relevance": <0.0-1.0>, '
        '"reasoning": "<one sentence>"}\n'
        "No other text."
    )

    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from gateway.router import route  # type: ignore[import]
        judge_result = route(
            task_shape="evaluation",
            prompt=judge_prompt,
            model_override=judge_model,
        )
        raw = judge_result.get("content", "{}")
        # Strip markdown fences if judge wraps in ```json
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        scores = json.loads(raw.strip())
    except Exception as exc:
        print(f"[WARN] judge error for task={task['id']}: {exc}", file=sys.stderr)
        scores = {"tool_call_correctness": 0.0, "output_relevance": 0.0, "reasoning": str(exc)}

    tc_score = float(scores.get("tool_call_correctness", 0.0))
    or_score = float(scores.get("output_relevance", 0.0))
    tc_w = tc_rubric.get("weight", 0.6)
    or_w = or_rubric.get("weight", 0.4)
    composite = tc_score * tc_w + or_score * or_w

    return {
        "tool_call_correctness": tc_score,
        "output_relevance": or_score,
        "tc_weight": tc_w,
        "or_weight": or_w,
        "composite": composite,
        "reasoning": scores.get("reasoning", ""),
        "judge": judge_model,
    }


# ---------------------------------------------------------------------------
# Per-rung eval loop
# ---------------------------------------------------------------------------

def eval_rung(
    rung_slug: str,
    tasks: list[dict],
    judge_model: str,
    dry_run: bool = False,
) -> dict:
    """Evaluate all tasks for one rung. Returns a per-rung result dict."""
    rows = []
    total_cost = 0.0

    for task in tasks:
        print(f"  [{rung_slug}] task={task['id']} ({task['title'][:50]})")
        try:
            response = call_gateway(rung_slug, task["prompt"], dry_run=dry_run)
        except RuntimeError as e:
            print(f"    [ERROR] gateway call failed: {e}", file=sys.stderr)
            response = {"model": rung_slug, "content": "", "tool_calls": [], "cost_usd": 0.0}

        scores = score_response(task, response, judge_model, dry_run=dry_run)
        total_cost += response.get("cost_usd", 0.0)

        rows.append(
            {
                "task_id": task["id"],
                "title": task["title"],
                "category": task.get("category", ""),
                "difficulty": task.get("difficulty", ""),
                "response_content": response.get("content", "")[:500],  # truncate for log
                "tool_calls": response.get("tool_calls", []),
                "tool_call_correctness": scores["tool_call_correctness"],
                "output_relevance": scores["output_relevance"],
                "composite_score": scores["composite"],
                "judge_reasoning": scores.get("reasoning", ""),
                "latency_ms": response.get("latency_ms", 0),
                "tokens_in": response.get("tokens_in", 0),
                "tokens_out": response.get("tokens_out", 0),
                "cost_usd": response.get("cost_usd", 0.0),
            }
        )

    n = len(rows)
    if n == 0:
        agg = {"mean_composite": 0.0, "mean_tc": 0.0, "mean_or": 0.0}
    else:
        agg = {
            "mean_composite": sum(r["composite_score"] for r in rows) / n,
            "mean_tool_call_correctness": sum(r["tool_call_correctness"] for r in rows) / n,
            "mean_output_relevance": sum(r["output_relevance"] for r in rows) / n,
            "n_tasks": n,
            "total_cost_usd": round(total_cost, 4),
        }

    return {
        "rung_slug": rung_slug,
        "aggregated": agg,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GAD-Tools Kael-Task eval — domain-specific tool-use benchmark"
    )
    parser.add_argument(
        "--rungs",
        default="nous-hermes-4-14b,nous-nouscoder-14b,qwen-2.5-coder-14b-base",
        help="Comma-separated rung slugs from RUNG_META (default: 14B comparator set)",
    )
    parser.add_argument(
        "--task-dir",
        type=Path,
        default=DEFAULT_TASK_DIR,
        help="Directory containing kael_task_eval/*.json task files",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Root output dir; results land in <out_dir>/<run_id>/results.json",
    )
    parser.add_argument(
        "--judge-model",
        default="claude-haiku-4-5",
        help="Model id for the LLM-as-judge scorer (default: claude-haiku-4-5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip all API calls; produce stub results to verify pipeline shape",
    )
    parser.add_argument(
        "--cost-cap",
        type=float,
        default=10.0,
        help="Abort if cumulative cost exceeds this USD amount (default: $10)",
    )

    args = parser.parse_args(argv)

    rung_slugs = [s.strip() for s in args.rungs.split(",") if s.strip()]
    task_dir: Path = args.task_dir
    out_dir: Path = args.out_dir

    # Validate
    if not task_dir.exists():
        print(f"[ERROR] Task dir not found: {task_dir}", file=sys.stderr)
        return 1

    tasks = load_tasks(task_dir)
    if not tasks:
        print(f"[ERROR] No task files found in {task_dir}", file=sys.stderr)
        return 1

    print(f"Loaded {len(tasks)} tasks from {task_dir}")
    print(f"Rungs: {rung_slugs}")
    if args.dry_run:
        print("[DRY RUN] No API calls will be made.")

    # Run ID
    run_id = f"kt-eval-{dt.datetime.utcnow().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    all_rung_results = []
    cumulative_cost = 0.0

    for rung_slug in rung_slugs:
        if rung_slug not in RUNG_META:
            print(f"[WARN] Unknown rung slug '{rung_slug}' — not in RUNG_META; skipping")
            continue

        print(f"\n=== Rung: {rung_slug} ===")
        result = eval_rung(rung_slug, tasks, args.judge_model, dry_run=args.dry_run)
        all_rung_results.append(result)
        cumulative_cost += result["aggregated"].get("total_cost_usd", 0.0)

        print(
            f"  mean_composite={result['aggregated']['mean_composite']:.3f}  "
            f"cost_so_far=${cumulative_cost:.4f}"
        )

        if cumulative_cost > args.cost_cap:
            print(
                f"[ABORT] Cumulative cost ${cumulative_cost:.4f} exceeded cap ${args.cost_cap:.2f}",
                file=sys.stderr,
            )
            break

    # Write results
    output = {
        "schema_v": 1,
        "run_id": run_id,
        "created_at": dt.datetime.utcnow().isoformat() + "Z",
        "dry_run": args.dry_run,
        "judge_model": args.judge_model,
        "n_tasks": len(tasks),
        "cost_cap_usd": args.cost_cap,
        "total_cost_usd": round(cumulative_cost, 4),
        "rung_results": all_rung_results,
        "decision_refs": ["slm-learning-097", "slm-learning-103", "slm-learning-210"],
    }

    results_path = run_dir / "results.json"
    with results_path.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults written to: {results_path}")
    print(f"Total cost: ${cumulative_cost:.4f}")

    # Summary table
    print("\n| Rung | Mean Composite | Mean TC Correctness | Mean OR | Cost |")
    print("|---|---|---|---|---|")
    for r in all_rung_results:
        agg = r["aggregated"]
        print(
            f"| {r['rung_slug']} "
            f"| {agg.get('mean_composite', 0):.3f} "
            f"| {agg.get('mean_tool_call_correctness', 0):.3f} "
            f"| {agg.get('mean_output_relevance', 0):.3f} "
            f"| ${agg.get('total_cost_usd', 0):.4f} |"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
