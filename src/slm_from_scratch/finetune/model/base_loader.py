"""Load a base HF causal-LM with the right dtype + quantization.

One file = one concern: produce a (tokenizer, model) pair from a
FinetuneConfig. No LoRA wrapping here — that's `lora_adapter.py`.

Per decision slm-learning-013, we use HF transformers / TRL / PEFT
for new fine-tunes; the bespoke MiniLlama loop in scripts/16_*.py
remains for the educational track only.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

if TYPE_CHECKING:
    from slm_from_scratch.finetune.config import FinetuneConfig


def _try_load_quantized(model_name: str):
    """Attempt 4-bit load via bitsandbytes; return None if unavailable."""
    try:
        from transformers import BitsAndBytesConfig
        import bitsandbytes  # noqa: F401  (presence check)
    except ImportError:
        return None
    quant_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )
    return AutoModelForCausalLM.from_pretrained(
        model_name, quantization_config=quant_cfg, device_map="auto",
    )


def load_base_model(cfg: "FinetuneConfig"):
    """Return (tokenizer, model) ready for adapter attachment."""
    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    if cfg.adapter == "qlora":
        model = _try_load_quantized(cfg.base_model)
        if model is None:
            raise RuntimeError(
                "qlora requested but bitsandbytes is not installed. "
                "Install it (Linux/WSL) or switch adapter to 'lora'."
            )
        return tokenizer, model

    if cfg.training.bf16:
        dtype = torch.bfloat16
    elif cfg.training.fp16:
        dtype = torch.float16
    else:
        dtype = torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        cfg.base_model,
        torch_dtype=dtype,
        device_map="auto",
    )
    if cfg.training.gradient_checkpointing:
        model.gradient_checkpointing_enable()
    return tokenizer, model
