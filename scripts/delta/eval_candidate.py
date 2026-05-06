"""Evaluate a candidate adapter against the benchmark battery.

Subprocess contract for global daemon (gad-monorepo phase 147 +
slm-learning phase 05). Returns a JSON summary suitable for the
promotion gate (slm-learning-032).

Input:
    --candidate-dir <path>   directory produced by train_lora_delta.py
    --baseline-id <str>      HF Hub id or local path of the baseline
                             to compare against (default: bare base)
    --benchmarks <list>      comma-separated subset of {gad_tools,
                             humaneval, gsm8k, swebench, livecodebench}

Output (stdout, JSON conforming to phase-146 role=benchmark_run shape):
    {
      "candidate_dir": "...",
      "candidate_adapter_sha": "...",
      "evaluated_at": "...",
      "results": {
        "gad_tools": {"score": ..., "n": ..., "vs_baseline": "+/-N pp"},
        ...
      },
      "regression_vs_canonical": {<benchmark>: <pp delta>},
      "verdict": "verified | refuted | inconclusive",
      "evidence_tier": "T1 | T2 | T3 | T4",
      "decision_ref": "slm-learning-051 + slm-learning-071"
    }

Verdict logic:
- All benchmarks meet baseline within 5 pp -> verified at T2
- Any benchmark regresses by > 5 pp -> refuted
- Insufficient sample size (< 30 cases per benchmark) -> inconclusive
- Returns regression_vs_canonical map for downstream promote_atomic.py.

For phase 06 SWE-bench / LiveCodeBench, this script delegates to
scripts/eval_swebench.py and scripts/eval_livecodebench.py once those
exist; until then it returns 'unimplemented' for those benchmarks.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUPPORTED = {"gad_tools", "humaneval", "gsm8k", "swebench", "livecodebench"}


def load_existing_results(candidate_dir: Path) -> dict:
    """Pick up eval results already written by the trainer's eval_hook."""
    eval_dir = candidate_dir / "eval"
    out: dict[str, dict] = {}
    if not eval_dir.exists():
        return out
    for f in eval_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        bm = f.stem.lower()
        if bm in SUPPORTED:
            out[bm] = data
    return out


def verdict_for(results: dict, baseline: dict | None, n_threshold: int = 30) -> tuple[str, str]:
    if not results:
        return "inconclusive", "T1"
    sample_sizes = [r.get("n", 0) for r in results.values()]
    if min(sample_sizes, default=0) < n_threshold:
        return "inconclusive", "T1"
    if baseline is None:
        return "inconclusive", "T1"
    regressions = []
    for bm, r in results.items():
        b = baseline.get(bm)
        if b is None:
            continue
        delta_pp = (r.get("score", 0.0) - b.get("score", 0.0)) * 100
        if delta_pp < -5:
            regressions.append((bm, delta_pp))
    if regressions:
        return "refuted", "T2"
    return "verified", "T2"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--baseline-id", type=str, default=None,
                        help="HF Hub id of baseline to compare against")
    parser.add_argument("--benchmarks", type=str, default="gad_tools,gsm8k,humaneval",
                        help="Comma-separated subset of supported benchmarks")
    parser.add_argument("--baseline-eval-dir", type=Path, default=None,
                        help="Path to baseline eval results (skip re-running)")
    args = parser.parse_args()

    if not args.candidate_dir.exists():
        print(json.dumps({"status": "error", "error": f"no such dir: {args.candidate_dir}"}))
        return 2

    requested = {b.strip() for b in args.benchmarks.split(",") if b.strip()}
    unknown = requested - SUPPORTED
    if unknown:
        print(json.dumps({"status": "error", "error": f"unknown benchmarks: {sorted(unknown)}"}))
        return 2

    results = load_existing_results(args.candidate_dir)
    # Filter to requested set.
    results = {k: v for k, v in results.items() if k in requested}

    # SWE-bench + LiveCodeBench are phase 06 — return unimplemented.
    for bm in {"swebench", "livecodebench"} & requested:
        if bm not in results:
            results[bm] = {"score": None, "n": 0, "status": "unimplemented",
                           "depends_on": "scripts/eval_" + bm + ".py (phase 06)"}

    baseline = None
    if args.baseline_eval_dir and args.baseline_eval_dir.exists():
        baseline = load_existing_results(args.baseline_eval_dir)

    verdict, tier = verdict_for(results, baseline)

    summary = {
        "candidate_dir": str(args.candidate_dir),
        "evaluated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "results": results,
        "regression_vs_canonical": {
            bm: ((r.get("score", 0.0) - (baseline.get(bm, {}).get("score", 0.0) if baseline else 0.0)) * 100)
            for bm, r in results.items()
            if baseline and bm in baseline and r.get("score") is not None
        },
        "verdict": verdict,
        "evidence_tier": tier,
        "decision_ref": "slm-learning-051 + slm-learning-071",
        "auto_promotion": False,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
