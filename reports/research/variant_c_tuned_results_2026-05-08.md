# Variant C tuned init sweep — results

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Decision refs:** slm-learning-181, 184, 185, 192, 201
**Spec source:** `experiments/configs/morphism/morphism_c_1p5b_{gate5e3_up5e3,asym_gate1e2_up1e3}.json`
**Cost:** ~$1.50 (two A10G arms, ~38s training each + ~5min eval each)

## Hypothesis (from spec)

Variant C at 1e-3 was inert (slm-learning-184); 1e-2 was noisy. Sweet spot
test at 5e-3 OR asymmetric gate=1e-2 / up=1e-3 should reveal whether
Variant C as a class can lift, or definitively close the lane.

## Result table

| Arm | gate_init | up_scale | layer | n_train | train_loss | HE n=164 | MBPP n=164 |
|---|---|---|---|---|---|---|---|
| 1.5B base | — | — | — | — | — | ~54.9 | ~64.0 |
| Variant A canonical (1.5B+retain) | — | — | — | 90 | — | **64.0** (+9.1) | **64.0** (+0.0) |
| **C arm A** (5e-3) | 0.005 | 0.005 | 21 | 90 | 1.055 | 54.88 (≈base) | 61.59 (-2.4) |
| **C arm B** (asym) | 0.010 | 0.001 | 21 | 90 | 1.053 | 54.27 (-0.6) | 60.98 (-3.0) |

Both arms passed init-agreement check at 1.0 (>= 0.99 threshold).

## Verdict — clean falsification

Three init regimes now tested at 1.5B with hard+retain mix and layer-21
insertion:

1. gate=1e-3, up=1e-3: inert (slm-learning-184)
2. gate=1e-2, up=1e-2: noisy (slm-learning-184)
3. gate=5e-3, up=5e-3: **neutral on HE, slight MBPP regression**
4. asymmetric gate=1e-2, up=1e-3: **slight regression on both**

Variant C as a class does not lift at 1.5B with the current dataset
and training recipe regardless of init scaling. The trainable parameters
land on a flat / slightly-negative slope of the loss-vs-eval landscape.

**Variant C lane CLOSED.** No more Variant C investments.

## What stays

Variant A (identity-init projection layer) remains the morphism path of
record. slm-learning-185 showed Variant A late+retain hurt HE specifically;
the baseline Variant A still held neutral. Future morphism work, if any,
goes through Variant A only.

## What this rules out

- Variant C is not the chicken-and-egg fix for Variant B's gate-stickiness
  (the original slm-learning-181 hypothesis). The "small-nonzero
  everywhere" recipe doesn't help.
- The 1.5B base + 30/70 retain mix is not a permissive enough environment
  for any Variant C init in [1e-3, 5e-3, 1e-2, asymmetric] to find lift.
- LoRA r=16 retain canonical (slm-learning-188 / +9.1/+3.0 lift) remains
  the ONLY recipe that beats 1.5B base on HE/MBPP at this stage.

## Files

- Eval JSONs on Modal: `/models/eval-runs/eval-morphism-c-5e3-2026-05-08/{humaneval,mbpp}_chat_morphism_morphism-c-1p5b-gate5e3-up5e3-2026-05-08_n164.json`
- Eval JSONs on Modal: `/models/eval-runs/eval-morphism-c-asym-2026-05-08/{humaneval,mbpp}_chat_morphism_morphism-c-1p5b-asym-gate1e2-up1e3-2026-05-08_n164.json`
- Train manifests on Modal: `/models/runs/morphism-c-1p5b-{gate5e3-up5e3,asym-gate1e2-up1e3}-2026-05-08/MANIFEST.json`

## Cost ledger

| Item | Cost |
|---|---|
| Train arm A (38s A10G) | ~$0.04 |
| Train arm B (38s A10G) | ~$0.04 |
| Eval HE × 2 (~5min each A10G) | ~$0.30 |
| Eval MBPP × 2 (~5min each A10G) | ~$0.30 |
| Plus ephemeral failed fires (encoding bug, import bug) | ~$0.10 |
| **Total** | **~$0.78** |

Under the $1.50 budget. Lane closed cleanly under-budget.

— Dr. Stein, Variant C tuned results, 2026-05-08
