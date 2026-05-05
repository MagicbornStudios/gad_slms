"""
Stage 3: Direct Preference Optimization (DPO)

This is the JUDGMENT stage. After SFT (format) and Reasoning (thinking),
DPO teaches the model to PREFER good responses over bad ones.

Traditional RLHF requires:
  1. Train a separate Reward Model
  2. Use PPO to optimize the policy against the reward
  This is extremely expensive and unstable.

DPO (Rafailov et al. 2023) skips the Reward Model entirely.
Instead, you provide PREFERENCE PAIRS:
  - (prompt, chosen_response, rejected_response)

The DPO loss directly pushes the model to:
  - Increase the probability of generating the CHOSEN response
  - Decrease the probability of generating the REJECTED response

The math: L_DPO = -log(σ(β * (log π(chosen) - log π_ref(chosen) - log π(rejected) + log π_ref(rejected))))

Where:
  π     = the model being trained (policy)
  π_ref = frozen copy of the model before DPO (reference)
  β     = temperature controlling how much we deviate from reference
  σ     = sigmoid function

The reference model prevents the trained model from deviating too far
from the SFT baseline, which would cause catastrophic forgetting.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import random
import sys
import time
from pathlib import Path
from copy import deepcopy

import torch
import torch.nn.functional as F
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from slm_from_scratch.model import LlamaConfig, MiniLlama
from slm_from_scratch.training import pick_device


def generate_dpo_pairs(corpus_path: Path, max_pairs: int = 80) -> list[dict]:
    """Generate preference pairs: (prompt, chosen, rejected).
    
    For each prompt, we create:
      chosen:   A high-quality response (concise, structured, with reasoning)
      rejected: A low-quality response (verbose, vague, no reasoning)
    
    In production, these would come from human raters ranking model outputs.
    Here, we synthetically construct them to demonstrate the DPO mechanism.
    """
    text = corpus_path.read_text(encoding="utf-8")
    blocks = text.split("<|file_start|>\nPath: ")
    
    file_index = {}
    for block in blocks[1:]:
        path_end = block.find("\n\n")
        if path_end == -1:
            continue
        file_path = block[:path_end].strip()
        content = block[path_end+2:].split("\n<|file_end|>")[0]
        if 100 < len(content) < 2000:
            file_index[file_path] = content
    
    pairs = []
    file_paths = list(file_index.keys())
    
    for path in random.sample(file_paths, min(max_pairs, len(file_paths))):
        content = file_index[path]
        basename = path.split("/")[-1] if "/" in path else path
        
        # Extract real details for quality responses
        lines = content.split("\n")
        func_count = sum(1 for l in lines if l.strip().startswith(("def ", "async def ", "function ")))
        imports = [l.strip() for l in lines if l.strip().startswith(("import ", "from "))][:3]
        
        prompt = f"What does {basename} do and how is it structured?"
        
        # CHOSEN: Structured, specific, references real code
        chosen = (
            f"<think>\n"
            f"Analyzing {path}: {len(lines)} lines, {func_count} functions.\n"
            f"</think>\n"
            f"`{basename}` is a {len(lines)}-line module with {func_count} function(s). "
        )
        if imports:
            chosen += f"It depends on: {', '.join(imp.split()[-1] for imp in imports)}. "
        chosen += "It follows GAD ecosystem conventions."
        
        # REJECTED: Vague, no specifics, unhelpful
        rejected = (
            f"This file does stuff related to the project. "
            f"It has some code in it that does things. "
            f"I think it might be important but I'm not sure. "
            f"You should probably look at it yourself to understand what it does."
        )
        
        pairs.append({
            "prompt": prompt,
            "chosen": chosen,
            "rejected": rejected,
        })
    
    random.shuffle(pairs)
    return pairs


def compute_log_probs(model, input_ids: torch.Tensor, target_ids: torch.Tensor) -> torch.Tensor:
    """Compute the sum of log probabilities of the target tokens given the input."""
    logits, _, _ = model(input_ids)
    # Shift logits to align with targets
    shift_logits = logits[:, :-1, :].contiguous()
    shift_targets = target_ids[:, 1:].contiguous()
    
    log_probs = F.log_softmax(shift_logits, dim=-1)
    target_log_probs = log_probs.gather(2, shift_targets.unsqueeze(2)).squeeze(2)
    
    return target_log_probs.sum(dim=-1)


def dpo_loss(
    policy_chosen_logps: torch.Tensor,
    policy_rejected_logps: torch.Tensor,
    ref_chosen_logps: torch.Tensor,
    ref_rejected_logps: torch.Tensor,
    beta: float = 0.1,
) -> torch.Tensor:
    """Compute the DPO loss.
    
    L = -log(σ(β * ((log π(chosen) - log π_ref(chosen)) - (log π(rejected) - log π_ref(rejected)))))
    """
    chosen_rewards = beta * (policy_chosen_logps - ref_chosen_logps)
    rejected_rewards = beta * (policy_rejected_logps - ref_rejected_logps)
    
    loss = -F.logsigmoid(chosen_rewards - rejected_rewards).mean()
    return loss


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3: Direct Preference Optimization (DPO)")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data" / "monorepo_corpus.txt")
    parser.add_argument("--ckpt", type=Path, default=ROOT / "runs" / "finetuned" / "reasoning_model.pt")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "finetuned" / "dr_stein.pt")
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=5e-6)
    parser.add_argument("--beta", type=float, default=0.1, help="DPO temperature parameter")
    parser.add_argument("--max-pairs", type=int, default=80)
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

    # Generate DPO preference pairs
    print("Generating DPO preference pairs...")
    pairs = generate_dpo_pairs(args.corpus, max_pairs=args.max_pairs)
    print(f"Generated {len(pairs)} preference pairs (chosen vs rejected).")

    # Save for inspection
    pairs_path = ROOT / "data" / "dpo_pairs.json"
    with open(pairs_path, "w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=2)
    print(f"Saved DPO pairs to {pairs_path}")

    # Tokenize pairs
    print("Tokenizing preference pairs...")
    tokenized_pairs = []
    for pair in pairs:
        chosen_conv = [
            {"role": "user", "content": pair["prompt"]},
            {"role": "assistant", "content": pair["chosen"]},
        ]
        rejected_conv = [
            {"role": "user", "content": pair["prompt"]},
            {"role": "assistant", "content": pair["rejected"]},
        ]
        
        chosen_text = tokenizer.apply_chat_template(chosen_conv, tokenize=False, add_generation_prompt=False)
        rejected_text = tokenizer.apply_chat_template(rejected_conv, tokenize=False, add_generation_prompt=False)
        
        chosen_ids = tokenizer.encode(chosen_text, truncation=True, max_length=args.block_size)
        rejected_ids = tokenizer.encode(rejected_text, truncation=True, max_length=args.block_size)
        
        tokenized_pairs.append({
            "chosen_ids": torch.tensor(chosen_ids, dtype=torch.long),
            "rejected_ids": torch.tensor(rejected_ids, dtype=torch.long),
        })

    # Load model
    config = LlamaConfig(
        vocab_size=49152, block_size=2048, n_layer=30, n_head=9, n_kv_head=3,
        n_embd=576, intermediate_size=1536, dropout=0.0, bias=False,
        rms_norm_eps=1e-05, rope_theta=10000.0
    )
    
    # Policy model (will be trained)
    policy_model = MiniLlama(config).to(device)
    
    if args.ckpt.exists():
        print(f"Loading reasoning checkpoint from {args.ckpt}")
        checkpoint = torch.load(args.ckpt, map_location=device, weights_only=False)
        policy_model.load_state_dict(checkpoint['model_state_dict'])
    else:
        print(f"WARNING: {args.ckpt} not found. Falling back to pretrained base.")
        base = ROOT / "runs" / "pretrained" / "smollm2_135M.pt"
        if base.exists():
            checkpoint = torch.load(base, map_location=device, weights_only=False)
            policy_model.load_state_dict(checkpoint['model_state_dict'])

    # Reference model (frozen copy — prevents catastrophic forgetting)
    ref_model = MiniLlama(config).to(device)
    ref_model.load_state_dict(policy_model.state_dict())
    ref_model.eval()
    for param in ref_model.parameters():
        param.requires_grad = False

    optimizer = torch.optim.AdamW(policy_model.parameters(), lr=args.lr, weight_decay=0.01)
    policy_model.train()

    print(f"\n{'='*60}")
    print(f"STAGE 3: DIRECT PREFERENCE OPTIMIZATION (DPO)")
    print(f"Parameters: {policy_model.num_parameters():,}")
    print(f"Preference pairs: {len(tokenized_pairs)}")
    print(f"Epochs: {args.epochs}")
    print(f"Beta (KL temperature): {args.beta}")
    print(f"Learning rate: {args.lr} (very low to preserve reasoning)")
    print(f"{'='*60}\n")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    total_loss = 0
    total_chosen_reward = 0
    total_rejected_reward = 0
    step = 0
    start_time = time.time()

    for epoch in range(args.epochs):
        random.shuffle(tokenized_pairs)
        epoch_loss = 0

        for pair in tokenized_pairs:
            chosen_ids = pair["chosen_ids"].unsqueeze(0).to(device)
            rejected_ids = pair["rejected_ids"].unsqueeze(0).to(device)
            
            # Truncate
            if chosen_ids.size(1) > config.block_size:
                chosen_ids = chosen_ids[:, :config.block_size]
            if rejected_ids.size(1) > config.block_size:
                rejected_ids = rejected_ids[:, :config.block_size]
            if chosen_ids.size(1) < 2 or rejected_ids.size(1) < 2:
                continue

            # Compute log probs for policy (bfloat16 to halve memory)
            with torch.autocast(device_type="cpu", dtype=torch.bfloat16):
                policy_chosen_logps = compute_log_probs(policy_model, chosen_ids, chosen_ids)
                policy_rejected_logps = compute_log_probs(policy_model, rejected_ids, rejected_ids)

            # Compute log probs for reference (frozen, no grad)
            with torch.no_grad(), torch.autocast(device_type="cpu", dtype=torch.bfloat16):
                ref_chosen_logps = compute_log_probs(ref_model, chosen_ids, chosen_ids)
                ref_rejected_logps = compute_log_probs(ref_model, rejected_ids, rejected_ids)

            # DPO loss
            loss = dpo_loss(
                policy_chosen_logps, policy_rejected_logps,
                ref_chosen_logps, ref_rejected_logps,
                beta=args.beta,
            )

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy_model.parameters(), 1.0)
            optimizer.step()

            loss_val = loss.item()

            # Track reward margins before freeing graph
            with torch.no_grad():
                chosen_reward = (policy_chosen_logps - ref_chosen_logps).item()
                rejected_reward = (policy_rejected_logps - ref_rejected_logps).item()
                total_chosen_reward += chosen_reward
                total_rejected_reward += rejected_reward

            del loss, policy_chosen_logps, policy_rejected_logps
            del ref_chosen_logps, ref_rejected_logps
            gc.collect()

            epoch_loss += loss_val
            total_loss += loss_val
            step += 1

            if step % 20 == 0:
                elapsed = time.time() - start_time
                margin = (total_chosen_reward - total_rejected_reward) / step
                print(
                    f"  step={step:04d} loss={loss_val:.4f} "
                    f"reward_margin={margin:+.4f} "
                    f"elapsed={elapsed:.1f}s"
                )

        avg_epoch = epoch_loss / max(len(tokenized_pairs), 1)
        print(f"Epoch {epoch+1}/{args.epochs} — avg_loss={avg_epoch:.4f}")

    # Save final Dr. Stein checkpoint
    torch.save({
        "model_state_dict": policy_model.state_dict(),
        "stage": "dpo",
        "training_pairs": len(tokenized_pairs),
        "beta": args.beta,
    }, args.out)

    elapsed = time.time() - start_time
    final_margin = (total_chosen_reward - total_rejected_reward) / max(step, 1)
    print(f"\n{'='*60}")
    print(f"DPO COMPLETE!")
    print(f"Saved Dr. Stein to {args.out}")
    print(f"Final reward margin: {final_margin:+.4f}")
    print(f"  (positive = model prefers chosen over rejected ✓)")
    print(f"Total time: {elapsed:.1f}s")
    print(f"{'='*60}")
    print(f"\nDr. Stein is now fully trained through all 3 stages:")
    print(f"  Stage 1 (SFT):       Instruction following ✓")
    print(f"  Stage 2 (Reasoning): Chain-of-thought <think> blocks ✓")
    print(f"  Stage 3 (DPO):       Quality judgment ✓")


if __name__ == "__main__":
    main()
