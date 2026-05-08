# Larger Smoothing Pass Policy (Lane E)

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Decision refs:** slm-learning-097 (two-shot $50 discipline),
slm-learning-126 (smallest salvageable piece first),
slm-learning-178..182 (consolidation framework),
slm-learning-186..192 (delta packets + sharding),
slm-learning-193 (souls/houses), slm-learning-194 (serving lane),
slm-learning-195 (proposed below)

> **Pregame with small deltas. Only do the big drunk full-model
> smoothing when the small deltas prove what needs to be
> integrated.** — operator 2026-05-08

This doc defines WHEN we authorize a larger smoothing pass and
WHAT mechanism we use.

---

## What "larger smoothing" means

Not bigger random training. Specifically, one of:

- **Larger LoRA** (r=64 or r=128 instead of r=16) — captures more
  features; same base
- **Multi-skill SFT** — train one adapter on the union of multiple
  houses' delta packets at the same base size; tests cross-house
  transfer within a faction
- **DPO / KTO / SimPO** — preference training from accumulated
  fallback-correction pairs (slm-learning-112)
- **Adapter merge / composition** — TIES-merge or DARE-merge of
  several promoted house adapters into one; produces a "faction
  unified" adapter
- **Bigger base adaptation** — re-train the proven recipe at 7B,
  14B, 32B (gated by slm-learning-097 two-shot $50 discipline)
- **Morphism capacity expansion** — once Variant C tuned init
  works, expand capacity at a strong base
- **Full fine-tune** — last resort; requires explicit operator
  authorization + budget cap

A larger pass typically costs **$5–$50** vs. $0.03–$0.30 for a
small consolidation run.

---

## Triggers (any one is necessary, but not sufficient alone)

Ranked from cheapest signal to most expensive:

1. **Promoted-deltas threshold:** ≥5 promoted house adapters in a
   faction at the same base size. (Today: Stein-house has 1
   promoted at 1.5B + 1 at 7B; Verifier-house has 1 at 1.5B.
   Total = 3 across 2 factions. Below threshold.)

2. **Adapter-graph fragmentation:** ≥3 adapters in the same
   `(base, faction)` cell with overlapping but non-identical
   coverage. Suggests merge-pass would consolidate without losing
   distinct skills.

3. **High fallback rate:** the inference router is choosing the
   bigger-model fallback >5% of the time despite a house's
   specialist adapter being available. Suggests the specialist
   isn't covering enough cases — bigger pass may help.

4. **Retain bank size:** ≥500 retain rows accumulated for a
   `(base, benchmark)` cell. Smaller passes can use 50-200; larger
   passes have material for bigger LoRA r without overfitting.

5. **Pressure clusters spanning multiple skills:** when failure
   clustering (Q5 in pressure_to_training_research_agenda.md)
   identifies clusters that touch ≥3 skill_ids, the right answer
   may be a multi-skill SFT, not 3 narrow adapters.

6. **Cost-per-successful-task plateau:** when small consolidation
   runs no longer improve cost/success on a benchmark for ≥3
   consecutive cycles, the marginal LoRA r=16 has saturated; need
   capacity (bigger r OR bigger base OR morphism expansion).

7. **Operator override:** strategic decision to integrate, e.g.,
   before a public release of Kael.

---

## Gates (ALL must pass before authorization)

Per slm-learning-097's two-shot $50 discipline + this policy:

| Gate | Threshold |
|---|---|
| Pre-flight comparator matrix | small-rung lift visible (e.g., 1.5B+hard+retain lifted at $0.034) |
| Cost-per-successful-task improvement at small rung | the smaller pass's $/success was already better than the bare base |
| Retain pass-rate ≥95% on small pass | confirms forgetting was bounded |
| Operator authorization recorded | budget cap explicit; mechanism explicit; expected lift named |
| Frontier comparator row exists for the eval suite | charter Row 8 — must be filled before large pass |
| 3-artifact rule (slm-learning-096) capacity in place | weights + outputs corpus + regression journal storage |

Missing any gate = HOLD, not REJECT. Re-evaluate when gate clears.

---

## Mechanism selection table

| Trigger | Recommended mechanism | Cost band |
|---|---|---|
| 5+ promoted deltas in faction at same base | Adapter merge (TIES/DARE) | ~$1 |
| Cross-house transfer wanted | Multi-skill SFT at same base | ~$3-10 |
| Correction pairs accumulated | DPO/KTO from pairs | ~$5-15 |
| Single-skill saturated at LoRA r=16 | Larger LoRA (r=64) | ~$3 |
| Single-skill saturated at base size | Bigger base adaptation | $11-50 (slm-learning-097) |
| Architecture-level capacity needed | Morphism expansion (Variant C tuned) | ~$5-15 |
| Multimodal artifact failures | Structured spec model (slm-learning-191) | ~$2-5 |
| Public release imminent | Multi-mechanism + DPO + merge | $20-50 |

---

## Required outputs from any larger pass

Per slm-learning-096 (3-artifact rule) + slm-learning-122 (durable
transfer artifacts):

1. Adapter / merged weights on Modal volume + HF Hub backup
2. **Outputs corpus** on a 200-prompt held-out bank (per faction)
3. **Regression journal** of every pre-existing benchmark/test
   the new pass made worse, with delta + provenance
4. Updated `reports/scaling/gad_scaling_ledger.json` entry
5. `consolidation_run.json` per `schemas/consolidation_run.schema.json`
6. **Promotion verdict** with explicit reason

If any of these are missing, the pass is REJECTED and the artifact
is `quarantined`, not promoted.

---

## What we DO NOT do

- **No "let's just try a bigger LoRA and see"** — every larger pass
  has a hypothesis tied to one of the 7 triggers above.
- **No bigger-base shots without scaling-ladder smoke** — slm-learning-097
  remains in force.
- **No silent fine-tunes** — every pass produces a consolidation_run.json.
- **No retain-bank skipping** — even larger passes must include
  retain rows; the ratio may shift (e.g., 50/50 instead of 30/70 at
  larger r), but never zero retain.

---

## Current state (2026-05-08)

| Trigger | Met? |
|---|---|
| 5+ promoted deltas per faction | NO (Stein has 2, Verifier has 1) |
| Adapter graph fragmentation | NO |
| High fallback rate | UNKNOWN (router not yet wired — Lane D blocker) |
| Retain bank size ≥500 | NO (1.5B HE retain = 90; 3B HE retain = 137) |
| Cross-skill clusters | UNTESTED (Q5 not yet run) |
| Cost-per-successful-task plateau | UNTESTED (Lane D blocker) |
| Operator override | NOT REQUESTED |

**Verdict:** No larger smoothing pass is authorized today. The
small-consolidation pregame is the active phase. Lane D (serving
+ cost matrix) and Q5 (failure clustering) are the unblockers
that decide WHEN trigger 1, 3, 5, or 6 fires.

---

## Decision proposed: slm-learning-195

> **Larger smoothing passes are gated.** The 7 triggers and 6
> gates above govern when a $5–$50 training pass is authorized.
> No larger pass fires without a documented trigger AND all gates
> green. Outputs follow the 3-artifact rule. Pregame remains the
> default until pressure accumulates enough to justify integration.

— Dr. Stein, larger smoothing pass policy, 2026-05-08
