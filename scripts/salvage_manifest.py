"""
Reconstruct experiments/runs/<name>/MANIFEST.json for runs whose
experiment_runner.py crashed in post-training log parsing (the em-dash
encoding bug fixed by commit b9... — present in train logs from before
that fix).

  .venv-gpu/Scripts/python.exe scripts/salvage_manifest.py

Walks experiments/runs/, finds every directory that has checkpoint.pt
+ train.log + config.snapshot.json but no MANIFEST.json, parses the log
and writes the manifest. Idempotent — skips if MANIFEST.json exists.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "experiments" / "runs"
INDEX_MD = ROOT / "experiments" / "INDEX.md"


EPOCH_RE = re.compile(r"Epoch\s+(\d+)/(\d+).*?avg_loss=([0-9.]+)")
COMPLETE_RE = re.compile(r"complete!.*?\(([0-9.]+)s\)")


def parse_log(text: str) -> dict:
    final_loss = None
    elapsed = None
    for line in text.splitlines():
        m = EPOCH_RE.search(line)
        if m:
            try:
                final_loss = float(m.group(3))
            except ValueError:
                pass
        m2 = COMPLETE_RE.search(line)
        if m2:
            try:
                elapsed = float(m2.group(1))
            except ValueError:
                pass
    return {"final_loss": final_loss, "elapsed_sec": elapsed}


def append_index_row(name: str, manifest: dict) -> None:
    INDEX_MD.parent.mkdir(parents=True, exist_ok=True)
    if not INDEX_MD.exists():
        INDEX_MD.write_text(
            "# Experiment Index\n\n"
            "| run | started | stage | epochs | lr | max_pairs | final_loss | elapsed | gad_tools_passed | notes |\n"
            "|-----|---------|-------|--------|----|-----------|-----------|---------|------------------|-------|\n",
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
        f"|  "
        f"| {manifest.get('notes', '')} |\n"
    )
    with INDEX_MD.open("a", encoding="utf-8") as f:
        f.write(line)


def main() -> int:
    if not RUNS_DIR.exists():
        print(f"No runs directory at {RUNS_DIR}")
        return 1

    salvaged = 0
    skipped = 0
    for run_dir in sorted(RUNS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        ckpt = run_dir / "checkpoint.pt"
        log = run_dir / "train.log"
        cfg = run_dir / "config.snapshot.json"
        manifest = run_dir / "MANIFEST.json"
        if manifest.exists():
            print(f"  [skip] {run_dir.name}: MANIFEST.json exists")
            skipped += 1
            continue
        if not (ckpt.exists() and log.exists() and cfg.exists()):
            print(f"  [miss] {run_dir.name}: incomplete (ckpt={ckpt.exists()} log={log.exists()} cfg={cfg.exists()})")
            continue

        log_text = log.read_text(encoding="utf-8", errors="replace")
        metrics = parse_log(log_text)
        config = json.loads(cfg.read_text(encoding="utf-8"))

        manifest_doc = {
            "id": run_dir.name,
            "config": config,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S",
                                       time.localtime(log.stat().st_mtime - (metrics.get("elapsed_sec") or 0))),
            "exit_code": "salvaged",
            "checkpoint": str(ckpt.relative_to(ROOT)),
            "log": str(log.relative_to(ROOT)),
            "metrics": metrics,
            "notes": (config.get("notes") or "") + " [salvaged manifest after runner UTF-8 crash]",
        }
        manifest.write_text(json.dumps(manifest_doc, indent=2), encoding="utf-8")
        append_index_row(run_dir.name, manifest_doc)
        print(f"  [OK] {run_dir.name}: final_loss={metrics.get('final_loss')} elapsed={metrics.get('elapsed_sec')}s")
        salvaged += 1

    print(f"\nSalvaged {salvaged}, skipped {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
