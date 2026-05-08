# Pressure-to-training research agenda

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Decisions logged:** slm-learning-186..192 (proposed below)
**Companion docs:**
- `reports/research/incremental_latent_consolidation.md` (the loop)
- `reports/research/delta_packet_dataset_sharding.md` (the data shape)
- `reports/research/scaling_proof_charter.md` (the proof discipline)

---

## Thesis

> **GAD evolves by converting ecosystem pressure into compact,
> non-redundant, base-specific delta packets, then consolidating
> those deltas through adapters, morphism layers, routers, and
> retain banks until capability improves without increasing cost
> per successful task.**

The research question is no longer "can we train a better LoRA?"
It is:

> **How does pressure inside GAD become the smallest possible
> high-value training signal that expands capability without
> bloating data, breaking old behavior, or wasting compute?**

This document enumerates the open research questions, the
experiments that answer them, and the metrics that decide.

---

## What this session has already taught us

Five empirical facts the agenda below builds on:

1. **Hard-only training regresses small/mid bases.** 0.5B+hard
   catastrophic; 1.5B+hard regressed −6.7 HE.
2. **Hard+retain LIFTS 1.5B** (+9.1 HE / +3.0 MBPP) at $0.034.
   Same hardware, same lr, same epochs — only data shape changed.
3. **Late morphism is ~19pp safer than mid morphism** at 1.5B.
   Position is a real lever.
4. **Variant B's gate-stickiness is structural** — chicken-and-egg
   of zero-init up + zero-init gate.
5. **Cross-base failure rows do not transfer** — 3B + 7B-hard
   regressed −7.3 HE. Each base has its own pressure profile.

These results define the problem shape. The agenda below tests
the rest.

---

## 13 research questions

### Q1 — Which pressure signals predict useful training data?

**Pressure sources currently visible in GAD:**
- repeated eval failures
- recurring errors (`gad errors list`)
- recurring human corrections
- fallback-to-bigger-model events
- contract-validity failures
- handoff blocked across projects
- skill repeatedly invoked without resolution
- high token/cost spent on a single task

**Experiment A:** Take 50 pressure clusters from
`.planning/.provenance/*.jsonl` + `gad errors list` + telemetry
exports. Convert each to delta packets. Train tiny LoRAs at 1.5B.
Measure which pressure types produce real eval lift.

**Pass:** ≥3 distinct pressure types correlate with
post-train eval lift > +1pp on at least one benchmark.

### Q2 — What is the minimum useful dataset?

Already partially answered: 58 rows lifted 7B (+3.1 HE);
74+90 retain mix lifted 1.5B (+9.1 HE).

**Experiment B (dataset density sweep):**
Same 1.5B base + same retain bank, vary hard count: 25 / 50 /
75 / 100 / 150. Measure lift, regression-on-retain, $/pp-lift.

**Hypothesis:** monotone-with-saturation curve. Lift grows with
hard count up to ~100 rows, then plateaus or inverts because
retain ratio becomes too thin.

### Q3 — How much retain data prevents forgetting?

**Experiment C (retain ratio sweep):**
Same 1.5B + 74 hard rows, vary retain count to hit ratios:
10/90, 30/70, 50/50, 70/30, 90/10. Measure lift, regression-on-
retain bank, regression-on-out-of-distribution benchmarks.

**Hypothesis:** sweet-spot near 30-50% hard. Below that,
under-trained on hard. Above that, forgetting risk grows.

### Q4 — Which metadata helps training vs. routing vs. ledger?

Not all metadata belongs in the prompt. Some is for the dataset
manifest, the router, the evaluator, or the ledger. Cluttered
prompts confuse training; under-typed manifests confuse routing.

**Experiment D (provenance-level sweep):**
Same hard rows, train with provenance levels:
- L0: prompt + completion only
- L1: + skill_id + failure_type
- L2: + base_model + target_contract
- L3: + tests + retain_tags + pressure_source

**Hypothesis:** L1 outperforms L0 (skill labels help). L2 ≈ L1
(base_model is a manifest field, not a prompt field). L3 hurts
(token bloat). Decision: store L2+ in manifest, prompt at L0/L1.

### Q5 — Can failure clustering remove redundant rows?

Many failures are the same underlying mistake. Clustering reduces
dataset size without losing signal.

**Experiment E:** Embed all 1.5B HE failures with sentence-transformers,
cluster by AST pattern + test-failure shape + skill_id. Train on
cluster representatives only (one row per cluster). Compare lift to
training on all-failures.

**Hypothesis:** cluster-representative training reaches ~80% of
all-failures lift at ~30% of dataset size. $/pp-lift improves.

### Q6 — Can smaller datasets beat larger generic datasets?

Already partial yes (slm-learning-130: 58 hard rows beat 1991
generic rows at 7B).

**Experiment F (general restatement):**
Vary the same 1.5B training across:
- 1991 generic fn_norm rows
- 100 1.5B-hard rows
- 100 1.5B-hard + 100 retain
- 50 cluster-rep + 100 retain (after Q5)

**Hypothesis:** hard+retain ≥ generic on lift, with 5–20× cheaper.

### Q7 — When should pressure create data vs. parameters?

Decision tree (proposed):

```
single failure                          → log only
repeated failure with clear correction  → dataset row
many rows, same task shape              → adapter / LoRA
adapter saturates or interferes         → router / specialist
adapter lifts but latency/cost too high → distill
adapter cannot absorb without regression → morphism / parameter expansion
```

**Experiment G:** Take 5 known failure types. Walk each through the
tree. Record at which level the lift stabilized.

### Q8 — Which task types are appropriate for morphism layers?

Refined rule from this session's findings (slm-learning-175 +
slm-learning-185):

**Good morphism target** (small inserted residual layer can absorb):
- compact, repeated, base-specific delta family
- late-stage output correction (formatting, decision, schema)
- behavior the base already does — just doing wrong consistently
- backed by a retain bank that anchors old behavior

**Bad morphism target** (a tiny inserted layer trained on a tiny
dataset is the wrong mechanism for these — NOT "never train this,"
just "don't expect a 0.8M-param projection to install it"):
- broad general reasoning from <100 rows
- cross-base failure knowledge
- architecture-wide changes (attention patterns, multi-FFN
  features, long-range reasoning)
- entirely new capabilities the base doesn't already do at all

Variant A late + hard-only (slm-learning-175) is currently the
best-staged morphism arm. Variant A late + retain HURT HE
(slm-learning-185), so retain-mix is NOT a universal smoother for
single-chokepoint mechanisms.

**Experiment H (morphism task-type matrix):** Test 4 task types
× 2 mechanisms (LoRA vs Variant A late). Record which mechanism
wins per task type.

### Q9 — When should we add capacity?

Pressure-gated growth ladder:

```
level 0: prompt skill (no training)
level 1: data correction (more retain rows; no model change)
level 2: LoRA r=8 small
level 3: LoRA r=16 (current canonical)
level 4: LoRA r=16 + retain-mix (current 1.5B canonical)
level 5: morphism late-layer (Variant A or C)
level 6: adapter graph + router
level 7: bigger base + adapter chain
level 8: internal MoE
```

**Experiment I:** Start at level 0 for each pressure cluster, escalate
only when previous level fails. Record at which level lift was
achieved per cluster.

### Q10 — Hard rows compressed further?

Compare 5 representations of the same hard row:
- full prompt + full canonical solution
- minimal prompt + solution
- prompt + tests + solution
- failure + correction only (delta packet form)
- skill-labeled correction (L1 of Q4)

**Hypothesis:** delta-packet form gives same-or-better lift at
~30% of token count. Direct test of "less data, more value."

### Q11 — Synthetic variants help or hurt?

For each base-failure row, generate K paraphrased variants via
haiku-class teacher, then train. But require: held-out eval +
dedup against trainset + contract validation + retain check.

Past evidence (slm-learning-093): doc-verifier r=16 augmented
REGRESSED. Augmentation needs variance, not just count.

**Experiment J:** 5 augmentation strategies × 1.5B + retain. Pass
gate is no regression on retain bank.

### Q12 — Which architecture should absorb which pressure?

Test the proposed mapping:

| Pressure | Best mechanism (predicted) |
|---|---|
| wrong output format | LoRA / adapter / prompt skill |
| repeated tool-action contract failures | tool_action specialist |
| hard coding edge cases | base-own-hard LoRA |
| small regression risk | hard+retain training |
| broad repeated task family | adapter graph |
| conflicting specialists | router-selected adapters |
| internal smoothing needed | late gated morphism |
| long trace understanding | retrieval / context scaling |
| high fallback cost | distillation into smaller specialist |

### Q13 — Cost / serving infrastructure questions

**Q13a:** Which trainer gives best $/eval-lift?
- Modal SFTTrainer (current)
- Modal + Unsloth-style optimizations
- Local 1660 Ti (free but slow)

**Q13b:** Which serving engine gives best $/successful-task?
- vLLM with multi-LoRA per-request routing
- SGLang with RadixAttention prefix caching + speculative decoding

**Q13c:** Can a 1.5B draft model accelerate 7B/32B via speculative
decoding? Measure tokens/sec + accuracy.

**Q13d:** Can quantized 32B fallback beat full 7B always-on on
$/successful-task?

These are deferred to a separate research lane; the primary lane
is data quality (Q1-Q12).

---

## Multimodal — boundary, not pretraining

Per operator 2026-05-08: do NOT start by training a multimodal
base. Start with **multimodal-adjacent structured artifacts**:
image prompt generation, sprite sheet specs, Remotion scene plans,
UI layout JSON, asset metadata tagging, art critique rubrics.

The model remains text/code-first, but produces structured
instructions for image/video systems (Kael / bestiary / sites).

**Q14 (deferred):** How far can a text/code SLM drive multimodal
pipelines through structured specs before we need a true
multimodal model?

---

## The seven highest-priority experiments

1. **Experiment B** — Dataset density sweep at 1.5B. ~$3.
2. **Experiment C** — Retain ratio sweep at 1.5B and 3B. ~$5.
3. **Experiment D** — Provenance-level sweep at 1.5B. ~$3.
4. **Experiment E** — Failure clustering + cluster-rep training. ~$2.
5. **Experiment H** — Morphism task-type matrix. ~$5.
6. **3B ratio fix** — 3B + LoRA at 15/85, 50/50, 70/30 (slm-learning-183 follow-up). ~$2.
7. **Variant C tuned init** — gate=5e-3, up=5e-3, then asymmetric
   gate=1e-2/up=1e-3 (slm-learning-184 follow-up). ~$2.

Total budget for the agenda's first pass: ~$22, well within the
remaining Modal envelope.

---

## Decisions proposed

- `slm-learning-186` — pressure becomes training data only through typed delta packets
- `slm-learning-187` — dataset density is a first-class scaling metric
- `slm-learning-188` — retain banks are required for consolidation
- `slm-learning-189` — base-specific pressure sets supersede cross-base failure transfer
- `slm-learning-190` — training cost optimization includes trainer + serving + quantization + caching + speculative decoding (deferred lane)
- `slm-learning-191` — multimodal starts as structured artifact generation, not multimodal pretraining
- `slm-learning-192` — morphism targets must be compact, repeated, base-specific delta families

— Dr. Stein, pressure-to-training research agenda, 2026-05-08
