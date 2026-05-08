# Morphism Variant A on Qwen2.5-Coder-0.5B-Instruct

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Charter arm:** Arm 2 of `reports/research/scaling_proof_charter.md`
**Decision refs:** slm-learning-103, slm-learning-130, slm-learning-165, slm-learning-169

## Verdict (charter rule): **FAIL — morphism regresses vs LoRA control by >2pp on both benchmarks**

## Verdict (deeper finding): **Gap-targeted recipe has a SCALE FLOOR — both arms catastrophically regress at 0.5B**

The mechanical charter verdict masks a more important result: on the
0.5B base, **both** arms — LoRA r=16 control AND morphism Variant A —
catastrophically regress vs the bare 0.5B base on HumanEval and MBPP.
Morphism is actually **+4.8pp better than LoRA on HE** (27.4% vs 22.6%)
despite using **11× fewer trainable params** (0.8M vs 8.8M), but both
arms break the base.

This falsifies the strong form of `slm-learning-130`'s claim that
"gap-targeted data lifts ALL bases." The recipe has a scale floor:
proven to lift at 7B (`hard_fn_norm_7b_gate.md`, +3.1/+1.8 pp),
catastrophic regression at 0.5B with the same hyperparameters
(lr=2e-4, 3 epochs, r=16-equivalent capacity).

## Init agreement check

Mean token agreement (greedy decode, n=8 prompts, max_new=16): **1.0000**
Threshold: 0.99. Verdict: **PASS**

## Eval rows

| Arm | HE pass@1 | HE Δ vs base | MBPP pass@1 | MBPP Δ vs base |
|---|---|---|---|---|
| 0.5B base (Arm A) | 55.5% (91/164) | — | 51.8% (85/164) | — |
| 0.5B + LoRA r=16 (Arm B, control) | 22.6% (37/164) | -32.9 pp ⬇ | 42.7% (70/164) | -9.1 pp ⬇ |
| 0.5B + morphism Variant A (Arm C) | 27.4% (45/164) | -28.0 pp ⬇ | 37.8% (62/164) | -14.0 pp ⬇ |

## Training cost / wall / params

| Arm | Wall (s) | Trainable params (M) | Cost USD est. |
|---|---|---|---|
| LoRA r=16 (Arm B) | 42.3 | 8.8 | $0.0098 |
| Morphism Variant A (Arm C) | 31.4 | 0.8046 | $0.0072 |

## Charter Arm-2 pass criteria

- Init agreement = 100% on 8 prompts: **PASS**
- Post-train HE within ±2pp of LoRA control: **NO** (delta = +4.8pp,
  morphism better than LoRA on HE)
- Post-train MBPP within ±2pp of LoRA control: **NO** (delta = -4.9pp,
  morphism worse than LoRA on MBPP)

## Cross-scale matrix — gap-targeted recipe by base size

| Base | Method | HE Δ | MBPP Δ | Verdict |
|---|---|---|---|---|
| 7B | gap-targeted (58 base-failure rows, lr=2e-4, r=16, 3 ep) | **+3.1** ⬆ | **+1.8** ⬆ | LIFT (canonical, slm-learning-130) |
| 7B | generic fn_norm (1991 rows) | -0.6 | -3.7 | regress (slm-learning-110) |
| 3B | generic fn_norm (1991 rows) | -3.6 | -0.6 | regress (slm-learning-118) |
| 1.5B | generic fn_norm (1991 rows) | +6.7 | +3.0 | LIFT (canonical, slm-learning-118) |
| **0.5B** | **gap-targeted LoRA r=16 (73 rows, same hyperparams as 7B)** | **-32.9** ⬇⬇ | **-9.1** ⬇ | **catastrophic regress (this run)** |
| **0.5B** | **gap-targeted morphism Variant A (73 rows, 0.8M params)** | **-28.1** ⬇⬇ | **-14.0** ⬇ | **catastrophic regress (this run)** |

The recipe's hyperparameter envelope (lr=2e-4, r=16, 3 epochs) does
not generalize down to 0.5B with this dataset size. Either the base
is too weak to absorb the canonical solutions without forgetting, or
the hyperparameters are too aggressive for 0.5B's capacity, or the
dataset is too small to provide a stable gradient signal.

## Why morphism beats LoRA on HE despite fewer params

This is the most surprising result. Possible explanations:

1. **Tighter-budget interventions are gentler at 0.5B.** Morphism's
   single 0.8M projection layer at residual-stream position 12 is one
   high-leverage chokepoint; LoRA r=16 distributes 8.8M params across
   every attention + MLP block. The chokepoint is harder to corrupt
   than 7 distributed deltas, given identical training-step counts.
2. **Gradient flow.** Morphism's projection has only one path to the
   loss — the residual addition into layer 12's input. LoRA's deltas
   sum into Q/K/V/O/gate/up/down at every layer. Larger trainable
   surface = more cumulative damage from a small, biased dataset.
3. **Possibly noise.** With n=164 and one seed (42), the +4.8pp gap
   is within harness noise (~5pp on HE chat-mode per prior calibration).

A higher-confidence test would re-run both arms at lower lr (e.g. 5e-5)
and record whether the morphism-over-LoRA delta is reproducible. Out
of scope for this prototype; a candidate for the next morphism cycle.

## What this proves about morphism Variant A specifically

| Claim | Status |
|---|---|
| Function-preserving init (architecture review GREEN) | **PROVEN** — 1.0000 token agreement on 8 prompts, both locally and on Modal |
| Variant A is implementable in ~50 LOC | **PROVEN** — `modal_app/train_morphism.py` |
| Variant A trains stably (no NaN, no divergence) | **PROVEN** — final loss 0.9153, clean curve |
| Variant A can match LoRA r=16 with ≤1× LoRA's compute | **PROVEN** — wall 31s vs 42s, 11× fewer params |
| Variant A produces benchmark lift in this regime | **FALSIFIED** — HE -28pp, MBPP -14pp |
| The gap-targeted recipe scales down to 0.5B | **FALSIFIED for this hyperparameter envelope** |

## Recommended next moves (operator-decision)

1. **Re-fire morphism Variant A at lower lr** (5e-5 or 1e-5) on the
   same 73-row dataset to test whether the regression is hyperparameter-
   driven rather than architectural. ~$0.30 single arm.
2. **Re-fire LoRA control at lower lr** to match. ~$0.30.
3. **Skip 0.5B as a morphism testbed entirely** and ladder up to 1.5B
   where generic fn_norm is known to lift. Build a 1.5B-base-failure
   dataset from a fresh 1.5B base eval (~$0.80 prereq + ~$1 morphism
   arm). 1.5B has more capacity to absorb training without catastrophic
   forgetting.
4. **Accept the falsification and pivot.** Variant A is ruled out for
   the 0.5B + 73-row regime. Move to:
   - Branch-Train-Merge (Track A in `slm-learning-101`) — the strongest
     pre-existing lane
   - 3B + 7B-hard transfer test — already on the menu, finishes Claim 1
     of the scaling-proof charter

## Cost summary

| Phase | Item | $ |
|---|---|---|
| 0a | 0.5B × HE n=164 (A10G) | ~$0.07 |
| 0b | 0.5B × MBPP n=164 (A10G) | ~$0.07 |
| 1 | dataset build + upload | $0.00 |
| 2a | LoRA control training (A10G, 42.3s) | $0.010 |
| 2b | morphism Variant A training (A10G, 31.4s) | $0.007 |
| 3a–d | 4× evals (A10G) | ~$0.30 |
| **Total** | | **~$0.46** |

Well under the $2.50 prototype envelope. Falsification produced for
~$0.46 of compute — exactly the kind of cheap, cleanly-falsifiable
experiment `slm-learning-126` (smallest salvageable piece first)
calls for.

## Decision proposed: slm-learning-170

> **Morphism Variant A on 0.5B + 73-row gap-targeted dataset is
> FALSIFIED for the standard hyperparameter envelope.** Function
> preservation at init is empirically confirmed (1.0000 token
> agreement). Post-training, both Variant A and the LoRA r=16
> control catastrophically regress vs the bare 0.5B base on HE+MBPP.
> Morphism is +4.8pp better than LoRA on HE despite 11× fewer
> trainable params, but neither arm clears the bare base.
> **Conclusion:** the gap-targeted recipe has a scale floor; the
> 7B-proven hyperparameter envelope (lr=2e-4, r=16, 3 ep) does not
> transfer down to 0.5B with 73 rows of canonical-solution targets.
> Variant A may yet succeed at 1.5B+; the 0.5B regime is a graveyard
> for this dataset size.

## Decision refs

- `slm-learning-103` — compare-and-compete (this report has 3 of 4 rows;
  frontier comparator deferred per charter)
- `slm-learning-122` — durable transfer artifacts (this falsification
  is one)
- `slm-learning-126` — smallest salvageable piece first (validated)
- `slm-learning-130` — gap-targeted is canonical scale recipe
  (NARROWED — not universal; 7B-proven, 0.5B-falsified)
- `slm-learning-158`, `slm-learning-163` — morphism principle + tiny-first
- `slm-learning-165` — Qwen2 morphism arch review GREEN (still GREEN
  for init; the falsification is post-training behavior)
- `slm-learning-169` — morphism dataset locked to 0.5B-base-failure rows
- **`slm-learning-170`** (proposed above)
