"""Magnitude-based weight pruning for the iterative train -> prune loop.

Per decision slm-learning-014, sparsity is a first-class hyperparameter.
This module exposes a single concern: take a model and a sparsity ratio,
return the model with the smallest-magnitude weights zeroed in the
target modules. Re-training after pruning happens through the normal
SFTTrainer path with the pruned weights as the starting point.

Designed to work on either a PEFT adapter (LoRA matrices) or a full
model. Default targets the same Llama linear layers we LoRA-fine-tune.
"""
from __future__ import annotations

from typing import Iterable

import torch
import torch.nn as nn
import torch.nn.utils.prune as prune


DEFAULT_TARGETS = (
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
)


def _matching_linears(model: nn.Module, name_substrings: Iterable[str]) -> list[tuple[nn.Module, str]]:
    out: list[tuple[nn.Module, str]] = []
    name_substrings = tuple(name_substrings)
    for module_name, module in model.named_modules():
        if not isinstance(module, nn.Linear):
            continue
        if any(s in module_name for s in name_substrings):
            out.append((module, "weight"))
    return out


def magnitude_prune(
    model: nn.Module,
    *,
    sparsity: float,
    target_substrings: Iterable[str] = DEFAULT_TARGETS,
    make_permanent: bool = True,
) -> dict:
    """Zero the smallest-magnitude `sparsity` fraction of weights per target.

    Returns a small report: {sparsity_target, layers_pruned, params_zeroed,
    params_total}.
    """
    if not 0.0 < sparsity < 1.0:
        raise ValueError(f"sparsity must be in (0, 1); got {sparsity}")

    layers = _matching_linears(model, target_substrings)
    if not layers:
        return {
            "sparsity_target": sparsity,
            "layers_pruned": 0,
            "params_zeroed": 0,
            "params_total": 0,
        }

    params_zeroed = 0
    params_total = 0
    for module, attr in layers:
        prune.l1_unstructured(module, name=attr, amount=sparsity)
        if make_permanent:
            prune.remove(module, attr)
        w = getattr(module, attr)
        params_total += w.numel()
        params_zeroed += (w == 0).sum().item()

    return {
        "sparsity_target": sparsity,
        "layers_pruned": len(layers),
        "params_zeroed": int(params_zeroed),
        "params_total": int(params_total),
        "actual_sparsity": (
            params_zeroed / params_total if params_total else 0.0
        ),
    }


def measure_sparsity(model: nn.Module, target_substrings: Iterable[str] = DEFAULT_TARGETS) -> float:
    """Return the fraction of zeroed weights across target linears."""
    layers = _matching_linears(model, target_substrings)
    z = 0
    n = 0
    for module, attr in layers:
        w = getattr(module, attr)
        z += (w == 0).sum().item()
        n += w.numel()
    return z / n if n else 0.0
