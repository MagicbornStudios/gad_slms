"""Daemon-contract alias for eval_candidate.py.

The gad-monorepo `gad delta-train daemon` (phase 147) shells out to
`scripts/delta/bench_candidate.py`. The actual implementation lives in
`scripts/delta/eval_candidate.py`. This file is the canonical entry
point so the daemon's expected name is what's invoked.
"""
from __future__ import annotations

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "eval_candidate.py"


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: backing implementation missing at {TARGET}", file=sys.stderr)
        return 2
    sys.argv[0] = str(TARGET)
    runpy.run_path(str(TARGET), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
