"""
Run scripts/eval_checkpoint.py against every experiment that has a
checkpoint but no eval result yet. Designed for "wake up to a finished
sweep" use cases.

  .venv-gpu/Scripts/python.exe scripts/eval_all_experiments.py

For each experiments/runs/<name>/checkpoint.pt without a sibling
eval_gad_tools.json, run the eval, save the summary, and update
experiments/INDEX.md.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "experiments" / "runs"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rerun", action="store_true", help="Re-evaluate even if eval_gad_tools.json exists")
    parser.add_argument("--max-new-tokens", type=int, default=50)
    parser.add_argument("--temperature", type=float, default=0.7)
    args = parser.parse_args()

    if not RUNS_DIR.exists():
        print(f"No runs directory at {RUNS_DIR}", file=sys.stderr)
        return 1

    python_exe = ROOT / ".venv-gpu" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    targets: list[Path] = []
    for run_dir in sorted(RUNS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        ckpt = run_dir / "checkpoint.pt"
        out = run_dir / "eval_gad_tools.json"
        if not ckpt.exists():
            print(f"  - {run_dir.name}: no checkpoint, skipping", flush=True)
            continue
        if out.exists() and not args.rerun:
            print(f"  - {run_dir.name}: eval already present, skipping", flush=True)
            continue
        targets.append(run_dir)

    if not targets:
        print("Nothing to eval.")
        return 0

    print(f"Evaluating {len(targets)} checkpoint(s)")
    failures = []
    for i, run_dir in enumerate(targets, start=1):
        ckpt = run_dir / "checkpoint.pt"
        out = run_dir / "eval_gad_tools.json"
        t0 = time.time()
        print(f"\n[{i}/{len(targets)}] {run_dir.name}", flush=True)
        proc = subprocess.run(
            [
                str(python_exe), str(ROOT / "scripts" / "eval_checkpoint.py"),
                "--checkpoint", str(ckpt),
                "--out", str(out),
                "--name", run_dir.name,
                "--max-new-tokens", str(args.max_new_tokens),
                "--temperature", str(args.temperature),
            ],
            cwd=str(ROOT),
        )
        elapsed = time.time() - t0
        if proc.returncode == 0:
            print(f"[{i}/{len(targets)}] {run_dir.name} EVAL OK ({elapsed:.1f}s)", flush=True)
        else:
            print(f"[{i}/{len(targets)}] {run_dir.name} EVAL FAILED exit={proc.returncode} ({elapsed:.1f}s)", flush=True)
            failures.append(run_dir.name)

    print(f"\nEval all done. failures={failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
