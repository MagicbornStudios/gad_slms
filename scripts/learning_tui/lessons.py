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
)
