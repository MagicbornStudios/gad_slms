"""Thin wrapper around TRL's SFTTrainer.

Single concern: turn (model, tokenizer, dataset, FinetuneConfig) into
a trained model + saved adapter on disk. No data loading, no model
construction, no eval — those are upstream/downstream modules.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from trl import SFTConfig, SFTTrainer

if TYPE_CHECKING:
    from datasets import Dataset
    from slm_from_scratch.finetune.config import FinetuneConfig


def build_sft_config(cfg: "FinetuneConfig") -> SFTConfig:
    out = cfg.output_dir
    out.mkdir(parents=True, exist_ok=True)
    return SFTConfig(
        output_dir=str(out),
        num_train_epochs=cfg.training.epochs,
        learning_rate=cfg.training.learning_rate,
        per_device_train_batch_size=cfg.training.batch_size,
        gradient_accumulation_steps=cfg.training.gradient_accumulation,
        warmup_ratio=cfg.training.warmup_ratio,
        weight_decay=cfg.training.weight_decay,
        bf16=cfg.training.bf16,
        fp16=cfg.training.fp16,
        gradient_checkpointing=cfg.training.gradient_checkpointing,
        seed=cfg.training.seed,
        save_strategy=cfg.training.save_strategy,
        logging_steps=cfg.training.logging_steps,
        max_length=cfg.data.max_length,
        report_to=[],  # no wandb / no telemetry
        dataset_text_field="text",
    )


def train(model, tokenizer, dataset: "Dataset", cfg: "FinetuneConfig") -> Path:
    """Run SFT on `dataset`. Returns the directory holding the saved adapter."""
    sft_cfg = build_sft_config(cfg)
    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset,
        args=sft_cfg,
    )
    trainer.train()
    final_dir = cfg.output_dir / "adapter"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    return final_dir
