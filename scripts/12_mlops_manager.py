import argparse
import sys
import os
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]

def format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} GB"

def cmd_quantize(args):
    """Casts all 32-bit floats to bfloat16 in .pt files to save 50% disk space."""
    target_dir = args.dir
    print(f"Scanning {target_dir} for unquantized models...")
    
    total_saved = 0
    for pt_file in target_dir.rglob("*.pt"):
        original_size = pt_file.stat().st_size
        print(f"\nProcessing {pt_file.name} (Size: {format_size(original_size)})")
        
        checkpoint = torch.load(pt_file, map_location="cpu", weights_only=False)
        
        if 'model_state_dict' not in checkpoint:
            print("  Skipping: No model_state_dict found.")
            continue
            
        state_dict = checkpoint['model_state_dict']
        quantized = 0
        for k, v in state_dict.items():
            if torch.is_floating_point(v) and v.dtype != torch.bfloat16:
                state_dict[k] = v.to(torch.bfloat16)
                quantized += 1
                
        if quantized == 0:
            print("  Skipping: Model is already fully quantized.")
            continue
            
        print(f"  Quantized {quantized} tensors to bfloat16. Saving...")
        
        # Save to a temporary file first, then replace
        temp_file = pt_file.with_suffix('.pt.tmp')
        torch.save(checkpoint, temp_file)
        
        new_size = temp_file.stat().st_size
        os.replace(temp_file, pt_file)
        
        saved = original_size - new_size
        total_saved += saved
        print(f"  Done! New size: {format_size(new_size)} (Saved {format_size(saved)})")
        
    print(f"\nQuantization Sweep Complete! Total space reclaimed: {format_size(total_saved)}")

def cmd_clean(args):
    """Deletes all checkpoints in a directory to free up space."""
    target_dir = args.dir
    print(f"Cleaning {target_dir}...")
    for pt_file in target_dir.rglob("*.pt"):
        print(f"Deleting {pt_file.name}...")
        pt_file.unlink()
    print("Clean complete.")

def cmd_push(args):
    """Pushes a model to the HuggingFace Hub and deletes the local copy."""
    print("Pushing to HuggingFace requires the `huggingface_hub` package and an active login.")
    print("Run: `huggingface-cli login` first.")
    print(f"Stub: Would push {args.file} to {args.repo_id} and then run os.remove('{args.file}')")

def main():
    parser = argparse.ArgumentParser(description="GAD MLOps Manager: Storage and Quantization")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    parser_q = subparsers.add_parser("quantize", help="Cast float32 weights to bfloat16 to halve disk usage")
    parser_q.add_argument("--dir", type=Path, default=ROOT / "runs", help="Directory to scan")
    
    parser_c = subparsers.add_parser("clean", help="Delete all .pt files in a directory")
    parser_c.add_argument("--dir", type=Path, default=ROOT / "runs" / "evolved", help="Directory to clean")
    
    parser_p = subparsers.add_parser("push", help="Push model to HuggingFace Hub")
    parser_p.add_argument("file", type=Path, help="Path to local .pt file")
    parser_p.add_argument("repo_id", type=str, help="HF repo id (e.g. username/dr_stein)")
    
    args = parser.parse_args()
    
    if args.command == "quantize":
        cmd_quantize(args)
    elif args.command == "clean":
        cmd_clean(args)
    elif args.command == "push":
        cmd_push(args)

if __name__ == "__main__":
    main()
