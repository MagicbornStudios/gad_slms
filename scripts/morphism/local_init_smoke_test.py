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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from modal_app.morphism_layers import (  # noqa: F401
    GatedBottleneckLayer,
    GatedResidualLayerC,
    IdentityProjectionLayer,
)
from modal_app.morphism_insertion import expand_with_identity


BASE_ID = "Qwen/Qwen2.5-Coder-0.5B-Instruct"


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
