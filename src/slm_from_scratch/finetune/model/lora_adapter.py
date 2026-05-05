"""Attach a PEFT LoRA adapter to a loaded base model.

Single concern: take a base causal-LM + a LoRASettings, return a
PEFT-wrapped model with the right target modules and trainable params.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slm_from_scratch.finetune.config import FinetuneConfig

from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType


def attach_lora(model, cfg: "FinetuneConfig"):
    """Wrap `model` with LoRA adapters per cfg.lora. Returns the wrapped model."""
    if cfg.adapter == "qlora":
        model = prepare_model_for_kbit_training(model)

    lora_cfg = LoraConfig(
        r=cfg.lora.r,
        lora_alpha=cfg.lora.alpha,
        lora_dropout=cfg.lora.dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=cfg.lora.target_modules,
    )
    return get_peft_model(model, lora_cfg)


def count_trainable(model) -> tuple[int, int]:
    """Return (trainable_params, total_params)."""
    total = 0
    trainable = 0
    for p in model.parameters():
        n = p.numel()
        total += n
        if p.requires_grad:
            trainable += n
    return trainable, total
