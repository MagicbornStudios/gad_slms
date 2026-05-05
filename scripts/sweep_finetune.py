"""Run many fine-tune configs end to end, one at a time.

  # all configs in a directory
  .venv-gpu/Scripts/python.exe scripts/sweep_finetune.py \
      --configs-dir experiments/configs/

  # specific configs
  .venv-gpu/Scripts/python.exe scripts/sweep_finetune.py \
      --configs experiments/configs/stage25_gad_tools_lora.yaml \
                experiments/configs/stage25_gad_tools_lora_higher_lr.yaml

By default skips runs whose output directory already has MANIFEST.json
(so re-running the sweep cheaply picks up only new work). Each run is
a fresh Python subprocess so a CUDA OOM in one config does not poison
the others.

Future: shard across GPUs via CUDA_VISIBLE_DEVICES once the eGPU is
detected; until then everything runs sequentially on cuda:0.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _resolve_configs(args) -> list[Path]:
    paths: list[Path] = []
    if args.configs:
        paths.extend(Path(p) for p in args.configs)
    if args.configs_dir:
        d = Path(args.configs_dir)
        if not d.is_dir():
            print(f"--configs-dir not a directory: {d}", file=sys.stderr)
            return []
        paths.extend(sorted(d.glob("*.yaml")))
    # de-dup, preserve order
    seen: set[str] = set()
    unique: list[Path] = []
    for p in paths:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _output_dir_for(config_path: Path, output_root: Path) -> Path | None:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "name" not in raw:
        return None
    return output_root / raw["name"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configs", nargs="*", help="Specific YAML config files")
    parser.add_argument("--configs-dir", help="Directory of YAML config files")
    parser.add_argument("--output-root", default="experiments/runs",
                        help="Where finetune runs write output (matches config default)")
    parser.add_argument("--rerun", action="store_true",
                        help="Re-run even if MANIFEST.json already exists")
    parser.add_argument("--dry-run", action="store_true",
                        help="Pass through to each finetune run")
    parser.add_argument("--cuda-device", default="0",
                        help="CUDA_VISIBLE_DEVICES value for every run")
    args = parser.parse_args()

    configs = _resolve_configs(args)
    if not configs:
        print("No configs to run.", file=sys.stderr)
        return 1

    python_exe = ROOT / ".venv-gpu" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = Path(sys.executable)
    output_root = Path(args.output_root)

    print(f"Sweep: {len(configs)} config(s) on cuda:{args.cuda_device}")
    failures: list[str] = []
    skipped: list[str] = []
    for i, cfg_path in enumerate(configs, start=1):
        out_dir = _output_dir_for(cfg_path, output_root)
        manifest = (out_dir / "MANIFEST.json") if out_dir else None
        if manifest and manifest.exists() and not args.rerun:
            print(f"[{i}/{len(configs)}] {cfg_path.name} — MANIFEST exists, skipping")
            skipped.append(cfg_path.name)
            continue

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["CUDA_VISIBLE_DEVICES"] = args.cuda_device

        cmd = [
            str(python_exe), str(ROOT / "scripts" / "18_stage25_finetune.py"),
            "--config", str(cfg_path),
        ]
        if args.dry_run:
            cmd.append("--dry-run")

        print(f"\n[{i}/{len(configs)}] {cfg_path.name}")
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env)
        dt = time.time() - t0
        if proc.returncode == 0:
            print(f"  -> ok in {dt:.1f}s")
        else:
            print(f"  -> FAILED rc={proc.returncode} in {dt:.1f}s")
            failures.append(cfg_path.name)

    print(f"\nSweep done. ran={len(configs) - len(skipped)} "
          f"skipped={len(skipped)} failed={len(failures)}")
    if failures:
        print(f"failed: {failures}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
