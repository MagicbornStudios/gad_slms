# SKELETON: deprecated 2026-05-06 reason: Phase 02 standalone reasoning trainer; replaced by scripts/18_stage25_finetune.py + TRL+PEFT per slm-learning-013. Marker only; move to tmp/museum/ on age threshold.
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import sys

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from slm_from_scratch.model import GPTConfig, MiniGPT
from slm_from_scratch.tokenizer import CharTokenizer
from slm_from_scratch.training import estimate_loss, get_batch, load_text, pick_device, split_train_val


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a tiny GPT on synthetic reasoning traces.")
    parser.add_argument("--text", type=Path, default=Path("data/reasoning.txt"))
    parser.add_argument("--out", type=Path, default=Path("runs/reasoner"))
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--steps", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--n-layer", type=int, default=4)
    parser.add_argument("--n-head", type=int, default=4)
    parser.add_argument("--n-embd", type=int, default=128)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--eval-interval", type=int, default=100)
    parser.add_argument("--eval-iters", type=int, default=20)
    args = parser.parse_args()

    if not args.text.exists():
        raise FileNotFoundError(f"Missing {args.text}. Run scripts/02_make_reasoning_data.py first.")

    text = load_text(args.text)
    tokenizer = CharTokenizer.from_text(text)
    ids = torch.tensor(tokenizer.encode(text), dtype=torch.long)
    train_data, val_data = split_train_val(ids, val_fraction=0.1)
    device = pick_device(args.device)

    config = GPTConfig(
        vocab_size=tokenizer.vocab_size,
        block_size=args.block_size,
        n_layer=args.n_layer,
        n_head=args.n_head,
        n_embd=args.n_embd,
        dropout=args.dropout,
    )
    model = MiniGPT(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)

    print(f"device={device}")
    print(f"vocab_size={tokenizer.vocab_size}")
    print(f"parameters={model.num_parameters():,}")
    args.out.mkdir(parents=True, exist_ok=True)

    for step in range(args.steps + 1):
        if step % args.eval_interval == 0:
            losses = estimate_loss(
                model=model,
                train_data=train_data,
                val_data=val_data,
                batch_size=args.batch_size,
                block_size=args.block_size,
                device=device,
                eval_iters=args.eval_iters,
            )
            print(f"step={step} train_loss={losses['train']:.4f} val_loss={losses['val']:.4f}")

        x, y = get_batch(train_data, args.batch_size, args.block_size, device)
        _, loss, _ = model(x, y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

    checkpoint = {
        "model_state_dict": model.state_dict(),
        "config": asdict(config),
        "tokenizer": tokenizer.to_state(),
        "train_args": vars(args),
    }
    torch.save(checkpoint, args.out / "model.pt")
    print(f"saved {args.out / 'model.pt'}")


if __name__ == "__main__":
    main()
