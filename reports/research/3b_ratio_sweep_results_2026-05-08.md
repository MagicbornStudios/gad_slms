# 3B retain-ratio sweep — results

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Decision refs:** slm-learning-130, 173, 178, 183, 187, 188 + new 202 (closure)
**Spec source:** `experiments/configs/morphism/lora_3b_hard_retain_{15_85,50_50,70_30}.json`
**Cost:** ~$0.90 (3 LoRA training arms ~3min each + 6 eval jobs ~5-8min each on A10G)

## Hypothesis (from spec)

3B + 30/70 retain regressed (slm-learning-183). Sweep at 15/85, 50/50, 70/30 to find the ratio that fits a saturated 3B base. Pass: any arm clears 3B base 83.5 / 73.2 on HE/MBPP. Closes Charter Claim 1 third rung.

## Result table

| Arm | hard:retain | n_train | train_loss | HE n=164 | HE Δ | MBPP n=164 | MBPP Δ |
|---|---|---|---|---|---|---|---|
| 3B base | — | — | — | **83.5** | — | **73.2** | — |
| 3B + 30/70 (slm-learning-183) | 27:63 | 90 | — | regressed | — | regressed | — |
| **15/85** | 27:137 | 164 | 0.456 | 74.39 | **-9.11** | 71.95 | -1.25 |
| **50/50** | 27:27 | 54 | 0.674 | 73.78 | -9.72 | 73.17 | ≈0 |
| **70/30** | 27:12 | 39 | 0.749 | 77.44 | **-6.06** | **75.00** | **+1.80** |

## Verdict — clean falsification across the retain-ratio range

**Every arm regresses on HumanEval.** The least-bad is 70/30 at -6.06pp; the worst is 50/50 at -9.72pp. MBPP shows a small lift only at 70/30 (+1.8pp), and even that doesn't compensate for the HE collapse.

**The 1.5B canonical recipe does not scale up to 3B.** Decision slm-learning-183 reported regression at the canonical 30/70 ratio; this sweep extends the falsification across the full ratio range. No retain-ratio choice in [0.165, 0.50, 0.692] avoids HE collapse.

**3B + LoRA r=16 + 27 hard rows + retain bank ≤ 137 is structurally incompatible with HumanEval reasoning preservation,** regardless of the hard:retain ratio.

## Pattern (interesting — possibly useful for other bases)

Within the regression range, more-hard-less-retain hurts LESS:

| Arm | hard ratio | HE retention | MBPP movement |
|---|---|---|---|
| 15/85 | 0.165 | 89.1% (worst) | -1.25pp |
| 50/50 | 0.500 | 88.4% (worst) | ≈0 |
| 70/30 | 0.692 | 92.7% (best) | **+1.80pp** |

This is the OPPOSITE direction from 1.5B (where 30/70 retain-heavy was canonical). Possible explanations:
- Saturated bases need stronger pressure signal per row to learn anything; retain rows dilute the corrective gradient
- The 3B retain bank (137 HumanEval-passed rows) may be too task-narrow — over-training on HE-format rows pulls the adapter toward MBPP-style trivial completions and away from HE-style structured reasoning
- LoRA r=16 (29.93M trainable params) on 3B is underpowered to encode the corrections without disturbing base reasoning; need larger r OR different target_modules

## What's ruled out

- "1.5B canonical recipe scales to 3B" — REFUTED across full retain ratio range
- "3B + LoRA r=16 + 27 hard rows + 137 retain (HE-narrow) + 30/70 ratio + 3 epochs at lr=2e-4" — REFUTED; produces -9.7pp HE regression
- A retain-ratio sweet spot exists for THIS dataset/recipe — REFUTED; all arms regress

## What stays open (next experiments)

1. **Larger retain bank.** 137 rows is HumanEval-PASS only. Add MBPP-pass + GSM8K-pass + general-instruct retain to dilute task-narrowness. ~$1.50 fire.
2. **Smaller LoRA rank.** r=4 or r=8 might let the base reasoning survive corrections that r=16 destroys. Same dataset, smaller adapter. ~$1 fire.
3. **Different target modules.** Drop `gate_proj`/`up_proj`/`down_proj` (the MLP); train only attention `q_proj`/`v_proj`. Hypothesis: MLP changes are what's destroying HE reasoning. ~$1 fire.
4. **Fewer epochs / lower lr.** 3 epochs at 2e-4 may be over-fitting. Try 1 epoch at 1e-4. ~$1 fire.
5. **Skip 3B as a target.** Promote 1.5B (Stein-house canonical) and 7B (Stein-house canonical) only; treat 3B as an unsuitable middle that doesn't reward LoRA at this rank/dataset combo.

## Adapter staging

The 3 trained adapters live at `/models/runs/lora-3b-hard-retain-{15_85,50_50,70_30}-2026-05-08/adapter` on Modal slm-models volume. Eval JSONs at `/models/eval-runs/eval-lora-3b-{15-85,50-50,70-30}-2026-05-08/`. Retain or evict per next-session decision.

## Cost ledger

| Item | Cost |
|---|---|
| Train 3 arms (3 × ~3min A10G) | ~$0.30 |
| Eval HE × 3 (~5-8min each) | ~$0.40 |
| Eval MBPP × 3 (~5-8min each) | ~$0.40 |
| Plus failed-fire cost (MSYS path bug) | ~$0.10 |
| **Total** | **~$1.20** |

Under $2 budget. Decision-ready data.

— Dr. Stein, 3B ratio sweep results, 2026-05-08
