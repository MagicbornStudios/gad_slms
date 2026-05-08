"""Three identity-init / near-identity-init residual layer classes used by
morphism Variants A, B, C. Single source of truth — copies in
train_morphism.py / eval_morphism.py / local_init_smoke_test.py reference
this module.

Refs: slm-learning-165, 169, 181, 184, 192, 196.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from transformers.models.qwen2.modeling_qwen2 import Qwen2RMSNorm


class IdentityProjectionLayer(nn.Module):
    def __init__(self, hidden_size: int, eps: float = 1e-6):
        super().__init__()
        self.hidden_size = hidden_size
        self.norm = Qwen2RMSNorm(hidden_size, eps=eps)
        self.proj = nn.Linear(hidden_size, hidden_size, bias=True)
        nn.init.zeros_(self.proj.weight)
        nn.init.zeros_(self.proj.bias)

    def forward(
        self,
        hidden_states,
        attention_mask=None,
        position_ids=None,
        past_key_values=None,
        use_cache=False,
        cache_position=None,
        position_embeddings=None,
        **kwargs,
    ):
        return hidden_states + self.proj(self.norm(hidden_states))


class GatedResidualLayerC(nn.Module):
    def __init__(self, hidden_size: int, bottleneck_size: int,
                 eps: float = 1e-6, gate_init: float = 0.01,
                 up_scale: float = 0.01):
        super().__init__()
        self.hidden_size = hidden_size
        self.bottleneck_size = bottleneck_size
        self.norm = Qwen2RMSNorm(hidden_size, eps=eps)
        self.down = nn.Linear(hidden_size, bottleneck_size, bias=True)
        self.up = nn.Linear(bottleneck_size, hidden_size, bias=True)
        self.gate = nn.Parameter(torch.full((1,), float(gate_init)))
        self.act = nn.SiLU()
        nn.init.kaiming_uniform_(self.down.weight, a=5**0.5)
        nn.init.zeros_(self.down.bias)
        nn.init.kaiming_uniform_(self.up.weight, a=5**0.5)
        with torch.no_grad():
            self.up.weight.mul_(float(up_scale))
        nn.init.zeros_(self.up.bias)

    def forward(
        self,
        hidden_states,
        attention_mask=None,
        position_ids=None,
        past_key_values=None,
        use_cache=False,
        cache_position=None,
        position_embeddings=None,
        **kwargs,
    ):
        h = self.norm(hidden_states)
        h = self.up(self.act(self.down(h)))
        return hidden_states + self.gate * h


class GatedBottleneckLayer(nn.Module):
    def __init__(self, hidden_size: int, bottleneck_size: int,
                 eps: float = 1e-6):
        super().__init__()
        self.hidden_size = hidden_size
        self.bottleneck_size = bottleneck_size
        self.norm = Qwen2RMSNorm(hidden_size, eps=eps)
        self.down = nn.Linear(hidden_size, bottleneck_size, bias=True)
        self.up = nn.Linear(bottleneck_size, hidden_size, bias=True)
        self.gate = nn.Parameter(torch.zeros(1))
        self.act = nn.SiLU()
        nn.init.kaiming_uniform_(self.down.weight, a=5**0.5)
        nn.init.zeros_(self.down.bias)
        nn.init.zeros_(self.up.weight)
        nn.init.zeros_(self.up.bias)

    def forward(
        self,
        hidden_states,
        attention_mask=None,
        position_ids=None,
        past_key_values=None,
        use_cache=False,
        cache_position=None,
        position_embeddings=None,
        **kwargs,
    ):
        h = self.norm(hidden_states)
        h = self.up(self.act(self.down(h)))
        return hidden_states + self.gate * h
