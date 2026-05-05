"""VRAM pre-flight check.

Per decision slm-learning-011, every model must load on the baseline
6 GB GTX 1660 Ti. This module gives the orchestrator a simple
yes/no/why-not on a planned run *before* it starts moving weights to
the device.

It is intentionally conservative: an estimate that errs toward
"will not fit" is much cheaper than an actual OOM mid-training.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch


@dataclass
class VRAMReport:
    available_gb: float
    estimated_required_gb: float
    fits: bool
    reason: str
    device: str


# Rough multipliers for a transformer fine-tune in bf16:
#   weights: 2 bytes/param
#   gradients: 2 bytes/param  (skipped for LoRA/QLoRA — only adapter grads)
#   optimizer state (AdamW): 8 bytes/param  (m + v in fp32)
#   activations: ~ batch * seq_len * hidden * n_layer * 0.0002 GB (very rough)
PARAM_BYTES_BF16 = 2
PARAM_BYTES_INT4 = 0.5
ADAMW_STATE_BYTES = 8


def estimate_vram_gb(
    n_params: int,
    *,
    adapter: str = "lora",
    n_trainable_params: Optional[int] = None,
    batch_size: int = 4,
    seq_len: int = 512,
    hidden_size: int = 576,
    n_layer: int = 30,
    grad_checkpointing: bool = True,
    weights_already_loaded: bool = False,
) -> float:
    """Crude estimate of peak VRAM (GB) for a fine-tune step.

    Splits between base weights (frozen for LoRA/QLoRA) and trainable
    params (carry grads + AdamW state). Activations approximated as
    `batch * seq * hidden * n_layer * 8 bytes` for bf16 with a small
    fudge factor; grad checkpointing roughly cuts that by sqrt(n_layer).

    If ``weights_already_loaded`` is True (caller is checking the budget
    *after* moving the model to GPU), the weights term is dropped — at
    that point CUDA has already deducted the weights from `mem_get_info`'s
    free counter, so adding them again double-counts. Without this
    correction the budget check rejects any model big enough that
    weights > free-memory-after-load (1.5B+ on a 6 GB card).
    """
    if adapter in ("lora", "qlora"):
        weights_bytes = n_params * (PARAM_BYTES_INT4 if adapter == "qlora" else PARAM_BYTES_BF16)
        trainable = n_trainable_params if n_trainable_params is not None else int(n_params * 0.005)
        grads_bytes = trainable * PARAM_BYTES_BF16
        opt_bytes = trainable * ADAMW_STATE_BYTES
    else:  # full fine-tune
        weights_bytes = n_params * PARAM_BYTES_BF16
        grads_bytes = n_params * PARAM_BYTES_BF16
        opt_bytes = n_params * ADAMW_STATE_BYTES

    if weights_already_loaded:
        weights_bytes = 0

    # bf16 = 2 bytes; ~4× multiplier for intermediate tensors per layer
    activations_bytes = batch_size * seq_len * hidden_size * n_layer * 2 * 4
    if grad_checkpointing and n_layer > 1:
        activations_bytes /= n_layer ** 0.5

    total_bytes = weights_bytes + grads_bytes + opt_bytes + activations_bytes
    return total_bytes / 1e9


def check_budget(
    n_params: int,
    *,
    adapter: str,
    n_trainable_params: Optional[int] = None,
    batch_size: int = 4,
    seq_len: int = 512,
    hidden_size: int = 576,
    n_layer: int = 30,
    grad_checkpointing: bool = True,
    safety_margin_gb: float = 0.5,
    weights_already_loaded: bool = False,
) -> VRAMReport:
    """Return a VRAMReport saying whether a planned run should fit.

    Pass ``weights_already_loaded=True`` when the model has already been
    moved to GPU by the caller — `mem_get_info` will already reflect
    weights as used, so the estimate must not count them again.
    """
    if not torch.cuda.is_available():
        return VRAMReport(
            available_gb=0.0,
            estimated_required_gb=0.0,
            fits=False,
            reason="cuda not available",
            device="cpu",
        )

    props = torch.cuda.get_device_properties(0)
    free, total = torch.cuda.mem_get_info(0)
    available_gb = free / 1e9
    needed_gb = estimate_vram_gb(
        n_params,
        adapter=adapter,
        n_trainable_params=n_trainable_params,
        batch_size=batch_size,
        seq_len=seq_len,
        hidden_size=hidden_size,
        n_layer=n_layer,
        grad_checkpointing=grad_checkpointing,
        weights_already_loaded=weights_already_loaded,
    )
    fits = (needed_gb + safety_margin_gb) <= available_gb
    reason = (
        f"need ~{needed_gb:.2f} GB + {safety_margin_gb:.1f} GB safety; "
        f"have {available_gb:.2f} GB free of {total / 1e9:.2f} GB total"
    )
    return VRAMReport(
        available_gb=round(available_gb, 2),
        estimated_required_gb=round(needed_gb, 2),
        fits=fits,
        reason=reason,
        device=props.name,
    )
