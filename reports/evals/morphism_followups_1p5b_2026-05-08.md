# 1.5B Ladder Follow-ups: late-layer A, Variant B follow-ups, 3B transfer

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Charter:** `reports/research/scaling_proof_charter.md`
**Decision refs:** slm-learning-130, 158, 165, 170, 171, 172, 173, 174

## Summary

Four cheap follow-up arms fired in parallel after the 1.5B ladder
landed (slm-learning-173). Each tests a specific hypothesis from the
operator + ChatGPT review at 2026-05-08 12:00.

## Eval rows

| Arm | HE pass@1 | HE Δ vs 1.5B base | MBPP pass@1 | MBPP Δ vs 1.5B base |
|---|---|---|---|---|
| 1.5B base | 54.9% (90/164) | — | 61.0% (100/164) | — |
| **Variant A late (layer 21, 75% depth)** | 52.4% (86/164) | **−2.5pp** | 58.5% (96/164) | **−2.5pp** |
| Variant B + retain-mix (layer 13) | 54.9% (90/164) | 0.0 — | 61.0% (100/164) | 0.0 — |
| Variant B at lr=5e-4 (layer 13) | 54.3% (89/164) | −0.6pp (noise) | 61.0% (100/164) | 0.0 — |

| Arm | HE pass@1 | HE Δ vs 3B base | MBPP pass@1 | MBPP Δ vs 3B base |
|---|---|---|---|---|
| 3B base (slm-learning-118 reference) | 83.5% | — | 74.4% | — |
| **3B + 7B-hard transfer (LoRA r=16)** | 76.2% (125/164) | **−7.3pp ⬇** | 73.8% (121/164) | **−0.6pp** |

## Headline findings

### 1. Variant A is position-sensitive (massive recovery from late insertion)

| Variant A insert position | HE Δ | MBPP Δ |
|---|---|---|
| Layer 13 (mid, ~46% depth) | **−21.9pp** ⬇⬇ | **−20.7pp** ⬇⬇ |
| Layer 21 (late, ~75% depth) | **−2.5pp** | **−2.5pp** |

**~19pp recovery on each benchmark just by changing insert position
from layer 13 to layer 21.** Validates the operator + ChatGPT review
hypothesis: late insertions cause less GLOBAL damage because there
are fewer downstream layers to propagate the residual perturbation.

Variant A's hostility is now more accurately framed as
"position-sensitive architectural cost" rather than "fundamentally
broken." Late + retain-mix is a natural follow-up (untested) — if
mid+retain-mix lifted via LoRA, late+retain-mix via Variant A could
plausibly land near-flat or slightly-positive at very low parameter cost.

### 2. Variant B's gate-stickiness is structural, not hyperparameter

Both Variant B follow-ups (lr=5e-4 and retain-mix) produced
EFFECTIVELY FLAT eval scores indistinguishable from base:

| Variant B follow-up | HE | MBPP |
|---|---|---|
| Default (lr=2e-4, hard 74) — slm-learning-174 | 54.9% (FLAT) | 61.0% (FLAT) |
| lr=5e-4, hard 74 | 54.3% (1 case off, FLAT-noise) | 61.0% (FLAT) |
| lr=2e-4, hard+retain 164 | 54.9% (FLAT) | 61.0% (FLAT) |

**Identical training loss across lr=2e-4 and lr=5e-4** (both 1.0402)
confirms the gate did not move under any tested hyperparameter. Even
with retain-mix (a richer, larger dataset), final loss only rose to
1.0583 — hypothesis: the gate's gradient is stuck near 0 because the
up_proj is also zero-init, making `bottleneck(x) = 0` at init,
making `gate × bottleneck(x) = 0`, making `∂loss/∂gate ≈ 0`.

**Real fix requires init redesign**, not hyperparameter sweeps:

- **Option A:** initialize up_proj with small-random Kaiming (not
  zero), keep gate=0. Then `bottleneck(x) ≠ 0` and gate's gradient
  can drive away from 0.
- **Option B:** train gate-only for 1 epoch first with up_proj
  unfrozen, then unfreeze the rest. Two-stage curriculum.
- **Option C:** replace scalar gate with a small MLP-gated mixture
  initialized near 0 with small variance.

Documented in queue; not fired this round.

### 3. Recipes are NOT base-agnostic — 3B + 7B-hard regresses

The third rung of Charter Claim 1 was supposed to test whether the
7B-proven gap-targeted recipe transfers to 3B without a 3B-specific
failure dataset. Result: **it does not.** 3B + 7B-hard × HE
regressed −7.3pp.

Asymmetric effect:

| Benchmark | 3B + 7B-hard Δ |
|---|---|
| HE (the source-of-failures benchmark) | **−7.3pp** ⬇ |
| MBPP (out-of-distribution) | −0.6pp (noise) |

Why HE worse than MBPP? The 7B-hard dataset is HE-shaped (built from
7B's HE failures + canonical solutions). When 3B trains on it:

- **MBPP:** Out-of-distribution; the 3B model just doesn't see
  these patterns at MBPP test time, so they don't help OR hurt much.
- **HE:** In-distribution shape; 3B is now being told "produce these
  specific canonical solutions" for inputs that 3B previously
  handled differently. The drift breaks 3B's HE behavior.

This validates `slm-learning-169` (morphism dataset locked to
0.5B-base-failure rows) and the broader rule: **base-failure rows
are base-specific. A 7B failure does not equal a 3B failure does
not equal a 1.5B failure. Each base needs its OWN gap data to lift.**

The 1.5B+retain-mix lift (slm-learning-173) used 1.5B-OWN failures.
The 7B+hard lift (slm-learning-130) used 7B-OWN failures. The 3B +
7B-hard transfer is the first test of CROSS-BASE failure-data
transfer in the project, and it falsifies the strong form.

## Cross-scale matrix (updated 2026-05-08 close)

| Base | Mechanism + Dataset | HE Δ | MBPP Δ | Verdict |
|---|---|---|---|---|
| 7B | LoRA r=16, 7B-hard 58 rows | **+3.1** ⬆ | **+1.8** ⬆ | canonical (slm-learning-130) |
| **1.5B** | **LoRA r=16, 1.5B-hard+retain 164 rows** | **+9.1** ⬆ | **+3.0** ⬆ | **canonical (slm-learning-173)** |
| 1.5B | LoRA r=16, 1.5B-hard 74 rows (no retain) | −6.7 | −3.7 | not safe without retain |
| 1.5B | Variant A mid (layer 13), 1.5B-hard | −21.9 ⬇ | −20.7 ⬇ | architecturally hostile |
| **1.5B** | **Variant A LATE (layer 21), 1.5B-hard** | **−2.5** | **−2.5** | **mildly hostile; 19pp recovery from position** |
| 1.5B | Variant B (mid), 1.5B-hard | 0.0 | 0.0 | preserves but inert |
| 1.5B | Variant B (mid), lr=5e-4 1.5B-hard | −0.6 (noise) | 0.0 | gate stuck (not hyperparams) |
| 1.5B | Variant B (mid), 1.5B-hard+retain | 0.0 | 0.0 | gate stuck (not data shape) |
| 3B | LoRA r=16, 7B-hard transfer (cross-base) | −7.3 ⬇ | −0.6 | recipes don't transfer |
| 0.5B | any × hard-only | catastrophic | catastrophic | base too weak |

## What got proven / falsified

### Proven this round

| Hypothesis | Evidence |
|---|---|
| Variant A is position-sensitive (operator hypothesis from 2026-05-08 12:00) | layer 21 vs layer 13: 19pp HE recovery, 18pp MBPP recovery, same data and lr |
| Variant B gate-stickiness is structural (chicken-and-egg of zero-init up + zero-init gate) | identical loss across lr=2e-4 and lr=5e-4; retain-mix also did not unstick |
| Base-failure rows are base-specific (slm-learning-169 generalizes) | 3B + 7B-hard regressed −7.3pp HE; recipes don't transfer cross-base |

### Falsified this round

| Hypothesis | Evidence |
|---|---|
| Variant B can lift via lr increase alone | identical eval at lr=5e-4 (FLAT) |
| Variant B can lift via retain-mix data alone | identical eval with retain-mix (FLAT) |
| Charter Claim 1 strong-form: "7B-proven recipe transfers to other strong bases" | 3B + 7B-hard regressed; recipe is base-specific |

### Still open

| Hypothesis | What would test it |
|---|---|
| Variant A late-layer + retain-mix lifts | one more $0.85 arm |
| Variant B with small-random up_proj init can lift | one more $0.85 arm + code change to up_proj init |
| Variant B with gate-only warmup epoch can lift | one more $0.85 arm + 2-stage training script |
| 3B + 3B-OWN-hard lifts (charter Claim 1 rung 3) | $0.40 prereq (3B base eval already done; need to extract 3B's failures) + $0.30 train + $0.80 eval |

## Recommended next moves (in priority order)

1. **3B + 3B-OWN-hard** — directly tests if the recipe lifts at 3B
   when given 3B's own failures (vs 7B's). $0.40 + $0.30 + $0.80 = ~$1.50
   total. Closes Charter Claim 1's third rung properly. **Highest priority.**
2. **Variant A late-layer + retain-mix at 1.5B** — combines the two
   biggest mitigations. ~$0.85. Tests if Variant A can lift when
   both interventions are applied.
3. **Variant B with small-random up_proj init** — code change in
   `train_morphism.py` (replace `nn.init.zeros_(self.up.weight)` with
   `nn.init.kaiming_uniform_(self.up.weight, a=5**0.5) * 0.1`) +
   one training arm. ~$0.85 + 5 min code edit. Tests if Variant B
   becomes lift-capable.
4. **Frontier comparator via Gemini-cli** — handoff filed at
   `h-2026-05-08T12-30-00`; awaits monorepo team pickup.

## Cost summary (this round)

| Arm | Train wall | Train cost | Eval cost (HE+MBPP) |
|---|---|---|---|
| Variant A late-layer | 52.9s | $0.012 | ~$0.30 |
| Variant B lr=5e-4 | 72.9s | $0.017 | ~$0.30 |
| Variant B + retain-mix | 80.3s | $0.019 | ~$0.30 |
| 3B + 7B-hard transfer | 110.1s | $0.025 | ~$0.30 |
| **Total this round** | | | **~$1.30** |

Cumulative session: ~$4.30 of $15 Modal envelope. Headroom remains.

— Dr. Stein, 1.5B follow-ups close 2026-05-08
