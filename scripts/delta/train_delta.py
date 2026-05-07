"""Daemon-contract alias for train_lora_delta.py.

The gad-monorepo `gad delta-train daemon` (phase 147) shells out to
`scripts/delta/train_delta.py`. The actual implementation lives in
`scripts/delta/train_lora_delta.py`. This file is the canonical entry
point so the daemon's expected name is what's invoked.

If the contract diverges in the future (e.g. multiple back-ends), this
wrapper is the right place to dispatch.
"""
from __future__ import annotations

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "train_lora_delta.py"


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: backing implementation missing at {TARGET}", file=sys.stderr)
        return 2
    sys.argv[0] = str(TARGET)
    runpy.run_path(str(TARGET), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
