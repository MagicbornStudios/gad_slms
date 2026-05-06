"""Comparative eval matrix — N models × M benchmarks → one table.

Per operator request 2026-05-06: "I want to have comparative results
to models across the board and frontier models in the same ecosystem."

Runs every declared benchmark (`benchmarks/<name>/manifest.json`)
against every declared model (`scripts/eval/models_to_compare.json`)
and writes a unified results table to `experiments/comparative/
matrix-<date>.{json,md}`.

Models supported (via the OpenAI-compatible interface, no provider lock-in):
- local vLLM endpoint (our v2/math/multitask adapters served by
  scripts/serve/start_v2.sh)
- bare base via local vLLM (no adapter)
- remote OpenAI-compat endpoints (HF Inference, vLLM hosted, OpenRouter)
- frontier APIs (Anthropic Claude / OpenAI / Google Gemini) via their
  OpenAI-compat shims or direct SDKs

Each row of the output table:

    | model_id | benchmark | n | score | latency_p50 | cost_usd | evidence_tier |

Cost tracking: per-call estimated_cost from `scripts/eval/model_costs.json`
or zero for local. Wall-time captured from inference loop.

Per slm-learning-070/071: comparative results must be evidence-tiered.
T1 = single-run anecdote (n=10). T2 = multi-run with baseline (n=30+).
T3 = vs published baseline at scale. T4 = reproduced externally.

Usage:

    # Run all declared benchmarks against all declared models
    .venv-gpu/Scripts/python.exe scripts/eval/run_comparative_matrix.py \\
        --models scripts/eval/models_to_compare.json \\
        --benchmarks benchmarks/ \\
        --out experiments/comparative/matrix-2026-05-06.json

    # Run a single benchmark against a single model (smoke)
    .venv-gpu/Scripts/python.exe scripts/eval/run_comparative_matrix.py \\
        --benchmark gad_tools_v2 \\
        --model local-v2 \\
        --out experiments/comparative/smoke.json

    # Skip frontier rows (cost control)
    .venv-gpu/Scripts/python.exe scripts/eval/run_comparative_matrix.py \\
        --no-frontier

Decision refs: slm-learning-053, slm-learning-070, slm-learning-071,
slm-learning-085 (model gateway), slm-learning-086 (data flywheel).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def load_models(path: Path) -> list[dict]:
    if not path.exists():
        # Default model set if file doesn't exist yet
        return DEFAULT_MODELS
    return json.loads(path.read_text(encoding="utf-8"))


def load_benchmarks(benchmarks_root: Path, only: str | None = None) -> list[dict]:
    out = []
    for d in sorted(benchmarks_root.iterdir()):
        if not d.is_dir():
            continue
        manifest = d / "manifest.json"
        if not manifest.exists():
            continue
        if only and d.name != only:
            continue
        m = json.loads(manifest.read_text(encoding="utf-8"))
        m["_dir"] = str(d)
        out.append(m)
    return out


# Default model set — comparative axis. Operator edits via
# scripts/eval/models_to_compare.json.
DEFAULT_MODELS = [
    # Local — bare base (no adapter, our floor)
    {
        "model_id": "bare-qwen2.5-1.5b-instruct",
        "kind": "local",
        "endpoint": "http://127.0.0.1:8000/v1/chat/completions",
        "served_name": "Qwen/Qwen2.5-1.5B-Instruct",
        "cost_usd_per_1k_tokens_out": 0.0,
        "tier": "Tier 0 local",
    },
    # Local — our specialists (when served via scripts/serve/start_v2.sh)
    {
        "model_id": "scrubster/dr-stein-stage25-qwen15-instruct-v2",
        "kind": "local",
        "endpoint": "http://127.0.0.1:8000/v1/chat/completions",
        "served_name": "adapter",
        "cost_usd_per_1k_tokens_out": 0.0,
        "tier": "Tier 0 local",
        "notes": "Currently canonical for cli_translator lane (30/30 GAD-tools)",
    },
    {
        "model_id": "scrubster/dr-stein-colab-qwen15-math-5k",
        "kind": "local",
        "endpoint": "http://127.0.0.1:8000/v1/chat/completions",
        "served_name": "adapter",
        "cost_usd_per_1k_tokens_out": 0.0,
        "tier": "Tier 0 local",
        "notes": "Currently canonical for math_reasoner lane (25/50 GSM8K)",
    },
    # Remote (when REMOTE_ENDPOINT env is set)
    {
        "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "kind": "remote-openai-compat",
        "endpoint_env": "GAD_REMOTE_ENDPOINT",
        "served_name_env": "GAD_REMOTE_MODEL",
        "cost_usd_per_1k_tokens_out": 0.001,
        "tier": "Tier 1 remote",
        "notes": "Phase 04 SL-T-04-06 target; populate when remote serving is live",
    },
    # Frontier — opt-in via --frontier (cost control)
    {
        "model_id": "claude-opus-4-7",
        "kind": "frontier-anthropic",
        "cost_usd_per_1k_tokens_out": 0.075,
        "tier": "frontier",
        "notes": "Costly. Use with --frontier explicitly.",
    },
    {
        "model_id": "claude-sonnet-4-6",
        "kind": "frontier-anthropic",
        "cost_usd_per_1k_tokens_out": 0.015,
        "tier": "frontier",
    },
    {
        "model_id": "claude-haiku-4-5",
        "kind": "frontier-anthropic",
        "cost_usd_per_1k_tokens_out": 0.005,
        "tier": "frontier",
        "notes": "Already used as distillation teacher per slm-learning-019",
    },
    {
        "model_id": "gpt-5",
        "kind": "frontier-openai",
        "cost_usd_per_1k_tokens_out": 0.015,
        "tier": "frontier",
    },
    {
        "model_id": "gemini-2.0-pro",
        "kind": "frontier-google",
        "cost_usd_per_1k_tokens_out": 0.0125,
        "tier": "frontier",
    },
]


def call_openai_compat(endpoint: str, model: str, prompt: str,
                        system: str | None = None,
                        max_tokens: int = 256, timeout: int = 60,
                        api_key: str | None = None) -> tuple[str, int, int]:
    """Returns (response_text, prompt_tokens, completion_tokens)."""
    msgs: list[dict[str, str]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": model,
        "messages": msgs,
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    text = payload["choices"][0]["message"]["content"].strip()
    usage = payload.get("usage", {})
    return text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def resolve_model_endpoint(model: dict) -> tuple[str, str, str | None]:
    """Returns (endpoint_url, served_name, api_key)."""
    kind = model.get("kind", "local")
    if kind == "local":
        return model["endpoint"], model.get("served_name", "adapter"), None
    if kind == "remote-openai-compat":
        ep = os.environ.get(model.get("endpoint_env", "GAD_REMOTE_ENDPOINT"), "")
        nm = os.environ.get(model.get("served_name_env", "GAD_REMOTE_MODEL"), "")
        return ep, nm, os.environ.get("GAD_REMOTE_API_KEY")
    if kind == "frontier-anthropic":
        ep = os.environ.get("GAD_ANTHROPIC_ENDPOINT", "https://api.anthropic.com/v1/messages")
        return ep, model["model_id"], os.environ.get("ANTHROPIC_API_KEY")
    if kind == "frontier-openai":
        ep = os.environ.get("GAD_OPENAI_ENDPOINT", "https://api.openai.com/v1/chat/completions")
        return ep, model["model_id"], os.environ.get("OPENAI_API_KEY")
    if kind == "frontier-google":
        # Google's OpenAI-compat shim:
        ep = os.environ.get("GAD_GOOGLE_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
        return ep, model["model_id"], os.environ.get("GOOGLE_API_KEY")
    raise ValueError(f"unknown model kind: {kind}")


def load_benchmark_cases(benchmark: dict) -> list[dict]:
    """Each benchmark provides a {prompt, expected} list. Schemas vary."""
    name = benchmark["name"]
    src = benchmark.get("source_dataset", "")

    if name == "gad_tools_v2":
        # promptfoo yaml -> tests
        try:
            import yaml
        except ImportError:
            print("[matrix] WARN: pyyaml missing, gad_tools_v2 skipped")
            return []
        path = ROOT / src
        if not path.exists():
            return []
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases = []
        for t in data.get("tests", []):
            inp = (t.get("vars") or {}).get("input") or ""
            asserts = t.get("assert", [])
            expected = ""
            for a in asserts:
                if a.get("type") == "contains":
                    expected = a.get("value", "")
                    break
            cases.append({
                "prompt": inp,
                "expected_contains": expected,
                "system": "You are an assistant. Translate the user's request "
                          "into a single gad CLI command. Output only the command "
                          "on one line.",
            })
        return cases

    if name == "doc_verifier":
        path = ROOT / src
        if not path.exists():
            return []
        cases = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                cases.append({
                    "prompt": row["instruction"],
                    "system": row.get("system_prompt", ""),
                    "expected_json_status": json.loads(row["command"]).get("status"),
                })
        return cases

    # gsm8k / humaneval / swebench — delegate to existing scripts when called
    # standalone. The matrix runner can't fully wrap them yet.
    return []


def score_case(case: dict, response: str) -> bool:
    if "expected_contains" in case and case["expected_contains"]:
        return case["expected_contains"] in response
    if "expected_json_status" in case and case["expected_json_status"]:
        try:
            # Find first JSON object in response
            s = response.strip()
            if s.startswith("```"):
                s = s.strip("`").strip()
                if s.startswith("json"):
                    s = s[4:].strip()
            start = s.find("{")
            end = s.rfind("}")
            if start == -1 or end == -1:
                return False
            parsed = json.loads(s[start:end + 1])
            return parsed.get("status") == case["expected_json_status"]
        except (json.JSONDecodeError, ValueError):
            return False
    return False


def run_one(model: dict, benchmark: dict, *, limit: int | None = None,
            max_tokens: int = 256, dry_run: bool = False) -> dict:
    cases = load_benchmark_cases(benchmark)
    if limit:
        cases = cases[:limit]
    if not cases:
        return {
            "model_id": model["model_id"],
            "benchmark": benchmark["name"],
            "n": 0,
            "score": None,
            "status": "no_cases_loadable",
            "reason": (f"benchmark {benchmark['name']} has no loader in "
                       f"run_comparative_matrix.load_benchmark_cases (yet)"),
        }

    endpoint, served_name, api_key = resolve_model_endpoint(model)
    if not endpoint:
        return {
            "model_id": model["model_id"],
            "benchmark": benchmark["name"],
            "n": len(cases),
            "score": None,
            "status": "endpoint_not_configured",
            "reason": f"set the env var for {model.get('kind')} kind",
        }

    if dry_run:
        return {
            "model_id": model["model_id"],
            "benchmark": benchmark["name"],
            "n": len(cases),
            "score": None,
            "status": "dry_run",
            "endpoint": endpoint,
        }

    passed = 0
    latencies: list[float] = []
    total_completion_tokens = 0
    failures: list[dict] = []
    for i, case in enumerate(cases):
        try:
            t0 = time.time()
            text, _pt, ct = call_openai_compat(
                endpoint, served_name,
                case["prompt"], system=case.get("system"),
                max_tokens=max_tokens, api_key=api_key,
            )
            wall = time.time() - t0
            latencies.append(wall)
            total_completion_tokens += ct
            if score_case(case, text):
                passed += 1
            elif len(failures) < 5:
                failures.append({"i": i, "prompt": case["prompt"][:100],
                                 "response": text[:200]})
        except (urllib.error.URLError, KeyError, ValueError) as e:
            return {
                "model_id": model["model_id"],
                "benchmark": benchmark["name"],
                "n": len(cases),
                "score": None,
                "status": "error",
                "reason": f"{type(e).__name__}: {e}",
                "endpoint": endpoint,
            }

    score = round(passed / len(cases), 3) if cases else 0.0
    cost = round(
        total_completion_tokens / 1000 * (model.get("cost_usd_per_1k_tokens_out") or 0),
        4,
    )
    sample_lat = sorted(latencies)
    p50 = sample_lat[len(sample_lat) // 2] if sample_lat else 0.0

    evidence_tier = "T1" if len(cases) < 30 else "T2"

    return {
        "model_id": model["model_id"],
        "benchmark": benchmark["name"],
        "kind": model.get("kind"),
        "tier": model.get("tier"),
        "n": len(cases),
        "passed": passed,
        "score": score,
        "latency_p50_s": round(p50, 2),
        "latency_total_s": round(sum(latencies), 2),
        "cost_usd": cost,
        "evidence_tier": evidence_tier,
        "endpoint_used": endpoint,
        "served_name": served_name,
        "first_failures": failures,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path,
                        default=ROOT / "scripts" / "eval" / "models_to_compare.json")
    parser.add_argument("--benchmarks", type=Path,
                        default=ROOT / "benchmarks")
    parser.add_argument("--benchmark", type=str, default=None,
                        help="Single benchmark name (smoke mode)")
    parser.add_argument("--model", type=str, default=None,
                        help="Single model_id (smoke mode)")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit cases per benchmark (smoke)")
    parser.add_argument("--no-frontier", action="store_true",
                        help="Skip rows with kind=frontier-* (cost control)")
    parser.add_argument("--no-remote", action="store_true",
                        help="Skip remote rows (no remote endpoint configured)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List rows that would run; no inference")
    args = parser.parse_args()

    models = load_models(args.models)
    benchmarks = load_benchmarks(args.benchmarks, only=args.benchmark)

    if args.model:
        models = [m for m in models if m["model_id"] == args.model]
    if args.no_frontier:
        models = [m for m in models if not str(m.get("kind", "")).startswith("frontier-")]
    if args.no_remote:
        models = [m for m in models if not str(m.get("kind", "")).startswith("remote-")]

    print(f"[matrix] {len(models)} model(s) x {len(benchmarks)} benchmark(s)")
    rows = []
    for m in models:
        for b in benchmarks:
            print(f"[matrix] {m['model_id']} x {b['name']} ...")
            row = run_one(m, b, limit=args.limit, dry_run=args.dry_run)
            rows.append(row)
            score_disp = f"{row['score']:.3f}" if row.get("score") is not None else row.get("status", "?")
            print(f"  -> {score_disp}  (n={row.get('n')} cost=${row.get('cost_usd', 0)})")

    summary = {
        "schema_v": 1,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "n_models": len(models),
        "n_benchmarks": len(benchmarks),
        "rows": rows,
        "decision_refs": ["slm-learning-053", "slm-learning-070",
                          "slm-learning-071", "slm-learning-085"],
    }

    out = args.out or (
        ROOT / "experiments" / "comparative" /
        f"matrix-{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H%M')}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n[matrix] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
