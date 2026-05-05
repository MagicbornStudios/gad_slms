"""
Run every experiment config in experiments/configs/ that doesn't already
have an experiments/runs/<name>/MANIFEST.json. Useful for "just go through
the list overnight."

  .venv-gpu/Scripts/python.exe scripts/run_sweep.py [--configs name1 name2]

Exit code is non-zero if any run failed.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIGS_DIR = ROOT / "experiments" / "configs"
RUNS_DIR = ROOT / "experiments" / "runs"
RUNNER = ROOT / "scripts" / "experiment_runner.py"


def discover_configs() -> list[str]:
    names = []
    for ext in ("*.yaml", "*.yml", "*.json"):
        for p in CONFIGS_DIR.glob(ext):
            if p.name.startswith("_"):
                continue
            names.append(p.stem)
    return sorted(set(names))


def is_done(name: str) -> bool:
    return (RUNS_DIR / name / "MANIFEST.json").exists()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configs", nargs="*", help="Subset of config names to run")
    parser.add_argument("--rerun", action="store_true", help="Run even if MANIFEST.json already exists")
    args = parser.parse_args()

    targets = args.configs or discover_configs()
    if not args.rerun:
        targets = [t for t in targets if not is_done(t)]

    if not targets:
        print("Nothing to do (all configs already have MANIFEST.json)")
        return 0

    python_exe = ROOT / ".venv-gpu" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    print(f"Sweep: {len(targets)} run(s) -> {targets}")
    failures = []
    for i, name in enumerate(targets, start=1):
        t0 = time.time()
        print(f"\n[{i}/{len(targets)}] {name}", flush=True)
        proc = subprocess.run(
            [str(python_exe), str(RUNNER), name],
            cwd=str(ROOT),
        )
        elapsed = time.time() - t0
        if proc.returncode == 0:
            print(f"[{i}/{len(targets)}] {name} OK ({elapsed:.1f}s)", flush=True)
        else:
            print(f"[{i}/{len(targets)}] {name} FAILED exit={proc.returncode} ({elapsed:.1f}s)", flush=True)
            failures.append(name)

    print(f"\nSweep done. failures={failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
