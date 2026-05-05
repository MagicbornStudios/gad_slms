"""
Stage 2: Reasoning Training (Chain-of-Thought Fine-Tuning)

After SFT teaches FORMAT (how to respond), this stage teaches REASONING
(how to THINK before responding). We train the model on examples where
the assistant explicitly shows its reasoning steps:

  User: "What file handles the chat input in the TUI?"
  Assistant: "<think>
  Let me trace through the TUI architecture:
  1. The entrypoint is scripts/06_learning_tui.py
  2. It launches SLMLearningApp from scripts/learning_tui/app.py
  3. app.py pushes ChatScreen on mount
  4. ChatScreen is in scripts/learning_tui/chat_screen.py
  5. The input widget is #chat-composer, an Input widget
  6. on_input_submitted handles the submit event
  </think>
  The chat input is handled by `chat_screen.py`. Specifically, the `#chat-composer`
  Input widget captures user text, and `on_input_submitted` processes it."

This is the technique behind o1/o3 and Claude's extended thinking.
The model learns to generate a <think> block before answering,
which forces it to decompose problems before committing to a response.
"""

from __future__ import annotations

import argparse
import gc
import json
import random
import sys
import time
from pathlib import Path

import torch
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from slm_from_scratch.model import LlamaConfig, MiniLlama
from slm_from_scratch.training import pick_device


def generate_reasoning_pairs(corpus_path: Path, max_pairs: int = 100) -> list[list[dict]]:
    """Generate chain-of-thought reasoning examples from the monorepo."""
    text = corpus_path.read_text(encoding="utf-8")
    blocks = text.split("<|file_start|>\nPath: ")
    
    # Build a file index for cross-referencing
    file_index = {}
    for block in blocks[1:]:
        path_end = block.find("\n\n")
        if path_end == -1:
            continue
        file_path = block[:path_end].strip()
        content = block[path_end+2:].split("\n<|file_end|>")[0]
        if 50 < len(content) < 2000:
            file_index[file_path] = content

    pairs = []
    file_paths = list(file_index.keys())
    
    # Template 1: Trace dependency chains
    for path in random.sample(file_paths, min(max_pairs // 3, len(file_paths))):
        content = file_index[path]
        basename = path.split("/")[-1] if "/" in path else path
        dirname = path.rsplit("/", 1)[0] if "/" in path else "root"
        
        # Extract imports for reasoning
        imports = [line.strip() for line in content.split("\n") 
                   if line.strip().startswith(("import ", "from ", "require("))][:5]
        
        import_reasoning = "\n".join(f"  {i+1}. {imp}" for i, imp in enumerate(imports)) if imports else "  No imports found."
        
        pairs.append([
            {"role": "user", "content": f"What are the dependencies of {basename}?"},
            {"role": "assistant", "content": (
                f"<think>\n"
                f"Let me trace the imports in {path}:\n"
                f"{import_reasoning}\n"
                f"This file is in the {dirname} directory.\n"
                f"</think>\n"
                f"The file `{basename}` has the following dependencies:\n"
                f"{import_reasoning}"
            )},
        ])

    # Template 2: Architecture reasoning
    for path in random.sample(file_paths, min(max_pairs // 3, len(file_paths))):
        content = file_index[path]
        basename = path.split("/")[-1] if "/" in path else path
        
        # Count classes and functions
        classes = [l.strip() for l in content.split("\n") if l.strip().startswith("class ")]
        functions = [l.strip() for l in content.split("\n") if l.strip().startswith("def ") or l.strip().startswith("async def ")]
        
        pairs.append([
            {"role": "user", "content": f"Analyze the structure of {basename}. What patterns does it use?"},
            {"role": "assistant", "content": (
                f"<think>\n"
                f"Let me analyze {path}:\n"
                f"  Classes found: {len(classes)}\n"
                f"  Functions found: {len(functions)}\n"
                f"  File size: {len(content)} characters\n"
                f"  {'This is a large file that may need refactoring.' if len(content) > 1500 else 'This is a focused, single-responsibility file.'}\n"
                f"</think>\n"
                f"`{basename}` contains {len(classes)} class(es) and {len(functions)} function(s). "
                f"{'It follows the single-responsibility principle.' if len(classes) <= 1 else 'It contains multiple classes and may benefit from decomposition.'}"
            )},
        ])

    # Template 3: Debugging reasoning
    for path in random.sample(file_paths, min(max_pairs // 3, len(file_paths))):
        content = file_index[path]
        basename = path.split("/")[-1] if "/" in path else path
        
        pairs.append([
            {"role": "user", "content": f"If {basename} throws an ImportError, how would you debug it?"},
            {"role": "assistant", "content": (
                f"<think>\n"
                f"An ImportError in {path} could mean:\n"
                f"  1. A dependency is not installed in the virtual environment\n"
                f"  2. The Python path doesn't include the parent directory\n"
                f"  3. A circular import between modules\n"
                f"  4. The imported module has a syntax error\n"
                f"Steps to debug:\n"
                f"  1. Run: python -m py_compile {path}\n"
                f"  2. Check if the import target exists on disk\n"
                f"  3. Verify sys.path includes the source root\n"
                f"</think>\n"
                f"To debug an ImportError in `{basename}`:\n"
                f"1. Compile-check the file: `python -m py_compile {path}`\n"
                f"2. Verify the imported module exists on disk\n"
                f"3. Ensure `sys.path` includes the project's `src/` directory\n"
                f"4. Check for circular imports between modules"
            )},
        ])
    
    random.shuffle(pairs)
    return pairs[:max_pairs]


def tokenize_conversation(tokenizer, conversation: list[dict], max_length: int = 512) -> dict:
    text = tokenizer.apply_chat_template(conversation, tokenize=False, add_generation_prompt=False)
    tokens = tokenizer.encode(text, truncation=True, max_length=max_length)
    return {
        "input_ids": torch.tensor(tokens, dtype=torch.long),
        "labels": torch.tensor(tokens, dtype=torch.long),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2: Chain-of-Thought Reasoning Training")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data" / "monorepo_corpus.txt")
    parser.add_argument("--ckpt", type=Path, default=ROOT / "runs" / "finetuned" / "sft_model.pt")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "finetuned" / "reasoning_model.pt")
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--max-pairs", type=int, default=100)
    parser.add_argument("--block-size", type=int, default=512)
    args = parser.parse_args()

    if not args.corpus.exists():
        raise FileNotFoundError(f"Missing {args.corpus}.")
    
    device = pick_device(args.device)
    print(f"Device: {device}")

    try:
        tokenizer = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolLM2-135M-Instruct", local_files_only=True)
    except OSError:
        tokenizer = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolLM2-135M-Instruct")

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Generate reasoning pairs
    print(f"Generating chain-of-thought reasoning pairs...")
    pairs = generate_reasoning_pairs(args.corpus, max_pairs=args.max_pairs)
    print(f"Generated {len(pairs)} reasoning pairs with <think> blocks.")

    # Save for inspection
    pairs_path = ROOT / "data" / "reasoning_pairs.json"
    with open(pairs_path, "w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=2)
    print(f"Saved reasoning pairs to {pairs_path}")

    # Tokenize
    tokenized = [tokenize_conversation(tokenizer, conv, max_length=args.block_size) for conv in pairs]

    # Load model
    config = LlamaConfig(
        vocab_size=49152, block_size=2048, n_layer=30, n_head=9, n_kv_head=3,
        n_embd=576, intermediate_size=1536, dropout=0.1, bias=False,
        rms_norm_eps=1e-05, rope_theta=10000.0,
        gradient_checkpointing=True,
    )
    model = MiniLlama(config).to(device)

    if args.ckpt.exists():
        print(f"Loading SFT checkpoint from {args.ckpt}")
        checkpoint = torch.load(args.ckpt, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint['model_state_dict'])
    else:
        print(f"WARNING: {args.ckpt} not found. Falling back to pretrained base.")
        base = ROOT / "runs" / "pretrained" / "smollm2_135M.pt"
        if base.exists():
            checkpoint = torch.load(base, map_location=device, weights_only=False)
            model.load_state_dict(checkpoint['model_state_dict'])

    # Use lower LR for reasoning — we don't want to destroy SFT knowledge
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    model.train()

    print(f"\n{'='*60}")
    print(f"STAGE 2: CHAIN-OF-THOUGHT REASONING TRAINING")
    print(f"Parameters: {model.num_parameters():,}")
    print(f"Training examples: {len(tokenized)}")
    print(f"Epochs: {args.epochs}")
    print(f"Learning rate: {args.lr} (lower to preserve SFT knowledge)")
    print(f"{'='*60}\n")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    total_loss = 0
    step = 0
    start_time = time.time()

    for epoch in range(args.epochs):
        random.shuffle(tokenized)
        epoch_loss = 0

        for sample in tokenized:
            ids = sample["input_ids"].unsqueeze(0).to(device)
            if ids.size(1) > config.block_size:
                ids = ids[:, :config.block_size]
            if ids.size(1) < 2:
                continue

            x = ids[:, :-1]
            y = ids[:, 1:]
            with torch.autocast(device_type="cpu", dtype=torch.bfloat16):
                _, loss, _ = model(x, y)

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            loss_val = loss.item()
            del loss
            gc.collect()

            epoch_loss += loss_val
            total_loss += loss_val
            step += 1

            if step % 25 == 0:
                elapsed = time.time() - start_time
                print(f"  step={step:04d} loss={loss_val:.4f} avg={total_loss/step:.4f} elapsed={elapsed:.1f}s")

        avg_epoch = epoch_loss / max(len(tokenized), 1)
        print(f"Epoch {epoch+1}/{args.epochs} — avg_loss={avg_epoch:.4f}")

    torch.save({
        "model_state_dict": model.state_dict(),
        "stage": "reasoning",
        "training_pairs": len(tokenized),
    }, args.out)

    elapsed = time.time() - start_time
    print(f"\nReasoning training complete! Saved to {args.out} ({elapsed:.1f}s)")
    print(f"Next: Run Stage 3 (DPO) with scripts/17_dpo_training.py --ckpt {args.out}")


if __name__ == "__main__":
    main()
