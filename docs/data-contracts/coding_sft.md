# Coding SFT Data Contract

**Status:** v1, locked 2026-05-08
**Decision refs:** `slm-learning-103`, `slm-learning-107`
**Owner:** Dr. Stein

This contract defines the **target output format** that a coding-SFT
example must teach. Mixing incompatible target formats in one
training run without labels is a known cause of benchmark regression
(see autonomous run 2026-05-07 OCR-LoRA finding: HE –34pp, MBPP –5pp
vs base).

> **Rule of thumb:** if you cannot answer "what shape of code does
> the model output after this row" in one sentence, the row is not
> ready to train on.

## Why this exists

The 7B coder LoRA trained on raw OpenCodeReasoning (OCR) regressed
HumanEval by 34pp and MBPP by 5pp versus the same-size base, despite
a clean monotone loss curve. Hypothesis ranking (autonomous run
2026-05-07):

1. Output-style mismatch — OCR teaches competitive-programming style
   (full programs, `input()`/`print()`, reasoning blocks); HE expects
   function bodies; MBPP expects function definitions.
2. Coder-on-coder distribution shift — the base model is already
   coder-tuned; SFT on a narrow corpus erodes existing
   instruction-following.
3. `<think>...</think>` reasoning blocks burn token budget at
   inference and shift the model toward "think-heavy" outputs.

The data contract below makes (1) impossible by typing every row
with its target format and forbidden styles.

## The five target formats

Each row in a coding-SFT corpus must declare exactly one
`target_format` from this list:

### `function_completion`

The model is given a function signature + docstring and must output
**only the function body, indented under the signature**.

```text
input:  "def add(a, b):\n    \"\"\"Return the sum.\"\"\"\n"
target: "    return a + b\n"
```

Allowed in target:
- statements at the appropriate indent level
- helper inline expressions
- nested `def` / `class` if scope is justified

Forbidden in target:
- `def` line at column 0 (the signature is already in input)
- markdown fences ` ``` `
- prose / explanation
- `<think>...</think>` blocks
- `input()` / `print()` unless explicitly in the docstring contract
- imports (the input prelude is canonical)

Eval shape: HumanEval (sanitized config).

### `full_function_definition`

The model is given a problem description and must output **a
complete function definition including the `def` line**.

```text
input:  "Write a Python function add(a, b) that returns the sum."
target: "def add(a, b):\n    return a + b\n"
```

Allowed in target:
- the full `def` signature
- imports at the top of the function body if needed
- multiple helper functions if the problem requires them

Forbidden in target:
- bare statements at module level
- markdown fences (the eval harness strips them but training data
  should be clean)
- `<think>` blocks
- assertion / test code (the harness adds its own tests)

Eval shape: MBPP, code_smoke.

### `competitive_program`

The model is given a contest-style problem statement and must output
**a full standalone Python program** including stdin reading, stdout
writing, and a runnable `if __name__ == "__main__":` block if needed.

```text
input:  "Read N integers from stdin, output their sum to stdout."
target: "n = int(input())\narr = [int(input()) for _ in range(n)]\nprint(sum(arr))\n"
```

Allowed in target:
- `input()` / `sys.stdin`
- `print()` / `sys.stdout`
- main block
- `<think>...</think>` blocks BEFORE the code IF the source corpus
  uses them (OCR style) — but the corpus must be flagged so a
  function-completion eval doesn't see this row

Forbidden in target:
- function-only output (the eval expects a runnable program)
- imports of nonexistent stdlib (lint cleanly)

Eval shape: USACO, CodeForces problems, OpenCodeReasoning competitive
subset.

### `tool_use_call`

The model is given a recent tool-call context and must output **a
single tool invocation** in the project's chosen format (e.g.
`Tool(json_args)` for GAD, or a JSON object).

```text
input:  "Recent tool calls: [...]\nUser asks: search for files matching foo"
target: "Glob(pattern=\"**/*foo*\")"
```

Allowed in target:
- exactly one tool invocation
- minimal args (no commentary)

Forbidden in target:
- multiple tool calls
- prose
- markdown fences
- `<think>` blocks (separate field if needed)

Eval shape: `gad_tools` (promptfoo-gad-tools.yaml), `tool_use_pairs`.

### `gad_command`

The model is given a natural-language operator request and must
output **the canonical `gad <subcommand> ...` CLI invocation**.

```text
input:  "Take a note that the build is broken on Windows."
target: "gad note add build-broken --title \"Windows build broken\""
```

Allowed in target:
- the full CLI string
- required flags only by default

Forbidden in target:
- prose
- multiple commands chained with `&&` unless the user explicitly
  asks for a sequence
- shell wrappers like `bash -c`
- markdown fences

Eval shape: `gad_tools` (promptfoo subset).

## Forbidden styles (any format)

These break the eval harness regardless of target format:

| Style | Why forbidden |
|---|---|
| markdown fences ` ``` ` in target | Judge has to strip them; better to never emit |
| `<think>` blocks where the format expects code-only | Confuses the judge; eats token budget |
| prose / commentary mixed with code | Indistinguishable from judge perspective |
| `# TODO` / `# FIXME` placeholders | Treated as no-op by judge → silent fail |
| inconsistent indent (tabs + spaces) | Python parse error |
| `from <module> import *` star imports | Pollutes test namespace |

## Row schema (recommended)

```json
{
  "id": "<corpus>-<row_id>",
  "source_corpus": "open-code-reasoning | mbpp | humaneval | gad-telemetry | ...",
  "target_format": "function_completion | full_function_definition | competitive_program | tool_use_call | gad_command",
  "input": "<prompt to model>",
  "target": "<expected model output>",
  "language": "python",
  "tags": ["math", "string", "tool-use", ...],
  "license": "<source license>",
  "redacted": true,
  "schema_v": 1
}
```

Trainers MUST filter on `target_format` matching the eval target,
OR train on a mix with `target_format` injected as a prefix in the
input so the model can route its own output style.

## Mixing rules

Training a model that needs to handle multiple target formats?
Either:

1. **Single-format runs** — one corpus per LoRA, one eval per LoRA.
   Compose specialists via Branch-Train-Merge or routing
   (decision `slm-learning-101` track A).
2. **Format-tagged input** — prepend a tag to every input:
   `[FUNCTION_COMPLETION] <prompt>` / `[COMPETITIVE_PROGRAM] <prompt>`.
   The model learns to output the right format conditional on the
   tag. The eval harness must add the tag too.

Do NOT train on a mix without tags. That's what produced the OCR-LoRA
regression.

## Repair pipeline (transformations OCR → variants)

The autonomous run 2026-05-07 directive specifies 5 OCR variants for
controlled experiments. Each is a transformation of the same base
corpus (`/data/external/open-code-reasoning/data.parquet`):

| Variant | Transformation | Target format | Use |
|---|---|---|---|
| `ocr_raw` | identity | competitive_program | baseline (we already saw it regress) |
| `ocr_no_think` | strip `<think>...</think>` | competitive_program | tests think-block hypothesis |
| `ocr_function_normalized` | extract function-only solutions; drop full programs; rewrite `input()` / `print()` calls into function args/returns | full_function_definition | tests format-mismatch hypothesis |
| `ocr_mixed_instruction_50` | 50% ocr_function_normalized + 50% open-instruct or alpaca-cleaned | full_function_definition + general | tests forgetting hypothesis |
| `ocr_high_quality_subset` | filter to rows where target compiles + passes self-test (if test_list available); drop rows <50 LOC; drop reasoning >2000 tokens | full_function_definition | tests data-quality hypothesis |

See `scripts/data/prepare_ocr_variants.py` for the implementation.
Each variant emits a `dataset_profile.json` with row count, dedupe
rate, output-shape distribution, examples.

## Pre-train checklist (mandatory)

Before firing any coding-SFT run:

- [ ] Every row has a declared `target_format`
- [ ] Every row's `target` passes the forbidden-style lint
- [ ] The eval benchmarks for this run match the `target_format`
      (you do not train on `competitive_program` and eval on HumanEval
      function-completion — that's what regressed the 7B run)
- [ ] The dataset profile shows balanced distribution if mixing
- [ ] License + redaction fields populated

If any check fails, the row is filtered out, not silently kept.

## See also

- `slm-learning-103` — compare-and-compete discipline
- `slm-learning-107` — benchmark-gated scaling
- `.planning/notes/2026-05-07-comparator-matrix-public-row.md` — the
  finding that motivated this contract
- `scripts/data/prepare_ocr_variants.py` — the variant generator
