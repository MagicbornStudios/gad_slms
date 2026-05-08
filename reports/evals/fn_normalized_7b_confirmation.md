# 7B fn_normalized confirmation — gate test for $50 32B shot

**Date:** 2026-05-08
**Decision refs:** `slm-learning-097`, `slm-learning-103`,
`slm-learning-107`, `slm-learning-110`
**Verdict:** **GATE FAILS — do NOT fire 32B + fn_normalized**

## Headline

> **The fn_normalized LoRA lift is a 1.5B-only artifact.** At 7B,
> the recipe is essentially neutral on HumanEval (−0.6 pp) and a
> small regression on MBPP (−3.7 pp). The 7B base is already strong
> enough that OCR-style training has nothing meaningful to add. The
> $50 32B shot with this recipe is not justified.

## Numbers

### 7B chat-mode (post v3 harness)

| Model | HumanEval n=164 | MBPP n=164 | gad_tools n=30 |
|---|---|---|---|
| 7B base | 134/164 (81.7%) | 132/164 (80.5%) | not tested |
| 7B + OCR raw LoRA | 102/164 (62.2%) | 124/164 (75.6%) | not tested |
| **7B + OCR fn-norm LoRA** | **133/164 (81.1%)** | **126/164 (76.8%)** | **11/30 (36.7%)** |

### Δ vs 7B base

| Recipe | HE Δ | MBPP Δ |
|---|---|---|
| OCR raw | −19.5 pp | −4.9 pp |
| **OCR fn-normalized** | **−0.6 pp (noise)** | **−3.7 pp** |

### Cross-scale comparison (the critical number)

| Scale | HE Δ (fn_norm vs base) | MBPP Δ |
|---|---|---|
| **1.5B** | **+6.7 pp lift** | **+3.0 pp lift** |
| **7B** | **−0.6 pp neutral** | **−3.7 pp regression** |

## Why the lift doesn't scale

Two compatible explanations:

### (a) Base saturation

Qwen2.5-Coder-7B-Instruct's HumanEval/MBPP capability is already
near the chat-mode harness ceiling. The base saw billions of
function-definition tokens during pretraining + instruction tuning.
A 1991-row LoRA on top of that adds nothing it doesn't already know
— and may slightly perturb the existing distribution (hence the
small MBPP regression).

At 1.5B, the base is much weaker (54.9% HE vs 81.7% at 7B). There's
room for a LoRA to add structured function-completion examples and
lift performance.

### (b) Distribution shift cost > benefit at scale

LoRA r=16 on 7B is 18.46M trainable params. Even with rank-16, the
adapter perturbs the model's output distribution toward the OCR
function-definition style. At 1.5B that perturbation HELPS because
the base distribution was further from HE/MBPP. At 7B the base
distribution was already close, so the perturbation is a small NET
NEGATIVE (you lose more by shifting away than you gain by aligning
with OCR style).

This is the classic pattern: **"small model benefit doesn't scale."**
The 1.5B → 7B line shows the base-capability-vs-lift curve crossing
zero somewhere between those two sizes.

## What this implies for the $50 32B shot

The slm-learning-097 pre-flight gate said: "scaling-ladder smoke
must predict benchmark lift before firing the larger shot."

What we now have:

| Recipe | 1.5B → 7B trend |
|---|---|
| OCR raw | regresses harder at 7B (worse format mismatch with strong base) |
| OCR no_think | regresses both sizes (expected to also regress at 32B) |
| **OCR fn-normalized** | **lifts at 1.5B → vanishes at 7B → likely neutral-to-negative at 32B** |

**Extrapolating the trend, 32B + fn-normalized is most likely
NEUTRAL or SMALL REGRESSION.** That's $50 to confirm "no harm done"
— bad return on investment when we have multiple unexplored variants.

## What's still on the table

The 32B shot has value INDEPENDENT of fn-normalized:

1. **32B base alone** (no LoRA) on Modal H100 to establish a
   `ours-coder-32b-base` route in the inference gateway. ~$15 for
   one warm load, no training. Gives us a frontier-class base for
   downstream LoRA composition.
2. **32B + DPO** on the preference pairs we've already mined (8
   from tooluse-v2 + future correction-pair captures). DPO is much
   cheaper than full SFT and more targeted.
3. **32B + tooluse_v3** trained on a properly contract-validated
   gad-CLI dataset (after the tooluse salvage A/B/C completes).
4. **32B + composition** — multiple specialist LoRAs merged via
   TIES/DARE per slm-learning-101 Track A.

## Recommendations

1. **HOLD the $50 32B + fn-normalized shot.** Gate fails.
2. **Add `slm-learning-113`** (TBD): "fn_normalized OCR is a 1.5B
   benefit, not a scale recipe. Active candidate for 1.5B + 3B
   coder specialists; explicitly NOT a 7B+ recipe."
3. **Pivot to the next variant** — either ocr_high_quality_subset
   (1988 rows, even stricter quality filter) at 7B, OR
   ocr_mixed_instruction_50 (when instruction-source is wired) at
   1.5B → 7B.
4. **Salvage the existing 7B + fn-normalized adapter** as
   `staging` for the **3B coder specialist** lane. The 1.5B
   numbers say it's good for small models; if 3B + fn-normalized
   also lifts, we ship a 3B specialist.
5. **Reallocate the $50** toward DPO experiments (much cheaper per
   shot, more targeted, and we already have preference-pair seed
   data).

## Cost summary

| Item | Spent |
|---|---|
| 7B fn-norm training (A100 14 min) | $0.66 |
| 7B fn-norm × HE eval | $0.40 |
| 7B fn-norm × MBPP eval | $0.40 |
| 7B fn-norm × gad_tools eval | $0.10 |
| **Gate test total** | **$1.56** |

The gate test cost less than 4% of the avoided 32B shot. **The gate
test paid for itself by ~30×.** This is the value of disciplined
benchmark-gated scaling per `slm-learning-107`.

## What "done" looks like for this batch

From the directive:

| Item | Status |
|---|---|
| 7B fn_normalized result | ✅ this report |
| Fixed-harness HE diagnosis report | ✅ `ocr_lora_diagnosis_2026-05-08.md` |
| Output-contract validator | ✅ `scripts/data/validate_output_contract.py` |
| Benchmark contract metadata | ✅ `benchmarks/contracts.json` |
| Tooluse-v2 salvage matrix | partial (status set, A/B/C not yet trained) |
| Checkpoint salvage statuses | ✅ `docs/checkpoints/checkpoint_status_policy.md` |
| bad-output → corrected-output DPO data | ✅ 8 pairs in `data/preference/tooluse_contract_failures_dpo.jsonl` |
| gad_tools_hard scaffold | ✅ `data/eval/gad_tools_hard.yaml` (categories defined) |
| Inference gateway handoff | ✅ `h-2026-05-08T02-00-00` |
| Decisions 108–112 logged | ✅ |

## Decision refs

- `slm-learning-094` — composition-of-specialists path
- `slm-learning-097` — two-shot $50 discipline (32B shot gate)
- `slm-learning-103` — compare-and-compete (4 rows per candidate)
- `slm-learning-107` — benchmark-gated scaling
- `slm-learning-110` — fn_normalized OCR is active recipe candidate
  (status now: 1.5B-only, not scale recipe)

— Dr. Stein, gate-test verdict 2026-05-08
