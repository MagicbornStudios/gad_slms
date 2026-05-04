import sys
from pathlib import Path
import torch
from transformers import GPT2LMHeadModel

# Add src to path so we can import our MiniGPT
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from slm_from_scratch.model import GPTConfig, MiniGPT

def main():
    print("Downloading GPT-2 124M weights from HuggingFace...")
    model_hf = GPT2LMHeadModel.from_pretrained("gpt2")
    sd_hf = model_hf.state_dict()

    print("Instantiating Custom MiniGPT...")
    config = GPTConfig(
        vocab_size=50257,
        block_size=1024,
        n_layer=12,
        n_head=12,
        n_embd=768,
        bias=True
    )
    model = MiniGPT(config)
    sd = model.state_dict()

    # The names in MiniGPT perfectly match the huggingface GPT-2 transformer!
    # Because MiniGPT was modeled after GPT-2.
    # We just need to map them across.
    
    # HuggingFace standardizes the keys under 'transformer.' prefix
    keys = [k for k in sd_hf.keys()]
    
    mapped_weights = 0
    for k in keys:
        target_key = k.replace("transformer.", "")
        target_key = target_key.replace("h.", "blocks.")
        target_key = target_key.replace("wte.weight", "token_embedding.weight")
        target_key = target_key.replace("wpe.weight", "position_embedding.weight")
        
        if target_key in sd:
            weight = sd_hf[k]
            if any(x in k for x in ["c_attn.weight", "c_fc.weight", "c_proj.weight"]):
                weight = weight.t()
                
            sd[target_key].copy_(weight)
            mapped_weights += 1
        elif target_key == "lm_head.weight":
            sd[target_key].copy_(sd_hf[k])
            mapped_weights += 1
        else:
            print(f"Unmapped key: {k} -> {target_key}")

    print(f"Successfully mapped {mapped_weights} tensors.")
    
    out_dir = ROOT / "runs" / "pretrained"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "gpt2_124M.pt"
    
    torch.save({
        "model_state_dict": sd,
        "config": config.__dict__
    }, out_path)
    print(f"Saved custom weights to {out_path}")

if __name__ == "__main__":
    main()
