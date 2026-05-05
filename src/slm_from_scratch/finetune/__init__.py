"""Stage 2.5+ fine-tune package built on TRL SFTTrainer + PEFT LoRA/QLoRA.

Entry point: `from slm_from_scratch.finetune import run_finetune`
or run `scripts/18_stage25_finetune.py --config <path>`.

See decisions slm-learning-011..018 and AGENTS.md "SLM Training Strategy".
"""
from slm_from_scratch.finetune.config import FinetuneConfig, load_config
from slm_from_scratch.finetune.orchestrator import run_finetune

__all__ = ["FinetuneConfig", "load_config", "run_finetune"]
