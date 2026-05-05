"""Run manifest writer.

Single concern: capture the full state of one run (config, environment,
trainable param count, VRAM report, eval scores) into a single JSON
file at the run's output directory. Mirrors the experiments/runs/<name>/
MANIFEST.json convention used by scripts/experiment_runner.py so the
existing INDEX.md tooling keeps working.
"""
from __future__ import annotations

import json
import platform
import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from slm_from_scratch.finetune.config import FinetuneConfig
    from slm_from_scratch.finetune.vram_budget import VRAMReport


def write_manifest(
    cfg: "FinetuneConfig",
    *,
    adapter_dir: Path,
    vram: "VRAMReport",
    n_trainable: int,
    n_total: int,
    train_seconds: float,
    eval_results: dict | None = None,
    extra: dict | None = None,
) -> Path:
    out = cfg.output_dir / "MANIFEST.json"
    payload = {
        "id": cfg.name,
        "kind": "stage25_finetune",
        "adapter_kind": cfg.adapter,
        "config": cfg.to_dict(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_train_sec": round(train_seconds, 1),
        "adapter_dir": str(adapter_dir),
        "trainable_params": n_trainable,
        "total_params": n_total,
        "vram_report": asdict(vram) if vram is not None else None,
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda": torch.version.cuda if torch.cuda.is_available() else None,
            "device": (
                torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
            ),
        },
        "eval_results": eval_results or {},
        "notes": cfg.notes,
    }
    if extra:
        payload.update(extra)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out
