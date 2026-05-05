"""Model loading + adapter attachment.

Two seams: load a base HF model (`base_loader`), then optionally wrap
it with PEFT adapters (`lora_adapter`).
"""
from slm_from_scratch.finetune.model.base_loader import load_base_model
from slm_from_scratch.finetune.model.lora_adapter import attach_lora

__all__ = ["load_base_model", "attach_lora"]
