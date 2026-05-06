"""Produce a candidate LoRA adapter from a manifest.

Subprocess contract for global daemon (gad-monorepo phase 147 +
slm-learning phase 05). Per slm-learning-051: this script produces
a candidate, never an auto-merged adapter.

Input:
    --manifest <path>   manifest JSON describing { base, data, lora, training }
    --base-model <id>   HF model id or local path
    --out-dir <path>    where to write candidate adapter + manifest
    --dry-run           validate inputs, do not train

Output (stdout, JSON):
    { "status": "ok", "candidate_dir": "...", "trainable_params": ...,
      "wall_seconds": ..., "manifest": {...} }

Internally delegates to scripts/18_stage25_finetune.py via the same
config schema. The manifest can either be a Stage 2.5 YAML config
(direct passthrough) or a thin JSON wrapper that points at one.

This script does NOT publish to HF Hub or merge anywhere. The output
candidate directory is the only artifact.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="Stage 2.5 YAML config OR JSON wrapper {config_path: ...}")
    parser.add_argument("--base-model", type=str, default=None,
                        help="Override base_model in the config (optional)")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Override output directory (optional)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.manifest.exists():
        print(json.dumps({
            "status": "error",
            "error": f"manifest not found: {args.manifest}",
        }))
        return 2

    # If JSON wrapper, dereference to actual config path.
    if args.manifest.suffix.lower() == ".json":
        try:
            wrapper = json.loads(args.manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(json.dumps({"status": "error", "error": f"manifest JSON parse: {e}"}))
            return 2
        config_path = Path(wrapper.get("config_path", ""))
        if not config_path.is_absolute():
            config_path = ROOT / config_path
    else:
        config_path = args.manifest

    if not config_path.exists():
        print(json.dumps({
            "status": "error",
            "error": f"resolved config not found: {config_path}",
        }))
        return 2

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "18_stage25_finetune.py"),
        "--config", str(config_path),
    ]
    if args.dry_run:
        cmd.append("--dry-run")

    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")

    t0 = time.time()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    wall = time.time() - t0

    if proc.returncode != 0:
        print(json.dumps({
            "status": "error",
            "error": "trainer subprocess returned non-zero",
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
            "wall_seconds": wall,
        }))
        return proc.returncode

    candidate_dir = ROOT / "experiments" / "runs" / config_path.stem.replace("stage25_", "")
    if args.out_dir is not None:
        candidate_dir = args.out_dir

    result = {
        "status": "ok",
        "candidate_dir": str(candidate_dir),
        "config_used": str(config_path),
        "wall_seconds": wall,
        "stdout_tail": proc.stdout[-500:],
        "decision_ref": "slm-learning-051",
        "auto_promotion": False,
        "next_step": "scripts/delta/eval_candidate.py + manual promote",
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
