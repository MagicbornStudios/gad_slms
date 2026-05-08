# Pressure formula v2

**Date:** 2026-05-08
**Author:** Dr. Stein
**Supersedes:** `reports/research/pressure_formula_calibration.md` (v1)
**Decision refs:** `slm-learning-103`, `slm-learning-125`,
`slm-learning-128`, `slm-learning-129`
**Decision proposed:** `slm-learning-166` (formula v2 + concrete weights)

---

## Why v2

v1 (`pressure_formula_calibration.md`) defined a 5-term sketch:

```
P(E) = α·Δ_eval + β·R_failure + γ·J_SLM + δ·R_correction + ε·L_skill
```

Audit 2026-05-08 surfaced seven gaps:

| # | Gap | Cost in practice |
|---|---|---|
| 1 | No error-pressure term | 4 currently-open errors invisible to the formula |
| 2 | No unknown/blocked-task term | Task debt invisible (note 2026-05-05 flagged this) |
| 3 | No cost penalty | $50 32B shot and $0.14 hard_fn_norm score identical at equal Δ_eval |
| 4 | No regret penalty | After ladder-3b-fn-norm regressed, formula has no memory of "we got bitten doing this kind of thing" |
| 5 | No staleness/decay | Old signals weight equal to fresh |
| 6 | Units mismatch | Δ_eval ±35pp, J_SLM 0–10, R_fail 0–1, threshold θ=5 meaningless |
| 7 | L_skill silently zero | `skill_pressure_correlation.py` returns 0 because `trigger_skill` envelope isn't in provenance |

v2 closes all seven. The cost-penalty form is **subtractive**
per operator decision 2026-05-08.

---

## The v2 formula

For any candidate evolutionary action $E$ (fire training run,
shed skill, promote checkpoint, log decision, etc.):

$$
P(E) \;=\; \underbrace{\sum_{i=1}^{7} w_i \cdot s_i(E)}_{\text{positive signal}}
       \;-\; w_{\text{cost}} \cdot C(E)
       \;-\; w_{\text{regret}} \cdot R(E)
$$

Every $s_i \in [0, 1]$. Penalties $C, R \in [0, 1]$. Threshold
**θ = 0.5**.

| Term | Symbol | Source | Range |
|---|---|---|---|
| Eval delta | $s_{\text{eval}}$ | `aggregate_public_matrix.py` | clamp(\|Δpp\| / 10, 0, 1) |
| Failure rate | $s_{\text{fail}}$ | telemetry export + gateway logs | recent contract-failure rate |
| SLM-judged pressure | $s_{\text{judge}}$ | model query (`prompts/pressure_judge.txt`) | $J_{\text{SLM}}/10$ |
| Correction rate | $s_{\text{corr}}$ | gateway correction-pair capture | rate per output |
| Skill-lift | $s_{\text{skill}}$ | `skill_pressure_correlation.py` | net signal score |
| **Error pressure (NEW)** | $s_{\text{err}}$ | `gad errors list` + decay | log-scaled count |
| **Unknown/blocked (NEW)** | $s_{\text{unk}}$ | `gad tasks list` blocked/unknown count | fraction of active tasks |
| **Cost penalty (NEW)** | $C(E)$ | action's expected USD cost | fraction of budget |
| **Regret penalty (NEW)** | $R(E)$ | recent similar-action regression | decay-weighted indicator |

---

## Term definitions (each computable from existing data)

### 1. Eval delta — $s_{\text{eval}}$

$$s_{\text{eval}} = \text{clamp}\left(\frac{|\Delta_{\text{eval,pp}}|}{10}, 0, 1\right)$$

**Sign-agnostic** because both lift and regression generate pressure
to act. A +6.7pp lift on 1.5B and a −34pp regression on 7B both
score 1.0 — both demand attention, just for opposite reasons. The
sign of the action that follows is determined elsewhere (e.g.,
"promote vs. investigate"); pressure asks only "is something
happening here?"

### 2. Failure rate — $s_{\text{fail}}$

$$s_{\text{fail}} = \frac{\text{contract-failures last 7 days}}{\text{total runs last 7 days}}$$

Already populated by output-contract validator (`slm-learning-108`).
Decay handled by the 7-day window itself.

### 3. SLM-judged pressure — $s_{\text{judge}}$

$$s_{\text{judge}} = J_{\text{SLM}} \;/\; 10$$

$J_{\text{SLM}} \in [0, 10]$ is the model's own pressure score
returned by the prompt template at `prompts/pressure_judge.txt`.
**Calibration loop is the same as v1** — collect tuples
$\langle\text{situation}, J_{\text{SLM}}, \text{outcome}\rangle$
weekly, compute correlation, tune $w_{\text{judge}}$.

### 4. Correction rate — $s_{\text{corr}}$

$$s_{\text{corr}} = \frac{\text{human-corrections last 7 days}}{\text{total outputs last 7 days}}$$

Captured by gateway correction-pair logger (`slm-learning-112`).

### 5. Skill-lift — $s_{\text{skill}}$

$$s_{\text{skill}} = \text{net\_signal\_score from skill\_pressure\_correlation.py}$$

**Currently silently 0** because `trigger_skill` envelope is
missing from provenance (telemetry gap from `slm-learning-128`).
Until that envelope is wired, set $w_{\text{skill}} = 0$ and
redistribute its weight to $s_{\text{judge}}$. Document this so
the formula doesn't silently weight a zero-evidence term.

### 6. Error pressure — $s_{\text{err}}$ (NEW)

$$s_{\text{err}} = \text{clamp}\left(\frac{\log_{10}(N_{\text{err,decayed}} + 1)}{\log_{10}(20)}, 0, 1\right)$$

Where $N_{\text{err,decayed}}$ is open errors weighted by recency:

$$N_{\text{err,decayed}} = \sum_{e \in \text{open errors}} 0.5^{\lfloor \text{age}(e) \,/\, 30\text{d}\rfloor}$$

A fresh error contributes 1.0; a 30-day-old error contributes 0.5;
60-day-old contributes 0.25. Cap at 20 errors saturating to 1.0.

Source: `gad errors list --projectid slm-learning` filtered to
`status=open` or `status=fixing`. Currently 4 such errors:

| Error ID | Age | Decayed weight |
|---|---|---|
| `subagent-committed-143mb-ocr-raw-2026-05-08` | 0 days | 1.000 |
| `eval-judge-strip-killed-body-indent-2026-05-08` | 0 days | 1.000 |
| `msys-pathconv-translates-modal-volume-paths-2026-05-08` | 0 days | 1.000 |
| `persist-path-no-slug-collision-2026-05-08` | 0 days | 1.000 |

$N_{\text{err,decayed}} = 4$. $s_{\text{err}} = \log_{10}(5)/\log_{10}(20) \approx 0.54$.

### 7. Unknown/blocked tasks — $s_{\text{unk}}$ (NEW)

$$s_{\text{unk}} = \frac{|\text{tasks}_{\text{blocked}}| + |\text{tasks}_{\text{unknown-shaped}}|}{|\text{tasks}_{\text{active}}|}$$

Where "unknown-shaped" tasks are heuristically those whose
description begins with "how do we", "research", "investigate",
or "figure out". Source: `gad tasks list --projectid slm-learning`.

### 8. Cost penalty — $C(E)$ (NEW)

$$C(E) = \text{clamp}\left(\frac{\text{expected cost}_E}{\text{action budget cap}}, 0, 1\right)$$

Action budget cap is **$15** (current Modal credit remaining).
For the candidate $E$:
- $E$ = "fire 32B + hard_fn_norm shot" → expected cost $11 → $C(E) = 0.73$
- $E$ = "fire morphism Variant A on 0.5B" → expected cost $2 → $C(E) = 0.13$
- $E$ = "calibration backread of 30 decisions" → expected cost $1 → $C(E) = 0.07$
- $E$ = "log a decision / write a doc" → expected cost $0 → $C(E) = 0.00$

This is the term that distinguishes "fire $50 32B" from "fire
$0.14 hard_fn_norm" under equal positive signal — and
operationalizes `slm-learning-125` (cost-per-successful-task).

### 9. Regret penalty — $R(E)$ (NEW)

$$R(E) = \begin{cases} 1 & \text{a similar action regressed in last 30 days} \\ 0 & \text{otherwise} \end{cases}$$

"Similar action" means same `(base_size, recipe_family)` tuple.
Examples:
- After `ladder-3b-fn-norm` regressed, $R(E) = 1$ for any $E$
  in the family `(3B, fn_norm)` for 30 days.
- $R(E) = 0$ for `(3B, hard_fn_norm)` because that's a different
  recipe family.

Source: `models/REGISTRY.json` rejected adapters indexed by
`(base, training_method)`. Decay: indicator drops to 0 after 30
days unless re-triggered.

---

## Default weights (calibrate via 30-decision backread)

| Weight | Default | Rationale |
|---|---|---|
| $w_{\text{eval}}$ | 0.25 | Strongest evidence of capability change |
| $w_{\text{judge}}$ | 0.30 | Currently 0.20 + 0.10 redistributed from $w_{\text{skill}}$ until telemetry lands |
| $w_{\text{fail}}$ | 0.10 | Operational signal |
| $w_{\text{corr}}$ | 0.10 | Operational signal |
| $w_{\text{skill}}$ | 0.00 | **Set to 0 until `trigger_skill` envelope is wired** (`slm-learning-128`) |
| $w_{\text{err}}$ | 0.10 | New term, evidence-based but unproven; conservative |
| $w_{\text{unk}}$ | 0.10 | New term, conservative |
| $w_{\text{cost}}$ | 0.20 | Subtractive; matches action-budget enforcement |
| $w_{\text{regret}}$ | 0.30 | Subtractive; biggest single negative signal — explicit memory of recent mistakes |

Sum of positive weights = 0.95 (intentionally <1.0 — leaves room
for unmeasured signal). Maximum positive signal = 0.95; maximum
penalty = 0.50; theoretical $P(E) \in [-0.5, +0.95]$.

Default $\theta = 0.5$ (mid-scale on the achievable positive
range).

---

## Action policy

| $P(E)$ range | Verdict | What it means |
|---|---|---|
| $P \geq 0.5$ | **FIRE** | Pressure clears the gate; act |
| $0.3 \leq P < 0.5$ | **HOLD** | Watch, gather more evidence |
| $0.0 \leq P < 0.3$ | **DEFER** | Don't act this cycle |
| $P < 0.0$ | **REFUSE** | Action would worsen state (penalties > signal) |

---

## Worked examples (with current state)

State at 2026-05-08:
- 4 open errors → $s_{\text{err}} = 0.54$
- ~3 blocked/unknown tasks of ~12 active → $s_{\text{unk}} \approx 0.25$
- Recent 7B + hard_fn_norm result (+3.1 HE / +1.8 MBPP) → $s_{\text{eval}} = \min(3.1/10, 1) = 0.31$
- $s_{\text{fail}}, s_{\text{corr}}$ unknown → assume 0.1 each baseline
- $s_{\text{skill}} = 0$ (telemetry gap; weight is 0)

### Example A: "Fire morphism Variant A on Qwen 0.5B"

| Term | Value | Weighted |
|---|---|---|
| $s_{\text{eval}}$ | 0.31 | 0.0775 |
| $s_{\text{fail}}$ | 0.10 | 0.0100 |
| $s_{\text{judge}}$ | est. 0.7 (untested but low risk) | 0.2100 |
| $s_{\text{corr}}$ | 0.10 | 0.0100 |
| $s_{\text{err}}$ | 0.54 | 0.0540 |
| $s_{\text{unk}}$ | 0.25 | 0.0250 |
| **positive signal** | | **0.3865** |
| $C(E)$ | 2/15 = 0.13 | −0.0260 |
| $R(E)$ | 0 (no recent regression in `(0.5B, morphism)`) | 0.0000 |
| **$P(E)$** | | **0.3605** |

Verdict: **HOLD** — close to fire-threshold. Should bump
$s_{\text{judge}}$ closer to 0.9 if morphism arch review's GREEN
verdict is taken into account, which would tip $P$ over 0.5.
**Sensitivity:** if $s_{\text{judge}} = 0.9$, $P = 0.42$; if 1.0,
$P = 0.45$. Marginal — calibration matters.

### Example B: "Fire 32B + hard_fn_norm shot"

| Term | Value | Weighted |
|---|---|---|
| $s_{\text{eval}}$ | 0.31 (predicted lift) | 0.0775 |
| $s_{\text{fail}}$ | 0.10 | 0.0100 |
| $s_{\text{judge}}$ | est. 0.6 (gated by 32B base eval first) | 0.1800 |
| $s_{\text{corr}}$ | 0.10 | 0.0100 |
| $s_{\text{err}}$ | 0.54 | 0.0540 |
| $s_{\text{unk}}$ | 0.25 | 0.0250 |
| **positive signal** | | **0.3565** |
| $C(E)$ | 11/15 = 0.73 | −0.1460 |
| $R(E)$ | 1 (`fn_norm` family regressed at 7B `slm-learning-113`) | −0.3000 |
| **$P(E)$** | | **−0.0895** |

Verdict: **REFUSE.** Cost is 73% of remaining budget AND the
`fn_norm` family has a recent regression. Even though we'd be
firing `hard_fn_norm` (different recipe), the regret penalty
fires conservatively because the families overlap. Override
requires explicit operator decision to relax $R(E)$.

This matches the current operating reality: 32B shot is on
HOLD pending 32B base eval (`slm-learning-097`). The formula
agrees with the human judgment — good calibration signal.

### Example C: "Log a decision recording today's morphism review"

| Term | Value | Weighted |
|---|---|---|
| $s_{\text{eval}}$ | 0 | 0.0000 |
| $s_{\text{judge}}$ | 0.9 (durable artifact, ties to `slm-learning-122`) | 0.2700 |
| $s_{\text{err}}$ | 0.54 | 0.0540 |
| $s_{\text{unk}}$ | 0.25 | 0.0250 |
| (others ~0.1 baseline) | | 0.0200 |
| **positive signal** | | **0.3690** |
| $C(E)$ | 0/15 = 0.00 | 0.0000 |
| $R(E)$ | 0 | 0.0000 |
| **$P(E)$** | | **0.3690** |

Verdict: **HOLD** by formula, but $s_{\text{judge}} = 0.9$ is
my own estimate. Manually I'd FIRE this. The disagreement is a
calibration signal — the formula under-weights "log a durable
artifact" because $s_{\text{eval}}$ doesn't capture meta-actions.
**Possible fix:** add an "artifact value" sub-term, or boost
$w_{\text{judge}}$ for actions where cost = 0. Defer to
calibration pass.

---

## Calibration plan (cheap, runnable today)

1. **Score 30 historical decisions** (`slm-learning-100..130`)
   retroactively. For each, compute the seven $s_i$ values from
   the state-at-decision-time, record the actual outcome (action
   that followed: did it produce learning, churn, or harm?).
2. **Run 3 model judges** in parallel (claude-haiku-4-5,
   sonnet, opus) for $J_{\text{SLM}}$ on the same 30 prompts.
3. **Linear regression** of $P(E)$ against ground-truth outcome
   binary (1 = good action, 0 = bad action). Tune the seven
   $w_i$ to maximize correlation.
4. **Cost: ~$1** in API calls. **Wall: ~1 hour.**
5. **Output:**
   - `reports/research/pressure_formula_v2_calibration.json`
     (the 30 tuples + computed $P$ + outcomes)
   - Updated weights in this doc, marked "calibrated 2026-05-XX"

---

## What still requires telemetry work

- $s_{\text{skill}}$: needs `trigger_skill` envelope in
  `.planning/.provenance/*.jsonl`. Framework-level work.
  Tracked under `slm-learning-128`. While missing,
  $w_{\text{skill}} = 0$.
- $s_{\text{fail}}$: needs gateway logs for fallback / contract
  failures. Partial today via output-contract validator.
- $s_{\text{corr}}$: needs gateway correction-pair logger.
  Partial today via decision capture.

The formula is **runnable today** with the current data sources
even with these gaps; the gaps just bias $P(E)$ lower than truth
for any action that depends on them.

---

## Migration from v1

| v1 → v2 | Action |
|---|---|
| Existing references to v1 formula | Add v2 pointer; keep v1 doc as historical record per `slm-learning-122` |
| Existing $J_{\text{SLM}}$ scoring plan | Reuse — Phase-1 implementation in v1 still applies |
| Threshold $\theta = 5$ | Replaced with $\theta = 0.5$ on the new normalized scale |
| 5-term formula | Replaced with 7+2 (signal+penalty) form above |

---

## Decision proposed: slm-learning-166

> **Pressure formula v2 supersedes v1.** The new formula has
> seven normalized [0,1] positive signal terms (eval delta,
> failure rate, SLM judgment, correction rate, skill lift, error
> pressure, unknown/blocked tasks), two subtractive penalty
> terms (cost, regret), and a θ = 0.5 fire threshold. Default
> weights are listed; calibration via the 30-decision backread
> is the next step. While `trigger_skill` telemetry is
> unwired, $w_{\text{skill}} = 0$ (redistributed to
> $w_{\text{judge}}$). The formula is computable from existing
> CLI surfaces and the `gad` snapshot today, no new
> infrastructure required.

---

## Cross-references

- `reports/research/pressure_formula_calibration.md` — v1 (historical)
- `reports/research/skill_pressure_evolution_signal.md` — skill-lift sub-term lineage
- `scripts/research/skill_pressure_correlation.py` — current implementation (returns 0)
- `.planning/notes/2026-05-05-2026-05-05-pressure-should-include-errors.md` — the 2026-05-05 note that flagged gaps 1 + 2
- `slm-learning-103` — compare-and-compete (eval delta source)
- `slm-learning-125` — cost-per-successful-task (basis for cost penalty)
- `slm-learning-128` — skills must generate measurable learning signal (basis for skill term)
- `slm-learning-129` — pressure is gated, not assumed (parent decision)

— Dr. Stein, pressure formula v2 draft, 2026-05-08
