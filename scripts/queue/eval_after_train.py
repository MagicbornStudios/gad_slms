"""Auto-eval a freshly-trained candidate against its declared benchmarks.

Reads a verdict.json from `experiments/queue/evaluated/<id>.verdict.json`,
finds the candidate adapter directory, runs the appropriate eval script
per benchmark name, and writes scored results to the candidate's
`eval/<benchmark>.json`.

Per slm-learning-051: never auto-promotes. This script just produces
the scoring envelope. Promotion still goes through
`scripts/delta/promote_atomic.py` with operator stamp.

Usage:

    .venv-gpu/Scripts/python.exe scripts/queue/eval_after_train.py \\
        --job-id doc-verifier-r8-2026-05-06

    # Or auto-pick the most recently evaluated job:
    .venv-gpu/Scripts/python.exe scripts/queue/eval_after_train.py --latest

Decision refs: slm-learning-051, slm-learning-071, slm-learning-082.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "experiments" / "queue"


# Benchmark-name → (eval_script, default_args)
BENCHMARKS = {
    "doc_verifier_f1": ("scripts/eval/eval_doc_verifier.py", []),
    "json_validity": ("scripts/eval/eval_doc_verifier.py", []),  # piggy-backed
    "doc_verifier": ("scripts/eval/eval_doc_verifier.py", []),
    "gad_tools": ("scripts/eval_checkpoint.py", []),
    "gad_tools_v2": ("scripts/eval_checkpoint.py", []),
    "gsm8k": ("scripts/eval_gsm8k.py", []),
    "humaneval": ("scripts/eval_humaneval.py", []),
}


def find_latest_evaluated() -> Path | None:
    eval_dir = QUEUE / "evaluated"
    if not eval_dir.exists():
        return None
    candidates = sorted(eval_dir.glob("*.verdict.json"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def find_verdict(job_id: str) -> Path | None:
    p = QUEUE / "evaluated" / f"{job_id}.verdict.json"
    return p if p.exists() else None


def find_candidate_dir(spec_path: Path, verdict: dict) -> Path | None:
    """Locate experiments/runs/<name>/ from the spec config_path."""
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    config_path = spec.get("config_path") or verdict.get("config_path")
    if not config_path:
        return None
    config_name = Path(config_path).stem.replace("stage25_", "")
    candidate = ROOT / "experiments" / "runs" / config_name
    return candidate if candidate.exists() else None


def run_eval(script: str, args: list[str], adapter_dir: Path,
             benchmark_name: str) -> int:
    py = ROOT / ".venv-gpu" / "Scripts" / "python.exe"
    full = [str(py), str(ROOT / script)]
    full.extend(args)
    full.extend(["--candidate", str(adapter_dir / "adapter")])
    full.extend(["--out", str(adapter_dir / "eval" / f"{benchmark_name}.json")])
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    print(f"[after-train] running: {' '.join(full)}")
    return subprocess.run(full, env=env).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--latest", action="store_true")
    args = parser.parse_args()

    if args.latest:
        verdict_path = find_latest_evaluated()
    elif args.job_id:
        verdict_path = find_verdict(args.job_id)
    else:
        print("ERROR: --job-id or --latest required")
        return 2

    if not verdict_path:
        print("ERROR: no verdict.json found")
        return 2

    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    spec_path = QUEUE / "evaluated" / verdict_path.name.replace(".verdict.json", ".json")
    if not spec_path.exists():
        print(f"ERROR: spec not found at {spec_path}")
        return 2
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    candidate_dir = find_candidate_dir(spec_path, verdict)
    if not candidate_dir:
        print(f"ERROR: candidate dir not found for {spec.get('job_id')}")
        return 2

    adapter_dir = candidate_dir / "adapter"
    if not adapter_dir.exists():
        print(f"ERROR: adapter dir missing at {adapter_dir}")
        return 2

    benchmarks = spec.get("evals", [])
    print(f"[after-train] job={spec.get('job_id')} candidate_dir={candidate_dir}")
    print(f"[after-train] benchmarks: {benchmarks}")

    if verdict.get("train_result", {}).get("status") != "ok":
        print("[after-train] WARN: train_result was not ok, eval may be on a partial adapter")

    seen_scripts: set[str] = set()
    for bench in benchmarks:
        if bench not in BENCHMARKS:
            print(f"[after-train] WARN: no eval script registered for benchmark {bench!r}")
            continue
        script, default_args = BENCHMARKS[bench]
        # Avoid running the same script twice (e.g. doc_verifier covers both
        # doc_verifier_f1 and json_validity).
        if script in seen_scripts:
            continue
        seen_scripts.add(script)
        rc = run_eval(script, default_args, candidate_dir, bench)
        if rc != 0:
            print(f"[after-train] {bench} returned non-zero: {rc}")

    print(f"\n[after-train] done. Eval results in {candidate_dir / 'eval'}")
    print("[after-train] next: review scores, then either:")
    print("  - scripts/delta/promote_atomic.py (with --decision-id + gate-evidence)")
    print("  - move spec to rejected/ if regressed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
