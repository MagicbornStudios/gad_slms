"""CLI entry point for a Stage 2.5+ fine-tune.

  .venv-gpu/Scripts/python.exe scripts/18_stage25_finetune.py \
      --config experiments/configs/stage25_gad_tools_lora.yaml

  # validate config + data + model load without training
  .venv-gpu/Scripts/python.exe scripts/18_stage25_finetune.py \
      --config experiments/configs/stage25_gad_tools_lora.yaml --dry-run

This script is just routing — the real logic lives in
src/slm_from_scratch/finetune/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True,
                        help="YAML config file (see experiments/configs/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip train + eval; validate config/data/model load only")
    args = parser.parse_args()

    from slm_from_scratch.finetune import load_config, run_finetune
    cfg = load_config(args.config)
    out = run_finetune(cfg, dry_run=args.dry_run)
    print(f"\noutput: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
