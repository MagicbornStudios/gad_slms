"""
Progressive Network Growth via Multi-Point Identity Grafting

This script implements the "growing network" thesis properly:

WHY IDENTITY LAYERS WORK (the gap):
  Each transformer layer is wrapped in a residual connection: x = x + layer(x)
  If layer(x) outputs zeros, the whole thing becomes x = x + 0 = x (identity).
  The layer is inert — it does nothing. But it's differentiable.

  During subsequent fine-tuning, gradients flow through the new layer and
  nudge its weights away from zero. The layer starts "firing" — producing
  non-zero outputs that modify the residual stream. What it learns depends
  entirely on WHERE it sits in the network:

  - Early positions (layers 1-10): syntax, token patterns, bracket matching
  - Middle positions (layers 11-20): compositional semantics, call graphs
  - Late positions (layers 21-30): reasoning, prediction, tool selection

HOW MULTI-POINT INSERTION WORKS:
  Instead of appending layers at the end (which only adds reasoning capacity),
  we INSERT identity layers at multiple positions simultaneously.

  Example: A 30-layer model gets 3 new layers inserted at positions 8, 16, 24.
  The result is a 33-layer model where:
  - Layer 8 is a fresh identity block that will learn syntax features
  - Layer 16 is a fresh identity block that will learn semantic features
  - Layer 24 is a fresh identity block that will learn reasoning features

  All existing layers keep their original weights — they just get renumbered.
  The model produces bit-identical outputs until the next fine-tuning cycle.

WHAT ACTUALLY IMPROVES:
  1. CAPACITY: More layers = more "computational steps" the model can take.
     Each layer is a differentiable function. More steps = deeper reasoning.
  2. SPECIALIZATION: New layers inserted between existing ones can learn
     to decompose complex features that their neighbors were cramming into
     a single transformation.
  3. GRADIENT FLOW: In deep networks, gradients can vanish. Inserting
     identity layers creates "gradient highways" — shortcuts where the
     gradient passes through unchanged, helping deeper layers train faster.
  4. SIZE vs EFFECTIVENESS: We're increasing parameter count, but the new
     parameters start at zero (no random noise). They only grow capacity
     where the training signal demands it.
"""

import argparse
import sys
from pathlib import Path
from dataclasses import asdict
from collections import OrderedDict

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from slm_from_scratch.model import LlamaConfig, LlamaBlock, SwiGLUMLP, MoEBlock


def create_identity_block(config: LlamaConfig) -> LlamaBlock:
    """Create a new LlamaBlock that acts as a pure identity function.
    
    The key insight: because of residual connections (x = x + block(x)),
    if block(x) outputs all zeros, the layer is mathematically transparent.
    We achieve this by zeroing the output projections of both attention and MLP.
    """
    block = LlamaBlock(config)
    
    # Zero the attention output projection
    block.self_attn.o_proj.weight.data.zero_()
    
    # Zero the MLP output projection(s)
    if isinstance(block.mlp, SwiGLUMLP):
        block.mlp.down_proj.weight.data.zero_()
    elif isinstance(block.mlp, MoEBlock):
        for expert in block.mlp.experts:
            expert.down_proj.weight.data.zero_()
    
    return block


def compute_insertion_positions(total_layers: int, num_insertions: int, strategy: str = "uniform") -> list[int]:
    """Compute WHERE to insert new identity layers.
    
    Strategies:
      uniform:  Spread evenly across the network (positions 1/4, 1/2, 3/4, etc.)
      early:    Bias toward early layers (improve syntax/tokenization capacity)
      late:     Bias toward late layers (improve reasoning/prediction capacity)
      middle:   Concentrate in the middle (improve compositional understanding)
    """
    if num_insertions <= 0:
        return []
    
    if strategy == "uniform":
        # Evenly spaced across the network
        step = total_layers / (num_insertions + 1)
        positions = [int(step * (i + 1)) for i in range(num_insertions)]
        
    elif strategy == "early":
        # First third of the network
        section = max(total_layers // 3, num_insertions)
        step = section / (num_insertions + 1)
        positions = [int(step * (i + 1)) for i in range(num_insertions)]
        
    elif strategy == "late":
        # Last third of the network
        start = total_layers * 2 // 3
        remaining = total_layers - start
        step = remaining / (num_insertions + 1)
        positions = [int(start + step * (i + 1)) for i in range(num_insertions)]
        
    elif strategy == "middle":
        # Middle third of the network
        start = total_layers // 3
        end = total_layers * 2 // 3
        section = end - start
        step = section / (num_insertions + 1)
        positions = [int(start + step * (i + 1)) for i in range(num_insertions)]
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    
    # Deduplicate and sort
    positions = sorted(set(positions))
    return positions


def insert_layers(state_dict: dict, config: LlamaConfig, positions: list[int]) -> dict:
    """Insert identity layers at the specified positions and renumber all existing layers.
    
    This is the surgical core of Network Morphism. For a 30-layer model with
    insertions at [8, 16, 24], the mapping is:
    
      Original layer 0-7   → New layer 0-7   (unchanged)
      [NEW IDENTITY BLOCK]  → New layer 8
      Original layer 8-15  → New layer 9-16  (shifted +1)
      [NEW IDENTITY BLOCK]  → New layer 17
      Original layer 16-23 → New layer 18-25 (shifted +2)
      [NEW IDENTITY BLOCK]  → New layer 26
      Original layer 24-29 → New layer 27-32 (shifted +3)
    """
    # Build the renumbering map
    # positions are the indices in the NEW numbering where identity blocks go
    # Sort positions so we can process them in order
    sorted_positions = sorted(positions)
    
    # Figure out the mapping: old_index -> new_index
    old_to_new = {}
    new_idx = 0
    insert_idx = 0
    
    for old_idx in range(config.n_layer):
        # Check if we need to insert an identity block before this old layer
        while insert_idx < len(sorted_positions) and sorted_positions[insert_idx] == new_idx:
            new_idx += 1  # Skip this position — it's reserved for the identity block
            insert_idx += 1
        old_to_new[old_idx] = new_idx
        new_idx += 1
    
    # Handle any remaining insertions at the end
    while insert_idx < len(sorted_positions):
        new_idx += 1
        insert_idx += 1
    
    total_new_layers = config.n_layer + len(sorted_positions)
    
    # Renumber existing layer keys
    new_state_dict = OrderedDict()
    for key, tensor in state_dict.items():
        if key.startswith("layers."):
            parts = key.split(".", 2)
            old_layer_idx = int(parts[1])
            rest = parts[2]
            new_layer_idx = old_to_new[old_layer_idx]
            new_key = f"layers.{new_layer_idx}.{rest}"
            new_state_dict[new_key] = tensor
        else:
            new_state_dict[key] = tensor
    
    # Create and insert identity blocks at each position
    new_config = LlamaConfig(**{
        k: v for k, v in asdict(config).items()
    })
    new_config.n_layer = total_new_layers
    
    for pos in sorted_positions:
        block = create_identity_block(config)
        for key, tensor in block.state_dict().items():
            new_state_dict[f"layers.{pos}.{key}"] = tensor
    
    return new_state_dict, new_config


def main():
    parser = argparse.ArgumentParser(
        description="Progressively grow a neural network via Multi-Point Network Morphism."
    )
    parser.add_argument("--ckpt", type=Path, default=ROOT / "runs" / "pretrained" / "smollm2_135M.pt")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "evolved" / "grown_model.pt")
    parser.add_argument("--add-layers", type=int, default=3,
                        help="Number of identity layers to insert")
    parser.add_argument("--strategy", type=str, default="uniform",
                        choices=["uniform", "early", "late", "middle"],
                        help="Where to insert new layers")
    parser.add_argument("--positions", type=int, nargs="*", default=None,
                        help="Explicit insertion positions (overrides --strategy)")
    args = parser.parse_args()

    if not args.ckpt.exists():
        raise FileNotFoundError(f"Checkpoint not found at {args.ckpt}")

    print(f"Loading checkpoint {args.ckpt}")
    checkpoint = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    state_dict = checkpoint['model_state_dict']

    # Detect current number of layers
    layer_keys = [k for k in state_dict.keys() if k.startswith("layers.")]
    if not layer_keys:
        raise ValueError("No 'layers.X.*' keys found in state dict.")
    
    current_layers = max(int(k.split('.')[1]) for k in layer_keys) + 1
    print(f"Detected {current_layers} existing layers.")

    # Reconstruct config
    if 'config' in checkpoint:
        config = LlamaConfig(**checkpoint['config'])
    else:
        print("Config not found in checkpoint. Falling back to default LlamaConfig.")
        config = LlamaConfig(
            vocab_size=49152,
            block_size=2048,
            n_layer=current_layers,
            n_head=9,
            n_kv_head=3,
            n_embd=576,
            intermediate_size=1536,
            dropout=0.0,
            bias=False,
            rms_norm_eps=1e-05,
            rope_theta=10000.0
        )

    # Compute insertion positions
    if args.positions:
        positions = sorted(args.positions)
        print(f"Using explicit insertion positions: {positions}")
    else:
        positions = compute_insertion_positions(current_layers, args.add_layers, args.strategy)
        print(f"Strategy '{args.strategy}' → insertion positions: {positions}")
    
    if not positions:
        print("No positions to insert. Exiting.")
        return

    print(f"\n{'='*60}")
    print(f"NETWORK MORPHISM: {current_layers} → {current_layers + len(positions)} layers")
    print(f"{'='*60}")
    for pos in positions:
        region = "early (syntax)" if pos < current_layers // 3 else \
                 "middle (semantics)" if pos < current_layers * 2 // 3 else \
                 "late (reasoning)"
        print(f"  → Inserting identity block at position {pos} [{region}]")
    print(f"{'='*60}\n")

    # Perform the insertion
    new_state_dict, new_config = insert_layers(state_dict, config, positions)

    print(f"Model grown: {config.n_layer} → {new_config.n_layer} layers")
    
    # Calculate parameter delta
    params_per_layer = sum(
        p.numel() for p in create_identity_block(config).parameters()
    )
    total_new_params = params_per_layer * len(positions)
    print(f"New parameters added: {total_new_params:,} ({total_new_params * 4 / 1024 / 1024:.1f} MB in fp32)")

    # Save expanded checkpoint
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_checkpoint = {
        "model_state_dict": new_state_dict,
        "config": asdict(new_config),
        "growth_metadata": {
            "source_layers": current_layers,
            "target_layers": new_config.n_layer,
            "insertion_positions": positions,
            "strategy": args.strategy if not args.positions else "explicit",
            "params_added": total_new_params,
        }
    }
    torch.save(out_checkpoint, args.out)
    print(f"Saved grown model to {args.out}")
    print(f"\nNext step: Fine-tune on your corpus to make the identity layers fire!")
    print(f"  .venv/Scripts/python.exe scripts/09_finetune_dr_stein.py --ckpt {args.out}")


if __name__ == "__main__":
    main()
