import argparse
import sys
from pathlib import Path
from dataclasses import asdict

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from slm_from_scratch.model import LlamaConfig


def main():
    parser = argparse.ArgumentParser(description="Convert a Dense model to a Mixture of Experts (MoE) via Sparse Upcycling.")
    parser.add_argument("--ckpt", type=Path, default=ROOT / "runs" / "pretrained" / "smollm2_135M.pt")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "evolved" / "moe_model.pt")
    parser.add_argument("--experts", type=int, default=4)
    parser.add_argument("--experts-per-tok", type=int, default=2)
    args = parser.parse_args()

    if not args.ckpt.exists():
        raise FileNotFoundError(f"Checkpoint not found at {args.ckpt}")

    print(f"Loading checkpoint {args.ckpt}")
    checkpoint = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    state_dict = checkpoint['model_state_dict']

    # Read layers
    layer_keys = [k for k in state_dict.keys() if k.startswith("layers.")]
    current_layers = max([int(k.split('.')[1]) for k in layer_keys]) + 1
    
    if 'config' in checkpoint:
        config_dict = checkpoint['config']
    else:
        config_dict = {
            "vocab_size": 49152,
            "block_size": 2048,
            "n_layer": current_layers,
            "n_head": 9,
            "n_kv_head": 3,
            "n_embd": 576,
            "intermediate_size": 1536,
            "dropout": 0.1,
            "bias": False,
            "rms_norm_eps": 1e-05,
            "rope_theta": 10000.0,
            "num_experts": 1,
            "num_experts_per_tok": 1
        }
        
    if config_dict.get('num_experts', 1) > 1:
        print("Model is already an MoE model. Exiting.")
        return

    print(f"Upcycling Dense model to MoE with {args.experts} experts ({args.experts_per_tok} active per token)...")
    
    config_dict['num_experts'] = args.experts
    config_dict['num_experts_per_tok'] = args.experts_per_tok
    config = LlamaConfig(**config_dict)
    
    new_state_dict = {}
    
    for key, tensor in state_dict.items():
        if "mlp." in key:
            # It's an MLP weight. We need to duplicate it into N experts!
            # Old key: layers.0.mlp.gate_proj.weight
            # New key: layers.0.mlp.experts.X.gate_proj.weight
            parts = key.split("mlp.")
            prefix = parts[0] + "mlp.experts."
            suffix = parts[1]
            
            for expert_idx in range(args.experts):
                new_key = f"{prefix}{expert_idx}.{suffix}"
                # We clone so they don't share identical memory pointers
                new_state_dict[new_key] = tensor.clone()
        else:
            new_state_dict[key] = tensor
            
    # Now we need to randomly initialize the routing gate for each layer
    for layer_idx in range(current_layers):
        gate_weight = torch.randn((args.experts, config.n_embd)) * 0.02
        new_state_dict[f"layers.{layer_idx}.mlp.gate.weight"] = gate_weight

    # Save upcycled checkpoint
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_checkpoint = {
        "model_state_dict": new_state_dict,
        "config": asdict(config)
    }
    torch.save(out_checkpoint, args.out)
    print(f"Successfully saved MoE model to {args.out}")


if __name__ == "__main__":
    main()
