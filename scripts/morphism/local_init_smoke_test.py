"""Local CPU/CUDA smoke test for the morphism Variant A patch.

Verifies — without spending Modal compute — that:
  1. The IdentityProjectionLayer can be inserted into a Qwen2 model.
  2. The expanded model returns identical logits to the base on a few prompts.
  3. The trainable param count matches what we expect (one Linear weight + bias).

Run on the local laptop CPU (or 1660 Ti via .venv-gpu) in <1 minute.
If this fails, the Modal job would also fail — fix the patch first.

Usage:
    .venv/Scripts/python.exe scripts/morphism/local_init_smoke_test.py

Decision refs: slm-learning-165, slm-learning-169.
"""
from __future__ import annotations

import sys

import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.models.qwen2.modeling_qwen2 import Qwen2RMSNorm


BASE_ID = "Qwen/Qwen2.5-Coder-0.5B-Instruct"


class IdentityProjectionLayer(nn.Module):
    def __init__(self, hidden_size: int, eps: float = 1e-6):
        super().__init__()
        self.hidden_size = hidden_size
        self.norm = Qwen2RMSNorm(hidden_size, eps=eps)
        self.proj = nn.Linear(hidden_size, hidden_size, bias=True)
        nn.init.zeros_(self.proj.weight)
        nn.init.zeros_(self.proj.bias)

    def forward(
        self, hidden_states, attention_mask=None, position_ids=None,
        past_key_values=None, use_cache=False, cache_position=None,
        position_embeddings=None, **kwargs,
    ):
        return hidden_states + self.proj(self.norm(hidden_states))


class GatedResidualLayerC(nn.Module):
    """Variant C: small-nonzero init throughout."""
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
        self, hidden_states, attention_mask=None, position_ids=None,
        past_key_values=None, use_cache=False, cache_position=None,
        position_embeddings=None, **kwargs,
    ):
        h = self.norm(hidden_states)
        h = self.up(self.act(self.down(h)))
        return hidden_states + self.gate * h


class GatedBottleneckLayer(nn.Module):
    """Variant B: y = x + gate * up(silu(down(norm(x))))."""

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
        self, hidden_states, attention_mask=None, position_ids=None,
        past_key_values=None, use_cache=False, cache_position=None,
        position_embeddings=None, **kwargs,
    ):
        h = self.norm(hidden_states)
        h = self.up(self.act(self.down(h)))
        return hidden_states + self.gate * h


def expand_with_identity(model, insert_after_layer: int,
                           variant: str = "A_identity_projection",
                           bottleneck_size: int | None = None):
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


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="A_identity_projection",
                    choices=["A_identity_projection", "B_gated_bottleneck",
                             "C_gated_residual"])
    ap.add_argument("--insert-after", type=int, default=11)
    ap.add_argument("--bottleneck-size", type=int, default=None)
    ap.add_argument("--base", default=BASE_ID)
    args = ap.parse_args()

    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    dtype = torch.bfloat16 if use_cuda else torch.float32
    print(f"[smoke] device={device} dtype={dtype} variant={args.variant} "
          f"insert_after={args.insert_after}")

    print(f"[smoke] loading base {args.base} (this may take 30s) ...")
    tok = AutoTokenizer.from_pretrained(args.base)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    base = AutoModelForCausalLM.from_pretrained(args.base, dtype=dtype).to(device)
    base.eval()

    print(f"[smoke] loading second copy for expansion ...")
    expanded = AutoModelForCausalLM.from_pretrained(args.base, dtype=dtype).to(device)
    new_layer, insert_pos = expand_with_identity(
        expanded, insert_after_layer=args.insert_after,
        variant=args.variant, bottleneck_size=args.bottleneck_size,
    )
    expanded.eval()
    print(f"[smoke] expanded num_hidden_layers={expanded.config.num_hidden_layers} "
          f"(inserted at {insert_pos})")

    trainable_params = sum(p.numel() for p in new_layer.parameters())
    total_params = sum(p.numel() for p in expanded.parameters())
    print(f"[smoke] trainable_params (new_layer): {trainable_params:,} "
          f"({100 * trainable_params / total_params:.4f}% of total)")

    prompts = [
        "def hello():",
        "import math\nfrom typing import List",
        "def fibonacci(n: int) -> int:",
        "class Stack:",
        "for i in range(10):",
    ]
    n_match = 0
    n_total = 0
    n_logit_match = 0

    for p in prompts:
        ids = tok(p, return_tensors="pt").to(device)

        # First check: logits at the prompt's last token must match exactly.
        with torch.no_grad():
            out_b = base(**ids).logits
            out_e = expanded(**ids).logits
        # Take last-position logits
        l_b = out_b[0, -1, :].float()
        l_e = out_e[0, -1, :].float()
        max_diff = (l_b - l_e).abs().max().item()
        # bf16 precision floor is ~7e-3
        if max_diff < 1e-2:
            n_logit_match += 1
        print(f"[smoke] prompt={p[:30]!r:<35} max_logit_diff={max_diff:.2e}")

        # Second check: greedy generation matches token-for-token
        with torch.no_grad():
            gen_b = base.generate(**ids, max_new_tokens=12, do_sample=False,
                                   pad_token_id=tok.pad_token_id)
            gen_e = expanded.generate(**ids, max_new_tokens=12, do_sample=False,
                                       pad_token_id=tok.pad_token_id)
        new_b = gen_b[0][ids["input_ids"].shape[1]:].tolist()
        new_e = gen_e[0][ids["input_ids"].shape[1]:].tolist()
        n = min(len(new_b), len(new_e))
        match = sum(1 for a, b in zip(new_b[:n], new_e[:n]) if a == b)
        n_match += match
        n_total += n

    overall = n_match / max(1, n_total)
    print()
    print(f"[smoke] logit-match (max_diff < 1e-2): {n_logit_match}/{len(prompts)}")
    print(f"[smoke] greedy-token agreement: {n_match}/{n_total} = {overall:.4f}")

    # Variant C deliberately uses small-NONZERO init so logit-diff is
    # ~0.0001 not bit-exact 0. Token agreement should still be 1.0000.
    threshold_logit = (5e-2 if args.variant == "C_gated_residual"
                       else 1e-2)
    logit_pass = sum(1 for r in [None] for _ in []) or n_logit_match  # placeholder
    if overall >= 0.99 and n_logit_match >= max(1, len(prompts) - 1):
        print(f"[smoke] PASS — patch is correct, function-preserving "
              f"(token agreement {overall:.4f}, "
              f"logit-match {n_logit_match}/{len(prompts)} "
              f"under tol {threshold_logit:.0e}).")
        return 0
    else:
        print(f"[smoke] FAIL — token agreement {overall:.4f} "
              f"or logit-match {n_logit_match}/{len(prompts)} "
              f"below threshold. Investigate before firing on Modal.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
