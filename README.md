# Small Language Model With Reasoning: Step-by-Step Course

This is a teaching repo for building a tiny GPT-style language model from scratch, then training it on synthetic reasoning traces.

The goal is not to compete with real LLMs. The goal is to understand the full stack:

1. Tokenization
2. Next-token prediction
3. Causal self-attention
4. Transformer blocks
5. Training loop
6. Sampling
7. Reasoning trace data
8. Evaluation
9. Later upgrade path into real small language models with SFT, LoRA, evals, and agent tooling

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Step 1: Create synthetic reasoning data

```bash
python scripts/02_make_reasoning_data.py --out data/reasoning.txt --n 20000 --max-n 99
```

This creates examples like:

```text
Question: What is 12 + 7?
Reasoning: Break the problem into numbers. 12 plus 7 equals 19.
Answer: 19
<|end|>
```

## Step 2: Train a tiny reasoning language model

CPU-safe starter run:

```bash
python scripts/03_train_reasoning_lm.py --text data/reasoning.txt --out runs/reasoner --device cpu --steps 500 --batch-size 16 --n-layer 2 --n-head 2 --n-embd 64
```

Better local GPU/MPS run:

```bash
python scripts/03_train_reasoning_lm.py --text data/reasoning.txt --out runs/reasoner --device auto --steps 3000 --batch-size 32 --n-layer 4 --n-head 4 --n-embd 128
```

## Step 3: Generate an answer

```bash
python scripts/04_generate.py --ckpt runs/reasoner/model.pt --prompt $'Question: What is 12 + 7?\nReasoning:' --device auto --max-new-tokens 160 --temperature 0.2
```

Expected shape:

```text
Question: What is 12 + 7?
Reasoning: Break the problem into numbers. 12 plus 7 equals 19.
Answer: 19
<|end|>
```

## Step 4: Evaluate the tiny model

```bash
python scripts/05_eval_reasoning.py --ckpt runs/reasoner/model.pt --device auto --n 50 --max-n 99
```

This checks generated answers on addition questions.

## What this model actually learns

This model is learning next-character prediction. Its reasoning behavior comes from the training format:

```text
Question -> Reasoning trace -> Answer
```

That is a tiny local version of chain-of-thought distillation. It does not prove the model has robust abstract reasoning. It proves you can train a model to emit useful intermediate reasoning patterns and measure whether they help answer simple tasks.

## Upgrade path

After this repo is understood, move in this order:

1. Replace char tokenizer with BPE or SentencePiece.
2. Train on a bigger mixed corpus: general text + code + reasoning traces.
3. Add instruction format: system/user/assistant.
4. Fine-tune a pretrained small model like Qwen2.5 0.5B/1.5B or Llama 3.2 1B/3B.
5. Use LoRA instead of full fine-tuning.
6. Add verifier/reranker: sample several reasoning traces, score answers, keep best.
7. Add tool use: calculator, Python REPL, retrieval.
8. Evaluate with dynamic/contamination-resistant tasks.
9. Wrap the model in an agent runtime.

## Files

- `src/slm_from_scratch/tokenizer.py` — simple character tokenizer
- `src/slm_from_scratch/model.py` — full GPT-style Transformer implementation
- `src/slm_from_scratch/training.py` — batching, device selection, loss estimation
- `scripts/02_make_reasoning_data.py` — synthetic reasoning dataset generator
- `scripts/03_train_reasoning_lm.py` — training loop for reasoning traces
- `scripts/04_generate.py` — text generation
- `scripts/05_eval_reasoning.py` — basic reasoning eval
