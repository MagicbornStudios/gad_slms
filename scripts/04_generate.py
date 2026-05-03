from __future__ import annotations

import argparse
from pathlib import Path
import sys

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from slm_from_scratch.model import GPTConfig, MiniGPT
from slm_from_scratch.tokenizer import CharTokenizer
from slm_from_scratch.training import pick_device


def load_model(ckpt_path: Path, device: torch.device) -> tuple[MiniGPT, CharTokenizer]:
    checkpoint = torch.load(ckpt_path, map_location=device)
    tokenizer = CharTokenizer.from_state(checkpoint["tokenizer"])
    config = GPTConfig(**checkpoint["config"])
    model = MiniGPT(config).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, tokenizer


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate text from a trained MiniGPT checkpoint.")
    parser.add_argument("--ckpt", type=Path, default=Path("runs/reasoner/model.pt"))
    parser.add_argument("--prompt", type=str, required=True)
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--max-new-tokens", type=int, default=180)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=40)
    args = parser.parse_args()

    device = pick_device(args.device)
    model, tokenizer = load_model(args.ckpt, device)
    context = torch.tensor([tokenizer.encode(args.prompt)], dtype=torch.long, device=device)
    output = model.generate(
        context,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
    )
    print(tokenizer.decode(output[0].tolist()))


if __name__ == "__main__":
    main()
