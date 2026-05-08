"""Insert one of the morphism layer variants into a Qwen2 model at a chosen
position. Mutates model.config.num_hidden_layers and config.layer_types.

Refs: slm-learning-165, 196.
"""
from __future__ import annotations

import torch.nn as nn

from modal_app.morphism_layers import (
    GatedBottleneckLayer,
    GatedResidualLayerC,
    IdentityProjectionLayer,
)


def expand_with_identity(model, insert_after_layer: int,
                         variant: str = "A_identity_projection",
                         bottleneck_size: int | None = None,
                         gate_init: float = 0.01,
                         up_scale: float = 0.01):
    inner = model.model
    cfg = inner.config
    target_device = next(inner.parameters()).device
    target_dtype = next(inner.parameters()).dtype
    if variant == "A_identity_projection":
        new_layer = IdentityProjectionLayer(
            cfg.hidden_size, cfg.rms_norm_eps
        ).to(device=target_device, dtype=target_dtype)
    elif variant == "B_gated_bottleneck":
        bn = bottleneck_size or max(64, cfg.hidden_size // 4)
        new_layer = GatedBottleneckLayer(
            cfg.hidden_size, bn, cfg.rms_norm_eps
        ).to(device=target_device, dtype=target_dtype)
    elif variant == "C_gated_residual":
        bn = bottleneck_size or max(64, cfg.hidden_size // 4)
        new_layer = GatedResidualLayerC(
            cfg.hidden_size, bn, cfg.rms_norm_eps,
            gate_init=gate_init, up_scale=up_scale,
        ).to(device=target_device, dtype=target_dtype)
    else:
        raise ValueError(f"unknown variant {variant!r}")
    insert_pos = insert_after_layer + 1
    layers = list(inner.layers)
    layers.insert(insert_pos, new_layer)
    inner.layers = nn.ModuleList(layers)
    cfg.num_hidden_layers = cfg.num_hidden_layers + 1
    if hasattr(cfg, "layer_types") and cfg.layer_types is not None:
        new_layer_types = list(cfg.layer_types)
        new_layer_types.insert(insert_pos, "full_attention")
        cfg.layer_types = new_layer_types
    return new_layer, insert_pos
