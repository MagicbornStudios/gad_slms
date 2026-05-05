"""Polymorphic checkpoint loader for eval scripts.

Two paths:
  - .pt file              -> DrSteinModel (our MiniLlama wrapper)
  - directory with        -> HFAdapterModel (HF base + PEFT LoRA)
    adapter_config.json

Returns a wrapper that exposes:
  .device
  .generate(prompt, max_new_tokens=..., temperature=...) -> str
"""
from __future__ import annotations

from pathlib import Path


def load_model_for_eval(checkpoint: str | Path, *, device: str = "auto"):
    p = Path(checkpoint)
    if p.is_dir() and (p / "adapter_config.json").exists():
        from slm_from_scratch.models.hf_adapter import HFAdapterModel
        return HFAdapterModel(p, device=device)
    if p.is_file() and p.suffix == ".pt":
        from slm_from_scratch.models.dr_stein import DrSteinModel
        return DrSteinModel(model_path=str(p), device=device)
    raise ValueError(
        f"unrecognized checkpoint shape: {p} — expected a .pt file or a "
        "directory containing adapter_config.json"
    )
