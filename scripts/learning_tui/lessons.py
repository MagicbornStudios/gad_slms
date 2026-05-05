from __future__ import annotations

from .models import Lesson
from .settings import PYTHON


LESSONS: tuple[Lesson, ...] = (
    Lesson(
        id="tokenizer",
        title="Lesson 1 — Tokenization",
        goal="See how text becomes token IDs, then back into text.",
        command=(PYTHON, "scripts/00_tokenizer_lesson.py"),
        body="""
# Lesson 1 — Tokenization

An LLM does not read raw text directly. It reads numbers.

This lesson runs a tiny character tokenizer:

```text
text -> token IDs -> text
```

You should watch for three things:

1. The vocabulary table maps each character to one integer.
2. Encoding converts characters into token IDs.
3. Decoding reconstructs the original text.

## Command this lesson runs

```bash
python scripts/00_tokenizer_lesson.py
```

## Success condition

The output should end with a round-trip check that says `True`.
""".strip(),
    ),
    Lesson(
        id="make-data",
        title="Lesson 2 — Generate reasoning data",
        goal="Create synthetic Question / Reasoning / Answer examples.",
        command=(
            PYTHON,
            "scripts/02_make_reasoning_data.py",
            "--out",
            "data/reasoning.txt",
            "--n",
            "20000",
            "--max-n",
            "99",
        ),
        body="""
# Lesson 2 — Generate Reasoning Data

Now we generate a small training corpus.

The examples have this shape:

```text
Question: What is 12 + 7?
Reasoning: Break the problem into numbers. 12 plus 7 equals 19.
Answer: 19
<|end|>
```

This teaches a simple pattern:

```text
question -> intermediate reasoning trace -> final answer
```

## Command this lesson runs

```bash
python scripts/02_make_reasoning_data.py --out data/reasoning.txt --n 20000 --max-n 99
```

## Success condition

You should get a generated `data/reasoning.txt` file.
""".strip(),
    ),
    Lesson(
        id="inspect-data",
        title="Lesson 3 — Inspect the dataset",
        goal="Look at the actual text the model will train on.",
        command=(PYTHON, "scripts/07_inspect_reasoning_data.py", "--path", "data/reasoning.txt"),
        body="""
# Lesson 3 — Inspect the Dataset

Before training, inspect the data directly.

This matters because the model can only learn patterns present in the training text.

Look for:

1. consistent formatting,
2. clear answer boundaries,
3. `<|end|>` separators,
4. examples that are simple enough for a tiny model.

## Command this lesson runs

```bash
python scripts/07_inspect_reasoning_data.py --path data/reasoning.txt
```

## Success condition

You should see several generated examples printed in the output pane.
""".strip(),
    ),
    Lesson(
        id="train-smoke",
        title="Lesson 4 — Train a tiny smoke-test model",
        goal="Run a short training job to prove the full model pipeline works.",
        command=(
            PYTHON,
            "scripts/03_train_reasoning_lm.py",
            "--text",
            "data/reasoning.txt",
            "--out",
            "runs/reasoner-smoke",
            "--device",
            "auto",
            "--steps",
            "150",
            "--batch-size",
            "16",
            "--block-size",
            "128",
            "--n-layer",
            "2",
            "--n-head",
            "2",
            "--n-embd",
            "64",
            "--eval-interval",
            "25",
            "--eval-iters",
            "5",
        ),
        body="""
# Lesson 4 — Train a Tiny Smoke-Test Model

This is not the full training run. It is a quick proof that the pipeline works.

The training loop does this:

```text
batch of token IDs
  -> model predicts next token logits
  -> cross-entropy loss
  -> backpropagation
  -> optimizer step
```

The important number is loss. It should generally move downward over time.

## Command this lesson runs

```bash
python scripts/03_train_reasoning_lm.py --text data/reasoning.txt --out runs/reasoner-smoke --device auto --steps 150 --batch-size 16 --block-size 128 --n-layer 2 --n-head 2 --n-embd 64 --eval-interval 25 --eval-iters 5
```

## Success condition

You should get `runs/reasoner-smoke/model.pt`.

## Note

If this fails on Python 3.14, recreate the virtual environment with Python 3.11 or 3.12. PyTorch wheel support tends to lag the newest Python releases.
""".strip(),
    ),
    Lesson(
        id="generate",
        title="Lesson 5 — Generate from the model",
        goal="Ask the trained model to continue a reasoning prompt.",
        command=(
            PYTHON,
            "scripts/04_generate.py",
            "--ckpt",
            "runs/reasoner-smoke/model.pt",
            "--prompt",
            "Question: What is 12 + 7?\nReasoning:",
            "--device",
            "auto",
            "--max-new-tokens",
            "160",
            "--temperature",
            "0.2",
        ),
        body="""
# Lesson 5 — Generate From the Model

Now the trained model receives a partial prompt and predicts continuation tokens.

The model is doing:

```text
given previous tokens -> predict next token -> append it -> repeat
```

Low temperature makes the output less random.

## Command this lesson runs

```bash
python scripts/04_generate.py --ckpt runs/reasoner-smoke/model.pt --prompt "Question: What is 12 + 7?\nReasoning:" --device auto --max-new-tokens 160 --temperature 0.2
```

## Success condition

You should see the model produce text after `Reasoning:`.

Early output may be ugly. That is normal after a tiny smoke-test run.
""".strip(),
    ),
    Lesson(
        id="evaluate",
        title="Lesson 6 — Evaluate simple reasoning accuracy",
        goal="Measure whether the model answers simple generated questions correctly.",
        command=(
            PYTHON,
            "scripts/05_eval_reasoning.py",
            "--ckpt",
            "runs/reasoner-smoke/model.pt",
            "--device",
            "auto",
            "--n",
            "25",
            "--max-n",
            "99",
        ),
        body="""
# Lesson 6 — Evaluate Reasoning Accuracy

Pretty generations are not enough.

This lesson asks generated arithmetic questions and checks whether the final answer is correct.

Track:

1. exact answer accuracy,
2. formatting failures,
3. malformed answers,
4. hallucinated reasoning,
5. whether more training improves the score.

## Command this lesson runs

```bash
python scripts/05_eval_reasoning.py --ckpt runs/reasoner-smoke/model.pt --device auto --n 25 --max-n 99
```

## Success condition

You should get an accuracy result. It may be low after the smoke-test run. That is expected.
""".strip(),
    ),
    Lesson(
        id="source-tour",
        title="Lesson 7 — Source tour: Transformer pieces",
        goal="Map the source files to the LLM concepts they implement.",
        command=None,
        body="""
# Lesson 7 — Source Tour: Transformer Pieces

Open these files in VS Code:

```text
src/slm_from_scratch/tokenizer.py
src/slm_from_scratch/model.py
src/slm_from_scratch/training.py
```

## What each file owns

`tokenizer.py`

- text -> token IDs
- token IDs -> text
- vocabulary state

`model.py`

- GPT config
- causal self-attention
- MLP
- Transformer block
- MiniGPT model
- autoregressive generation

`training.py`

- batch sampling
- train/validation split
- loss estimation
- device selection

## What to understand before moving on

The core training objective is next-token prediction:

```text
input:  token 0, token 1, token 2, ... token n
 target: token 1, token 2, token 3, ... token n+1
```

That objective is simple. The model architecture is what makes it powerful.
""".strip(),
    ),
    Lesson(
        id="gpt2-arch",
        title="Lesson 8 — The GPT-2 Architecture (2019)",
        goal="Understand the classic transformer architecture that started the LLM revolution.",
        command=None,
        body="""
# Lesson 8 — The GPT-2 Architecture

GPT-2 proved that a simple, decoder-only transformer could generate coherent text if trained on enough data. Our original `model.py` was built precisely to this specification.

## The Architecture Graph

```text
       [Input Tokens]
             │
[Token Embed] + [Absolute Positional Embed]
             │
      ┌──────┴─────────┐
      │ LayerNorm      │
      │ Multi-Head Attn│
      │ + Residual Add │
      │ LayerNorm      │
      │ MLP (GELU)     │
      │ + Residual Add │
      └──────┬─────────┘  x N Layers
             │
        [LayerNorm]
       [Linear Head]
             │
      [Output Logits]
```

## Key Characteristics
1. **Absolute Positional Embeddings:** GPT-2 learns a specific vector for position 0, position 1, up to its max block size (e.g. 1024). It struggles to generalize to longer text.
2. **LayerNorm:** Computes both mean and variance to normalize activations.
3. **Multi-Head Attention (MHA):** Every Attention head has its own Query, Key, and Value weights.
4. **GELU:** The Gaussian Error Linear Unit activation function.
""".strip(),
    ),
    Lesson(
        id="llama-arch",
        title="Lesson 9 — The Llama Architecture (Modern)",
        goal="Understand the state-of-the-art transformer architecture used by SmolLM2, Llama-3, and Qwen.",
        command=None,
        body="""
# Lesson 9 — The Llama Architecture

We upgraded `model.py` to this architecture to load modern weights. Almost every core component from GPT-2 was replaced with mathematically superior alternatives.

## The Architecture Graph

```text
       [Input Tokens]
             │
       [Token Embed]   <--- (No absolute positions!)
             │
      ┌──────┴─────────┐
      │ RMSNorm        │
      │ GQA Attention  │ <--- RoPE applied dynamically here
      │ + Residual Add │
      │ RMSNorm        │
      │ SwiGLU MLP     │
      │ + Residual Add │
      └──────┬─────────┘  x N Layers
             │
         [RMSNorm]
       [Linear Head]
             │
      [Output Logits]
```

## Key Upgrades
1. **RoPE (Rotary Positional Embeddings):** Instead of adding position vectors at the start, Llama rotates the Query and Key vectors inside the attention mechanism based on their relative distance.
2. **RMSNorm:** Drops the mean-centering from LayerNorm, computing only the variance. It's strictly faster with no performance loss.
3. **Grouped Query Attention (GQA):** Multiple Query heads share a single Key/Value head. This massively shrinks memory requirements.
4. **SwiGLU:** A gated activation function that uses element-wise multiplication of two linear projections.
""".strip(),
    ),
    Lesson(
        id="arch-compare",
        title="Lesson 10 — GPT-2 vs Llama Comparison",
        goal="Compare the mathematical differences between classic and modern SLMs.",
        command=None,
        body="""
# Lesson 10 — GPT-2 vs Llama Comparison

Why go through the effort of rewriting `model.py`? Because the Llama architecture provides massive efficiency and intelligence gains for the same parameter count.

## Component Comparison

| Feature | GPT-2 (2019) | Llama (Modern) | Primary Benefit |
| :--- | :--- | :--- | :--- |
| **Normalization** | `LayerNorm` | `RMSNorm` | ~10% faster computation by dropping the mean. |
| **Positions** | Absolute | RoPE (Rotary) | Extrapolates to longer sequence lengths flawlessly. |
| **Activation** | `GELU` | `SwiGLU` | Better capacity and gradient flow. |
| **Attention** | Multi-Head (MHA) | Grouped Query (GQA)| Massively reduces KV Cache memory usage. |

## Visualizing MHA vs GQA

```text
MHA (GPT-2): Every Query gets its own Key/Value pair. (Huge memory usage)
Q0 ── K0/V0
Q1 ── K1/V1
Q2 ── K2/V2

GQA (Llama): Multiple Queries share a Key/Value pair. (Very efficient)
Q0 ─┐
Q1 ─┼─ K0/V0
Q2 ─┘
```

Because memory bandwidth (moving data from RAM to the GPU core) is the main bottleneck in SLMs, GQA makes modern models exponentially faster at generation than GPT-2 models of the same size.
""".strip(),
    ),
    Lesson(
        id="frontier-arch",
        title="Lesson 11 — Frontier Architectures (Opus, Gemini)",
        goal="Understand the cutting-edge techniques used by multi-trillion parameter frontier models.",
        command=None,
        body="""
# Lesson 11 — Frontier Architectures

Our `MiniLlama` is a "Dense" model. Every token passes through every weight in the network. This works great for Small Language Models (SLMs) under 10B parameters, but frontier models like GPT-4, Claude 3.5 Opus, and Gemini 1.5 Pro require radically different architectures to scale efficiently.

## 1. Mixture of Experts (MoE)

Instead of having one giant `SwiGLU` MLP in each block, MoE models have multiple smaller MLPs (called "Experts") and a Router. 

```text
       [Input Tokens]
             │
      ┌──────┴─────────┐
      │ RMSNorm        │
      │ GQA Attention  │ 
      │ + Residual Add │
      │ RMSNorm        │
      │   [Router] ────┼──► [Expert 1 MLP] (Used for code)
      │                ├──► [Expert 2 MLP] (Used for math)
      │                └──► [Expert N ...] (Unused this token)
      │ + Residual Add │
      └──────┬─────────┘
             │
```
**Why do this?** In a dense 100B parameter model, a single token requires 100B floating point operations. In a 100B MoE model with 8 experts (where the router picks the best 2), each token only uses ~25B parameters. This makes the model "Trillion-parameter smart" but "Small-parameter fast".

## 2. Native Multimodality (Gemini / GPT-4o)

Early multimodal models (like LLaVA) bolted a separate Vision Transformer onto a pre-trained text model. Modern frontier models (like Gemini 1.5 Pro) are trained from scratch across modalities.

```text
[Audio Waveform] ──► Audio Tokenizer ──┐
[Image Pixels]   ──► Vision Tokenizer ─┼─► [Shared Transformer Blocks]
[Text String]    ──► Text Tokenizer ───┘
```
Because the model learns the exact same embedded space for all three inputs, it can "reason" across audio and text perfectly without losing context in translation.

## 3. Ring Attention & Blockwise Compute

Gemini 1.5 Pro famously supports a 2-Million token context window. Standard Attention scales quadratically $O(N^2)$, meaning 2M tokens would require more VRAM than exists on the planet.
Frontier architectures solve this by chopping the Query and Key matrices into blocks and passing them in a "ring" across dozens of networked GPUs, computing chunks of the attention matrix in parallel without ever materializing the full 2M x 2M matrix in memory.
""".strip(),
    ),
)
