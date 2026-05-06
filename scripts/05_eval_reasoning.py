# SKELETON: deprecated 2026-05-06 reason: Phase 02 reasoning eval; replaced by scripts/eval_benchmark_matrix.py + scripts/eval_gsm8k.py + scripts/eval_humaneval.py. Marker only; move to tmp/museum/ on age threshold.
from __future__ import annotations

import argparse
import random
import re
from pathlib import Path
import sys

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from slm_from_scratch.model import GPTConfig, MiniGPT
from slm_from_scratch.tokenizer import CharTokenizer
from slm_from_scratch.training import pick_device

ANSWER_RE = re.compile(r"Answer:\s*(-?\d+)")


def load_model(ckpt_path: Path, device: torch.device) -> tuple[MiniGPT, CharTokenizer]:
    checkpoint = torch.load(ckpt_path, map_location=device)
    tokenizer = CharTokenizer.from_state(checkpoint["tokenizer"])
    config = GPTConfig(**checkpoint["config"])
    model = MiniGPT(config).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, tokenizer


def ask(model: MiniGPT, tokenizer: CharTokenizer, device: torch.device, prompt: str, max_new_tokens: int) -> str:
    context = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long, device=device)
    output = model.generate(context, max_new_tokens=max_new_tokens, temperature=0.2, top_k=20)
    return tokenizer.decode(output[0].tolist())


def extract_numeric_answer(text: str) -> int | None:
    matches = ANSWER_RE.findall(text)
    if not matches:
        return None
    try:
        return int(matches[-1])
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate basic arithmetic reasoning of a tiny checkpoint.")
    parser.add_argument("--ckpt", type=Path, default=Path("runs/reasoner/model.pt"))
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--max-n", type=int, default=99)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    device = pick_device(args.device)
    model, tokenizer = load_model(args.ckpt, device)

    correct = 0
    failures: list[tuple[str, int, int | None, str]] = []
    for _ in range(args.n):
        a = rng.randint(0, args.max_n)
        b = rng.randint(0, args.max_n)
        expected = a + b
        prompt = f"Question: What is {a} + {b}?\nReasoning:"
        text = ask(model, tokenizer, device, prompt, max_new_tokens=120)
        got = extract_numeric_answer(text)
        if got == expected:
            correct += 1
        else:
            failures.append((prompt, expected, got, text))

    accuracy = correct / args.n
    print(f"addition_accuracy={accuracy:.2%} correct={correct}/{args.n}")
    if failures:
        print("\nSample failures:")
        for prompt, expected, got, text in failures[:5]:
            print("-" * 80)
            print(f"prompt={prompt!r}")
            print(f"expected={expected} got={got}")
            print(text)


if __name__ == "__main__":
    main()
