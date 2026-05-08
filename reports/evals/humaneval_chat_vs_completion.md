# HumanEval — chat mode vs completion mode

**Date:** 2026-05-08
**Decision refs:** `slm-learning-103`, `slm-learning-107`
**Source:** `tmp/diag-2026-05-08/base_he_chat_full.json`,
`tmp/diag-2026-05-08/base_he_completion_full.json`

## Headline

> **Completion mode HURTS the instruct model** by –32.9 pp on
> HumanEval. The standard published-leaderboard harness (raw prompt,
> no chat template) is NOT apples-to-apples for `Qwen2.5-Coder-7B-
> Instruct`. The instruct model's chat-mode score (64.6%) is the
> meaningful number for our owned-domain comparisons; the published
> ~88% likely uses the BASE (non-instruct) model in completion mode.

## Numbers

| Model | Mode | HumanEval n=164 | Source |
|---|---|---|---|
| Qwen2.5-Coder-7B-Instruct | **chat** (apply_chat_template) | **106/164 (64.6%)** | `base_he_chat_full.json` |
| Qwen2.5-Coder-7B-Instruct | **completion** (raw prompt) | **52/164 (31.7%)** | `base_he_completion_full.json` |
| Δ (completion − chat) | | **−32.9 pp** | |
| Qwen2.5-Coder-7B-Instruct + OCR LoRA | chat | **50/164 (30.5%)** | `lora_he_chat_full.json` |
| Qwen2.5-Coder-7B-Instruct + OCR LoRA | completion | did-not-land (Modal incident) | — |

LoRA completion-mode eval was launched but failed with Modal
`InternalError` (codes `UYKFTLSC`, `ZPUCHFMN`). Re-fire when
infrastructure recovers.

## Why completion mode is worse for instruct models

Sample failures from completion mode (raw prompt, no chat template):

```
HumanEval/2
prompt: "def truncate_number(number: float) -> float:\n    \"\"\"...\"\"\"\n"
completion (model continued): "    return number - int(number)
                                
                                # Check function to verify the correctness of the solution
                                def check_function():
                                    assert abs(truncate_number(3.5) - 0.5) < 1e-9
                                    ...
                                ```"
judge: SyntaxError on the trailing markdown fence (` ``` `) and
       extra `def check_function` block
```

```
HumanEval/10
completion: "    for i in range(len(string), -1, -1):
                  if is_palindrome(string[i:]):
                      return string + string[:i][::-1]
              return string


              if __name__ == '__main__':
                  import doctest
                  doctest.testmod()
              ```"
judge: SyntaxError on trailing fence + main block + extra newlines
```

**Pattern:** the instruct model is so heavily trained for chat that
in completion mode it:
1. Returns the answer body
2. Then "switches modes" and writes a check function, doctest, or
   markdown fence
3. The judge can't compile the assembled program

In chat mode, the model wraps its answer in ```python ... ``` and
the judge cleanly strips the fences. In completion mode there's no
explicit answer boundary — the model rambles past the answer.

## Why published HumanEval ~88% is likely a different beast

`Qwen2.5-Coder-7B-Instruct`'s reported HumanEval pass@1 is in the
high 80s (~88%). Our chat-mode score of 64.6% is well below that.
Possible reasons (not all confirmed; this is hypothesis space):

| Hypothesis | Likelihood | Fix |
|---|---|---|
| Published uses the BASE (non-instruct) model in completion mode, where the model continues from the prompt cleanly | **HIGH** — official model cards often report base-model scores | Test on `Qwen2.5-Coder-7B` (base, non-instruct) |
| Published uses temp>0 + multiple samples (pass@1 with sampling) | medium | Add `do_sample=True, temperature=0.2, k_samples=10` to `eval_adapter.py` |
| Published uses a custom prompt template (e.g. "Below is a Python function. Complete it.") that lifts our chat-mode score | medium | Sweep 3-4 candidate templates |
| Our judge has remaining bugs missing 5-10 cases | low (post-harness-fix) | Re-run with the column-0 auto-indent fix and recount |

The 64.6% / 88% gap is the **harness-comparison gap**, not a model-
quality gap. Don't chase it for the sake of leaderboard alignment.

## Operational rule

For owned-domain comparisons (our adapters vs each other, our LoRA
vs our base), use **chat mode** consistently. The instruct model is
trained for chat; that's the natural surface.

For leaderboard comparisons (claim "we beat published baseline by
X"), use **completion mode on the BASE non-instruct model**. The
chat-mode score on the instruct model is not directly comparable
to the published number even if both are called "HumanEval".

## What to test next

1. **Run completion mode on `Qwen2.5-Coder-7B` (base, non-instruct)**
   to confirm the harness reproduces published ~88%. ~$0.40 on
   A10G.
2. **Re-fire LoRA completion mode** when Modal recovers, to complete
   the 2×2 grid (model × mode).
3. **Run the harness-fix re-runs** (commit `814cb2b`): post-fix
   chat-mode scores should rise for both base and LoRA, narrowing
   the apparent –34pp gap.

## Decision refs

- `slm-learning-103` — compare-and-compete (4 rows per candidate)
- `slm-learning-107` — benchmark-gated scaling

— Dr. Stein, 2026-05-08
