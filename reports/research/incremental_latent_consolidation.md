# Incremental Latent Consolidation

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Status:** Active research framework
**Decision refs:** slm-learning-122 (durable artifacts), slm-learning-126
(smallest salvageable piece), slm-learning-130 (gap-targeted recipe),
slm-learning-172 (1.5B ladder + Variant B + retain-mix direction),
slm-learning-173 (retain-mix lift at 1.5B), slm-learning-174
(Variant B preserves but inert), slm-learning-175 (Variant A
position-sensitive), slm-learning-176 (Variant B gate-stickiness
structural), slm-learning-177 (cross-base transfer falsified),
slm-learning-178..182 (proposed below)

> **GAD scales by repeated pressure-gated consolidation: small deltas
> are trained on base-specific failures and smoothed with retain
> memory until useful behavior becomes stable enough to promote.**

This doc operationalizes the operator + ChatGPT review framing of
2026-05-08 — that incremental latent consolidation is the long-term
training/deployment path, not one-shot training.

---

## Vocabulary

| Term | Meaning |
|---|---|
| **hard rows** | Pressure / correction rows. Rows where a specific base failed, paired with canonical solutions. |
| **retain rows** | Stabilizing / replay rows. Rows the base **already passed** that we want to NOT forget. |
| **consolidation** | Training a small delta on hard+retain so the new behavior settles without distorting old behavior. |
| **smoothing** | Hard+retain curriculum + low-magnitude residual updates + late insertion + small gates. |
| **retain bank** | Per-base store of passed/golden behavior rows tagged by benchmark/skill/contract. Sampled every consolidation run. |
| **consolidation window** | Pressure-gated training cycle. Fires when pressure exceeds threshold (slm-learning-129 + v2 formula). NOT continuous training. |
| **pressure profile** | The set of failure clusters specific to one base. 7B-pressure ≠ 3B-pressure ≠ 1.5B-pressure (slm-learning-177). |
| **delta type** | LoRA / morphism layer / adapter / router / skill-model. The mechanism the consolidation uses. |
| **promotion verdict** | canonical / staging / skeleton / negative_teacher / quarantined. |

---

## What this session has empirically proven about consolidation

Five experiments fed this framework:

| Experiment | Finding |
|---|---|
| 7B + 7B-hard 58 rows (slm-learning-130) | Hard-only LIFTS strong base (+3.1 HE / +1.8 MBPP) |
| 0.5B + 0.5B-hard 73 rows (slm-learning-170) | Hard-only CATASTROPHICALLY regresses small base (−33 HE) |
| 0.5B Variant A morphism (slm-learning-170,171) | Single-chokepoint architecture amplifies catastrophic forgetting |
| 1.5B + 1.5B-hard+retain 164 rows (slm-learning-173) | **Retain-mix LIFTS** (+9.1 HE / +3.0 MBPP); first non-7B lift |
| 1.5B Variant A late vs mid (slm-learning-175) | Position-sensitive: late insert recovers ~19pp from mid |
| Variant B gate=0+up=0 (slm-learning-174,176) | Double-safety preserves but cannot learn (chicken-and-egg gradient) |
| 3B + 7B-hard cross-base (slm-learning-177) | Recipes don't transfer cross-base; pressure profile is base-specific |

**Synthesis:** the model needs **both** pressure rows AND stabilizing
rows. Hard alone destabilizes; retain alone teaches nothing. Identity
layers can grow capacity but only when they're (a) inserted late
enough to limit blast radius, and (b) initialized so gradients can
actually flow.

---

## The 4 kinds of smoothing

### 1. Retain-mix (data-level smoothing) — **PROVEN at 1.5B**

```
hard rows = pressure
retain rows = "do not break this old behavior"
train on both
```

Empirical: 1.5B+hard alone regressed −6.7/−3.7. Same recipe with
retain-mix lifted +9.1/+3.0. Same model, same lr, same epochs, same
hardware — only data shape changed.

### 2. Curriculum (gradual data introduction) — UNTESTED

```
stage 1: 10% hard / 90% retain
stage 2: 30% hard / 70% retain
stage 3: 50% hard / 50% retain
```

Predicted to help when the base is small/inert; lets the model
adjust without shock. Untested in slm-learning; queued for the
3B-OWN-hard arm if direct 30/70 retain-mix produces noisy results.

### 3. Low-magnitude update smoothing — PARTIALLY TESTED

| Knob | Status |
|---|---|
| Lower learning rate | TESTED at 0.5B (lr=5e-5 hurt HE worse than lr=2e-4 — slm-learning-171) and at 1.5B Variant B (no effect — slm-learning-176). Lower lr is NOT a generic smoother. |
| Smaller residual branch (Variant B bottleneck = h/4) | TESTED — preserves but inert (slm-learning-174) |
| Late insertion (75% depth) | TESTED — recovers ~19pp (slm-learning-175) |
| Small NONZERO gate at init (Variant C) | NEW ARCHITECTURE — see below |
| Identity regularization (penalize ‖projection‖) | UNTESTED |
| Gradient clipping max_grad_norm=1.0 | DEFAULT in all our morphism configs |

### 4. Eval smoothing (multi-axis acceptance) — DOC-ONLY

Don't only ask "did hard rows improve?" Ask:

- did the retain rows stay passing? (pre-vs-post on the bank)
- did unrelated benchmarks stay stable?
- did contract validity stay ≥95%?
- did fallback rate drop?

Currently: we measure HE+MBPP only. The retain-pass-rate measurement
is queued (`schemas/consolidation_run.schema.json` includes the
field; need to wire the eval).

---

## Variant C — the next morphism design

The two morphism failures point to a single architecture that fixes
both:

```
A's failure: gate path is too aggressive (full hidden×hidden projection
             at every token, no scaling)
B's failure: gate=0 AND up_proj=0 → ∂loss/∂gate ≈ 0 → never moves
```

**Variant C: late gated residual, small-nonzero init throughout.**

```python
class GatedResidualLayer(nn.Module):
    """y = x + g · F(norm(x)). Initialized so gradients flow but
    behavior starts close to identity."""

    def __init__(self, hidden_size, bottleneck_size, eps=1e-6,
                  gate_init=0.01):
        super().__init__()
        self.norm = Qwen2RMSNorm(hidden_size, eps=eps)
        self.down = nn.Linear(hidden_size, bottleneck_size, bias=True)
        self.up = nn.Linear(bottleneck_size, hidden_size, bias=True)
        self.gate = nn.Parameter(torch.full((1,), gate_init))
        self.act = nn.SiLU()
        # down init: kaiming so it represents diverse features
        nn.init.kaiming_uniform_(self.down.weight, a=5**0.5)
        nn.init.zeros_(self.down.bias)
        # up init: SMALL random (NOT zero), scaled by 0.01 so initial
        # bottleneck output is small but nonzero — gradient can flow
        nn.init.kaiming_uniform_(self.up.weight, a=5**0.5)
        with torch.no_grad():
            self.up.weight.mul_(0.01)
        nn.init.zeros_(self.up.bias)
        # gate init: 0.01 — small enough that initial perturbation is
        # tiny, large enough that gradient is non-vanishing
```

Function preservation at init: `gate × bottleneck(x)` with
`gate = 0.01` and `up.weight ≈ 0.01·random` produces output norm of
~0.0001× input residual norm. Bit-identity is sacrificed but
empirical preservation should still pass the ≥95% token-agreement
gate (acceptance test below).

**Default insertion: layer 21 of 28 (75% depth).**
**Default training: hard+retain mix.**
**Default lr: 2e-4 (same as canonical).**

---

## The 10-step GAD evolution loop (formal)

```
1. Observe pressure
   failures, corrections, fallback, human edits, task friction
   → produces a `pressure_event`

2. Pressure gate (slm-learning-129 / v2 formula)
   if P(action) < θ: HOLD
   else: continue

3. Identify failure clusters
   base-specific, skill-specific, project-specific
   → produces `failure_set`

4. Build hard rows
   canonical corrections for each failed case
   → produces `<base>_<date>_hard_rows.jsonl`

5. Build retain rows
   sample from base's retain bank
   stratify by skill/contract/benchmark
   → produces `<base>_<date>_retain_rows.jsonl`

6. Build consolidation mix
   hard + retain at target ratio
   → produces `<base>_<date>_consolidation_mix.jsonl`

7. Train small delta
   LoRA / morphism / skill-adapter
   logged to `consolidation_run.json` per schema

8. Eval (multi-axis)
   public eval (HE/MBPP)
   owned-domain eval (gad_tools / doc-verifier / Kael traces)
   retain-bank pass-rate (delta vs base)
   regression score (max negative delta on any axis)
   → produces `eval_report.json`

9. Promote / reject
   gate by lift on at least one axis + no major regression on retain bank
   → emits `promotion_verdict`

10. Serve through router (vLLM/Modal/Kael runtime)
    telemetry feeds back to step 1 as next pressure_event
```

---

## What's first-class in this framework

### 1. Consolidation windows (pressure-gated training)

Not continuous random training. Pressure-gated.

Triggers:
- N accepted human corrections collected → fire
- M repeated identical failures observed → fire
- Fallback rate > τ → fire
- Manual operator authorization → fire

### 2. Retain banks (per-base stable-behavior memory)

Each base has:
- `retain_bank/<base>/<date>/passed.jsonl` — rows base passed, by benchmark
- `retain_bank/<base>/<date>/golden.jsonl` — operator-curated must-preserve
- `retain_bank/<base>/<date>/contract.jsonl` — contract-validity exemplars

### 3. Skill banks (capability anchors)

Skills become training anchors. If a new delta improves
`benchmark-gated-training`, it must not break `tool-action-generation`.
Each skill carries `anchor_examples.jsonl` — small held-out tests.

### 4. Latent consolidation ledger

Extend `reports/scaling/gad_scaling_ledger.json` with one row per
consolidation run:
- delta_id (= adapter_id)
- pressure_source (failure_set id)
- hard_set + retain_set + ratio
- eval_before / eval_after / retain_delta / regression_score
- promotion_verdict

---

## What this doc does NOT promise

- **Variant C will lift.** It's an architecture proposal motivated by
  Variant A and Variant B failures; the empirical test is queued.
- **Curriculum (stage 10/30/50%) will outperform 30/70 mix.** Untested.
- **Eval smoothing replaces public benchmarks.** Public benchmarks
  remain mandatory per slm-learning-103. Retain-pass-rate is an
  ADDITIONAL gate, not a replacement.

The framework is the discipline; experiments validate or falsify
each piece.

---

## Cross-references

- `schemas/consolidation_run.schema.json` — per-run record schema
- `scripts/data/build_retain_bank.py` — per-base retain bank builder
- `scripts/data/build_consolidation_mix.py` — hard+retain mixer
- `experiments/configs/morphism/variant_c_late_gated_residual.json` — Variant C config
- `reports/research/scaling_proof_charter.md` — how this fits into the charter
- `reports/research/pressure_formula_v2.md` — the pressure gate at step 2
- `reports/research/morphism_qwen2_arch_review.md` — architecture review (Variants A/B/C all use the same Qwen2 insertion scaffold)

— Dr. Stein, incremental latent consolidation framework, 2026-05-08
