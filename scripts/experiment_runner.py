"""
Training factory: run one experiment from a YAML/JSON config and write a
deterministic checkpoint + manifest.

The goal is to make "try a different hypothesis fast" a 30-second edit:
  1. Copy experiments/configs/_template.yaml to experiments/configs/<name>.yaml
  2. Edit the fields you want to vary (model size, data mix, hparams)
  3. Run: .venv-gpu/Scripts/python.exe scripts/experiment_runner.py <name>
  4. Read the result in experiments/runs/<name>/MANIFEST.json
  5. Skim experiments/INDEX.md for cross-run comparison

Each experiment is a discrete identity:
  - id: <name>
  - config (recorded verbatim)
  - runtime metrics (wall-clock, peak VRAM, final loss)
  - eval scores (added by scripts/eval_checkpoint.py later)

This is intentionally minimal — train Stage 2 reasoning on a (possibly
custom) data file with the existing MiniLlama, save the checkpoint, write
the manifest. Stage 1 SFT and Stage 3 DPO will be folded in once we
exercise this loop end-to-end on Stage 2 first.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = ROOT / "experiments"
RUNS_DIR = EXPERIMENTS_DIR / "runs"
CONFIGS_DIR = EXPERIMENTS_DIR / "configs"
INDEX_MD = EXPERIMENTS_DIR / "INDEX.md"


def load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError:
            print("yaml not installed; switching to JSON or pip install pyyaml", file=sys.stderr)
            raise
        return yaml.safe_load(text)
    return json.loads(text)


def build_train_command(cfg: dict, run_dir: Path) -> list[str]:
    """Translate a config dict into a CLI invocation for scripts/16_reasoning_training.py.

    Recognized keys (Stage 2 only for now):
        stage:        "reasoning"
        ckpt:         path to seed checkpoint (default: SFT result)
        out:          output checkpoint name (defaults to run_dir/checkpoint.pt)
        epochs:       training epochs
        lr:           learning rate
        max_pairs:    cap on training pairs
        block_size:   sequence cap
        device:       "auto" | "cuda" | "cpu"
    """
    if cfg.get("stage", "reasoning") != "reasoning":
        raise ValueError("experiment_runner currently supports only stage=reasoning")

    python_exe = ROOT / ".venv-gpu" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    cmd = [
        str(python_exe), "-u",
        str(ROOT / "scripts" / "16_reasoning_training.py"),
    ]
    if "ckpt" in cfg:
        cmd += ["--ckpt", str(ROOT / cfg["ckpt"])]
    cmd += ["--out", str(run_dir / "checkpoint.pt")]
    cmd += ["--epochs", str(cfg.get("epochs", 5))]
    cmd += ["--lr", str(cfg.get("lr", 1e-5))]
    cmd += ["--max-pairs", str(cfg.get("max_pairs", 100))]
    cmd += ["--block-size", str(cfg.get("block_size", 512))]
    cmd += ["--device", str(cfg.get("device", "auto"))]
    return cmd


def parse_train_log(log_text: str) -> dict:
    """Pull final loss + wall time from the training script's stdout."""
    final_loss = None
    elapsed = None
    for line in log_text.splitlines():
        s = line.strip()
        if s.startswith("Epoch ") and "avg_loss=" in s:
            try:
                final_loss = float(s.split("avg_loss=")[1])
            except (IndexError, ValueError):
                pass
        if "elapsed=" in s:
            try:
                elapsed = float(s.split("elapsed=")[1].rstrip("s"))
            except (IndexError, ValueError):
                pass
        if "training complete" in s.lower() and "(" in s:
            try:
                elapsed = float(s.rsplit("(", 1)[1].split("s")[0])
            except (IndexError, ValueError):
                pass
    return {"final_loss": final_loss, "elapsed_sec": elapsed}


def append_index(name: str, manifest: dict) -> None:
    """Append a one-line summary to INDEX.md for quick cross-experiment scan."""
    INDEX_MD.parent.mkdir(parents=True, exist_ok=True)
    if not INDEX_MD.exists():
        INDEX_MD.write_text(
            "# Experiment Index\n\n"
            "| run | started | stage | epochs | lr | max_pairs | final_loss | elapsed | notes |\n"
            "|-----|---------|-------|--------|----|-----------|-----------|---------|-------|\n",
            encoding="utf-8",
        )
    cfg = manifest.get("config", {})
    metrics = manifest.get("metrics", {})
    line = (
        f"| {name} "
        f"| {manifest.get('started_at', '')} "
        f"| {cfg.get('stage', 'reasoning')} "
        f"| {cfg.get('epochs', '')} "
        f"| {cfg.get('lr', '')} "
        f"| {cfg.get('max_pairs', '')} "
        f"| {metrics.get('final_loss', '?')} "
        f"| {metrics.get('elapsed_sec', '?')}s "
        f"| {manifest.get('notes', '')} |\n"
    )
    with INDEX_MD.open("a", encoding="utf-8") as f:
        f.write(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Experiment id; reads experiments/configs/<name>.yaml|json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    # Locate config file
    cfg_path = None
    for ext in (".yaml", ".yml", ".json"):
        candidate = CONFIGS_DIR / f"{args.name}{ext}"
        if candidate.exists():
            cfg_path = candidate
            break
    if cfg_path is None:
        print(f"No config found for '{args.name}' in {CONFIGS_DIR}", file=sys.stderr)
        return 2

    cfg = load_config(cfg_path)
    run_dir = RUNS_DIR / args.name
    run_dir.mkdir(parents=True, exist_ok=True)

    started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    cmd = build_train_command(cfg, run_dir)

    # Mirror every run's config inside the run directory for traceability
    (run_dir / "config.snapshot.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    # Stream the training output to the run dir so we can parse loss after
    log_path = run_dir / "train.log"
    print(f"Running: {' '.join(cmd)}", flush=True)
    with log_path.open("w", encoding="utf-8") as logf:
        proc = subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True)

    log_text = log_path.read_text(encoding="utf-8")
    metrics = parse_train_log(log_text)

    manifest = {
        "id": args.name,
        "config_path": str(cfg_path.relative_to(ROOT)),
        "config": cfg,
        "started_at": started_at,
        "exit_code": proc.returncode,
        "checkpoint": str((run_dir / "checkpoint.pt").relative_to(ROOT)),
        "log": str(log_path.relative_to(ROOT)),
        "metrics": metrics,
        "notes": cfg.get("notes", ""),
    }
    (run_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    append_index(args.name, manifest)

    status = "ok" if proc.returncode == 0 else f"exit={proc.returncode}"
    print(f"\nDone [{status}] -> {run_dir}/MANIFEST.json")
    print(f"final_loss={metrics.get('final_loss')} elapsed={metrics.get('elapsed_sec')}s")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
