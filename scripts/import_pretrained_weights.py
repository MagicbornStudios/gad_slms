import torch
from transformers import AutoModelForCausalLM
import sys
from pathlib import Path

# Add src to python path so we can import slm_from_scratch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from slm_from_scratch.model import MiniLlama, LlamaConfig

def map_smollm_weights():
    print("Downloading HuggingFaceTB/SmolLM2-135M-Instruct weights from HuggingFace...")
    model_hf = AutoModelForCausalLM.from_pretrained("HuggingFaceTB/SmolLM2-135M-Instruct")
    sd_hf = model_hf.state_dict()
    
    # SmolLM2-135M config
    config = LlamaConfig(
        vocab_size=49152,
        block_size=2048,
        n_layer=30,
        n_head=9,
        n_kv_head=3,
        n_embd=576,
        intermediate_size=1536,
        dropout=0.0,
        bias=False,
        rms_norm_eps=1e-05,
        rope_theta=10000.0
    )
    
    print("Instantiating Custom MiniLlama...")
    model = MiniLlama(config)
    sd = model.state_dict()
    
    # The names in MiniLlama perfectly match the huggingface Llama structure (minus 'model.' prefix)!
    keys = [k for k in sd_hf.keys()]
    
    mapped_weights = 0
    for k in keys:
        target_key = k.replace("model.", "")
        
        if target_key in sd:
            sd[target_key].copy_(sd_hf[k])
            mapped_weights += 1
        else:
            print(f"Unmapped key: {k} -> {target_key}")

    print(f"Successfully mapped {mapped_weights} tensors.")
    
    out_dir = ROOT / "runs" / "pretrained"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "smollm2_135M.pt"
    
    torch.save({
        "model_state_dict": sd,
    }, out_path)
    print(f"Saved custom weights to {out_path}")

if __name__ == "__main__":
    map_smollm_weights()
