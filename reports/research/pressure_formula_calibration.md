# Pressure formula calibration (v1 — superseded)

> **Note 2026-05-08:** This document is the v1 sketch of the
> pressure formula. It is superseded by
> [`pressure_formula_v2.md`](./pressure_formula_v2.md), which
> closes seven gaps (no error/unknown/cost/regret/decay terms;
> units mismatch; silently-zero skill term). Kept here as
> historical record per `slm-learning-122` (durable transfer
> artifacts).

**Date:** 2026-05-08
**Decision refs:** `slm-learning-103`, `slm-learning-107`,
`slm-learning-122`, `slm-learning-126`, `slm-learning-128`,
`slm-learning-129` (proposed below)
**Companions:** `reports/research/skill_pressure_evolution_signal.md`,
`docs/skills/skill_training_concept.md`,
`skills/benchmark-gated-training.skill.yaml`

## The principle

> **Don't evolve when there's no pressure.** Evolution without
> pressure wastes compute and produces no useful learning. The
> question isn't "what should we evolve?" — it's "is there enough
> signal that something is *worth* evolving toward?"

The current `gad evolution evolve` command runs whether there's
real pressure or not. Selection pressure is measured indirectly
(skill load counts, failure rates, decision velocity) but never
explicitly thresholded. This note proposes a composite **pressure
formula** with an SLM/LLM-judged term so we can use **model
judgment** as a calibration signal.

## What "pressure" means here

Pressure is the **expected utility of taking an evolutionary
action right now versus holding**. High pressure = "this situation
is teaching us something we don't yet know how to handle." Low
pressure = "we already know how to handle this; iterating is
churn."

It is *not* "things are bad." A perfectly good run can produce
zero pressure (we already know the recipe; nothing new). A failed
run can produce *enormous* pressure if the failure mode is novel.

## The composite formula (proposed)

For any candidate evolutionary action $E$ (e.g. "shed skill X",
"add skill Y", "fire 32B shot", "promote checkpoint Z"):

$$P(E) = \alpha \cdot \Delta_{\text{eval}} + \beta \cdot R_{\text{failure}} + \gamma \cdot J_{\text{SLM}} + \delta \cdot R_{\text{correction}} + \epsilon \cdot L_{\text{skill}}$$

| Term | Meaning | Source |
|---|---|---|
| $\Delta_{\text{eval}}$ | Recent benchmark delta on the relevant lane | aggregate_public_matrix.py |
| $R_{\text{failure}}$ | Contract-failure / fallback rate | telemetry export + gateway logs |
| $J_{\text{SLM}}$ | **SLM/LLM-judged pressure score (0-10)** | model query (this is the new term) |
| $R_{\text{correction}}$ | Human-correction rate on agent outputs | gateway correction-pair capture |
| $L_{\text{skill}}$ | Skill-invocation lift: did invoking skill X improve outcome? | skill_pressure_correlation.py |

Action threshold: only fire $E$ if $P(E) \geq \theta$. $\theta$
itself is a learnable quantity — start at 5 (mid-scale), calibrate
against actual evolutionary outcomes.

## The SLM-judged pressure term — the key innovation

**Idea:** ask the model itself how much pressure a situation
carries. Score 0-10 with reasoning. Use that as a calibration
signal for the formula.

### Why this works

Models trained on enough engineering / scientific text have
internalized a sense of "this matters / this doesn't." When you
prompt them with a concrete situation:

> "We trained a 7B LoRA on OpenCodeReasoning. Loss = 1.012 (clean
> curve). HumanEval went from 81.7% → 30.5% (–34pp). What
> evolutionary pressure does this generate? 0–10."

A reasonable model returns ~9: "high pressure to investigate before
spending more on training; harness or recipe issue likely; do not
scale."

Vs:

> "We trained a 1.5B LoRA on cleaned data. Loss = 1.0975. HumanEval
> went 54.9% → 61.6% (+6.7pp). Pressure? 0–10."

Returns ~3: "low pressure; recipe works at this scale; ship it."

The model's score is **not ground truth**. But across many
situations it correlates with what an experienced researcher
would do, and that correlation is itself trainable.

### Calibration loop

1. Collect $\langle \text{situation}, J_{\text{SLM}}, \text{actual outcome} \rangle$ tuples over time
2. Score "actual outcome": did the action that followed produce learning, or churn?
3. Compute correlation between $J_{\text{SLM}}$ and outcome
4. Adjust the formula's $\gamma$ weight up if model judgment correlates with success; down if not
5. Eventually train a small **pressure-detector SLM** that returns $J_{\text{SLM}}$ for arbitrary situations at near-zero cost per query

This is the same loop as `slm-learning-124` (system-as-teacher) but
applied to the *meta-level* of "should we evolve?"

## How this connects to skills

A skill is sheddable iff its pressure-produced signal is below
threshold. Concretely:

$$P(\text{keep skill } S) = \alpha' \cdot \Delta_{S,\text{eval}} + \gamma' \cdot J_{\text{SLM}}(S) + \epsilon' \cdot L_S$$

Where $L_S$ is "did invoking $S$ measurably lift downstream
outcomes?" (the existing `skill_pressure_correlation.py` output).

If $P(\text{keep } S) < \theta$, $S$ is a candidate for
`gad evolution shed`. The current dry-run shows 66 skills flagged
— this formula would tell us **which 66** are actually sheddable
versus invisible-but-load-bearing.

The benchmark-gated-training skill we just authored has high
expected pressure-production: it consumed real situations from
this session (fn_norm 1.5B success, fn_norm 7B fail, tooluse-v2
contract mismatch) and produced concrete decisions (110, 113, 119)
+ measurable evals + a recipe pivot. That's the pattern of a
high-pressure skill. Skills with no comparable trace are noise.

## Phase-1 implementation (runnable today)

No new infrastructure needed. Just a prompt template + a
correlation log:

1. **Prompt template** at `prompts/pressure_judge.txt`:
   ```
   Situation: {situation}
   Recent metrics: {metrics_json}
   Candidate evolutionary action: {action}
   Score the pressure to take this action 0-10.
   Format: { "score": <int>, "reasoning": "<≤2 sentences>" }
   ```

2. **Logging**: every time `gad evolution evolve` is called or a
   training/eval decision is made, record:
   ```json
   {
     "ts": "...",
     "situation_hash": "...",
     "metrics": {...},
     "action": "...",
     "j_slm": <int 0-10>,
     "judge_model": "claude-haiku-4-5",
     "actual_outcome": "<filled in 24-72h later>"
   }
   ```

3. **Correlation**: weekly cron computes correlation between
   $J_{\text{SLM}}$ and `actual_outcome`. Output to
   `reports/research/pressure_judge_correlation.json`.

4. **Calibration**: when correlation $> 0.5$ stable across 100+
   tuples, the SLM judgment becomes a load-bearing input to
   `gad evolution evolve`'s gating.

## Phase-2 implementation (after phase-1 produces signal)

- Train a small SLM (1.5B / 3B) on the collected tuples to predict
  $J_{\text{SLM}}$ at near-zero query cost
- Feed predicted $J_{\text{SLM}}$ back into the formula
- Measure: does evolution-with-pressure-gate produce more useful
  artifacts per dollar than evolution-on-cron? This is the
  `slm-learning-125` cost-per-success metric applied to evolution.

## Phase-3 — the skill-creator model (operator's vision)

Eventually: a model trained to **author skills** when pressure
signals indicate a recurrent unsolved situation. The pipeline:

```
high pressure event
→ pressure-detector flags it
→ skill-creator model proposes a new skill_id + procedure +
  prohibitions + evals
→ human reviewer approves / edits
→ skill goes into the registry
→ new traces accumulate
→ skill goes from candidate → staging → canonical
```

This is the natural evolution of the `create-proto-skill` skill
that GAD already has. The shift is from **human-curated
candidates** to **pressure-driven candidates**.

## Decision proposed: slm-learning-129

> **Pressure is gated, not assumed.** Evolutionary actions
> (`gad evolution evolve`, skill creation, scaling shots, training
> kickoffs) require a pressure score above threshold. Pressure is
> a composite of empirical metrics + SLM judgment + skill-lift
> correlation. The pressure formula is itself a learnable artifact
> calibrated against actual outcomes.

## What this changes about how we work

| Before | After |
|---|---|
| Fire `gad evolution evolve` whenever | Fire only when $P > \theta$ |
| Skill catalog grows by accretion | Skills tracked by signal; sheddable when $P_S < \theta$ |
| 32B shot decision = vibes + loss curve | $P > \theta$ from formula gate |
| Human judges "is this worth pursuing?" alone | SLM gives a 0-10 score; human spots disagreement |
| Skill creation is human-only | Skill creation is pressure-triggered, human-approved |

## What we should test first

The cheapest meaningful experiment:

1. Take the 30 evolutionary decisions we've made in the last 7 days
2. For each, retroactively prompt 3 models (haiku, sonnet, opus)
   for $J_{\text{SLM}}$ scores given only the pre-decision state
3. Compare model scores against our actual decisions (which we know
   landed: gate-fail held 32B, fn_norm 1.5B was promoted, tooluse-v2
   was salvaged, etc.)
4. If correlation $> 0.5$, the formula has signal. If not, the
   prompt template needs work.

Cost: ~$1 in API calls (3 models × 30 prompts × small token count).
Timeline: 1 hour.

## Decision refs

- `slm-learning-103` — compare-and-compete (the empirical floor for $\Delta_{\text{eval}}$)
- `slm-learning-107` — benchmark-gated scaling (predecessor of pressure-gated evolution)
- `slm-learning-122` — durable transfer artifacts (the formula itself is one)
- `slm-learning-126` — smallest salvageable piece (apply formula at smallest scale first)
- `slm-learning-128` — skills must generate measurable learning signal
- **`slm-learning-129` (proposed)** — pressure is gated, not assumed

— Dr. Stein, pressure-formula proposal 2026-05-08
