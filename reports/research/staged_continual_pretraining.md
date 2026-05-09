# Staged Continual Pretraining — Design Report

**Date:** 2026-05-09
**Author:** claude-code (Sonnet 4.6), operator direction
**Status:** Living document — update after each CPT chain promotion

---

## 1. Bottom Line

Staged CPT expands the model's latent space through a sequence of small, reversible, eval-gated steps rather than one large pretraining run. The "no giant losses" rule is enforced structurally: each stage's token budget is capped, every merge is conditional on passing eval gates, and revert is always cheaper than the last stage cost.

---

## 2. Why Staged

- **Bounded blast radius.** Each stage touches 1-20M tokens — a fraction of a 7B model's 1.4T base pretraining budget. A bad stage is discarded; the cumulative adapter from the prior promoted stage becomes the new base. Revert cost = zero compute.
- **Regression caught early.** Retain banks are checked after every stage. A single catastrophic-forgetting event caught at stage 3 is far cheaper than discovering it after a monolithic 200M-token run.
- **Dataset tower fills incrementally.** Layer 2 data (see `reports/research/training_data_tower.md`) accumulates from daily `.planning/.gad-log/` curator output, not in a single batch. Training cadence must match data cadence — stages fire when each curated block clears promotion, not on a fixed calendar.
- **Cost is operationally predictable.** Each stage carries an `est_cost_usd` and an `authorization_required` flag. Stages under $20 auto-fire on success of the prior stage. Stages above $20 require explicit operator sign-off. No open-ended compute spend.
- **Cumulative adapter pattern.** Each promoted stage produces a LoRA adapter that is merged into the cumulative adapter path. The next stage trains on top of that cumulative adapter — not from raw base. The chain grows incrementally without re-traversing earlier data.

---

## 3. The Stage Lifecycle

Every stage passes through the following states, as defined in `cpt_stage.schema.json`:

```
planned
   |
   | (operator or auto-authorize when parent=succeeded AND cost <= $20)
   v
authorized
   |
   | (compute job fires on Modal/Together/local)
   v
running
   |
   +---> succeeded  (both regression + promotion gates pass)
   |         |
   |         +---> promoted  (adapter merged into cumulative chain)
   |         |
   |         +---> hold      (gates passed but operator wants human review)
   |
   +---> regressed  (any retain bank exceeds drop threshold)
   |         |
   |         +---> reverted  (adapter discarded, chain stays on prior promoted stage)
   |
   +---> failed     (run crashed or hard_floor breached)
             |
             +---> reverted  (same as regressed path)
```

Key invariant: `promoted` is the only terminal state that advances the cumulative adapter path. `reverted` always lands back on the last `promoted` stage — never on the raw base. The `result` object in the schema is only populated after a run completes.

---

## 4. Eval Gates

Three gate types govern every stage. All three must pass for a stage to reach `promoted`.

### Regression Gate (retain banks)

Retain banks are golden (prompt, expected_output) sets that represent capabilities the model must preserve. Each bank is indexed to a task: `hard-fn-norm-v1` covers code-completion normalization; `humaneval-clean-v1` covers Python function synthesis. The `regression_thresholds` map in `eval_gates` specifies the maximum allowable score drop per bank in percentage points.

The HumanEval judge bug (14B: 27.44 → 88.41% post-patch; 7B: 82.32 → 86.59% post-patch, confirmed 2026-05-09) is the strongest evidence for the principle that **measurement quality matters more than sample count**. Running retain banks against a buggy judge produced phantom regressions and blocked valid promotions. The lesson: before adding new retain banks, validate the judge on at least 20 held-out rows. `hard_floor` entries in the schema encode an absolute minimum below which any run is immediately aborted — these are not thresholds to tune, they are non-negotiable floors.

### Promotion Gate (target eval lift)

Each stage must demonstrate forward progress on at least one domain eval by a minimum lift (in pp). This prevents "neutral" stages from accumulating in the chain — every merge must carry measurable signal. If a stage passes regression but fails promotion, it is held for analysis rather than merged. Common causes: dataset block not curated well enough, token count too low for the target task, or the eval is measuring the wrong thing.

### Cost Gate (optional per stage)

`cost_per_success_target_usd` sets an efficiency ceiling. If a stage costs more than this value and the eval lift is marginal, the chain halts for reanalysis. This gate is optional (null) for early exploratory stages where the recipe is being calibrated, and mandatory once the recipe is validated and stages are running on a cadence.

---

## 5. Sizing Per Stage

These are opinionated defaults. Adjust after three stages of empirical data.

| Phase | Token range | Est. budget | GPU-hours | Hardware | Notes |
|---|---|---|---|---|---|
| First stage | 1-5M | $2-5 | 1-3 hrs | A100-80GB LoRA | Smoke test the recipe; validate judge before declaring done |
| Mid stages | 5-20M | $10-30 | 3-10 hrs | A100-80GB LoRA | Standard cadence; auto-authorize below $20 |
| Big-base CPT | 50-200M | $50-200 | 20-80 hrs | H100 LoRA or full-param | Rare; only after multiple mid stages prove the recipe on this base |

Reference: Together AI LoRA SFT pricing for 70-100B class is approximately $2.90/M training tokens (operator-cited). Modal A100-80GB runs roughly $3/hr; H100 roughly $4-5/hr. For 7B LoRA CPT at sequence_length=8192 and batch=32 effective, expect ~1.5 GPU-hours per 1M tokens. Calibrate against actual runs after stage v1.

Big-base CPT is the exception, not the default. Mid stages on 7B must saturate before escalating compute. The signal-strength scale is 30/300/3000 tokens for smoke/behavior/product signal — never run a product-scale stage without behavioral signal from prior smoke and behavior stages passing.

---

## 6. Rebaseline Rule

Stages chain additively. Without periodic resets, cumulative drift accumulates and the eval-gate deltas become harder to interpret.

**Rule:** After every 5 promoted stages OR after any retain-bank schema change (new bank added, bank rows swapped, judge version bump), run a full rebaseline:

1. Evaluate the current cumulative adapter against all retain banks from scratch (not delta).
2. Evaluate against the original base model on the same banks.
3. Record the cumulative drift as the baseline for the next 5-stage window.
4. If cumulative drift on any retain bank exceeds 3pp from base, investigate before running additional stages.

This rebaseline is encoded as a `v5` validation pass in the first 5-stage plan (see §8). It costs one A100-hour and ~$3. Skipping it means flying blind on cumulative forgetting.

---

## 7. Connection to Dataset Tower

CPT stages consume **Layer 2 (domain adaptation)** data exclusively. Layer 2 teaches code understanding, CLI invocation patterns, TypeScript/React/Tauri/Next idioms, and the gad CLI DSL. See `reports/research/training_data_tower.md` for the full 9-layer architecture.

Layers 3-9 (SFT, reasoning, DPO, tool/action, agent trajectory, delta packets, customer soul) are trained ON TOP of the CPT'd base, not inside CPT stages. The dependency is strict:

```
Base model
    +-- CPT chain (Layers 1-2, this document)
          +-- SFT pass (Layer 3)
          +-- Reasoning pass (Layer 4)
          +-- DPO pass (Layer 5)
          +-- Tool/Action pass (Layer 6)
          +-- Agent Trajectory pass (Layer 7)
          +-- Delta Packet corrections (Layer 8)
          +-- Customer Soul adapter (Layer 9)
```

Each upper layer trains on the cumulative CPT base, not on each other's checkpoints (except where explicit stacking is designed). The CPT chain is the shared foundation. Corrupting it corrupts everything above.

---

## 8. First 5 Stages Plan

| stage_id | base | expansion_data | tokens | budget | target_eval | retain_banks | est_outcome |
|---|---|---|---|---|---|---|---|
| `kael-7b-cpt-v1` | Qwen2.5-Coder-7B-Instruct | gad-trace-recent-60d-v1 | 1M | $5 | gad_tools_v1 ↑2pp | hard-fn-norm-v1 | Smoke-test recipe; encode recent gad CLI patterns; validate judge on 20 held-out rows before declaring done |
| `kael-7b-cpt-v2` | parent=v1 | decisions-handoffs-corpus-v1 | 3M | $10 | decision_writing_v1 ↑3pp | hard-fn-norm-v1, humaneval-clean-v1 | Encode planning artifact vocabulary (decisions, handoffs, task stamps); expect better structured-prose output from Kael |
| `kael-7b-cpt-v3` | parent=v2 | tool-action-json-v1 | 5M | $15 | tool_action_v1 ↑3pp | hard-fn-norm-v1, humaneval-clean-v1 | Encode tool_call/tool_result JSON patterns from gad-log curator; reduce schema-validation errors in live inference |
| `kael-7b-cpt-v4` | parent=v3 | delta-packets-corrected-v1 | 5M | $20 | kael_task_v1 ↑3pp | hard-fn-norm-v1, humaneval-clean-v1, tool-action-v1 | Encode correction signals from ERRORS-AND-ATTEMPTS.xml distillations; should lift on multi-step task eval and reduce known failure modes |
| `kael-7b-cpt-v5` | parent=v4 | _(validation pass, no new data)_ | 0 | $5 | no regression >1pp on any bank | all prior banks + rebaseline | Full rebaseline against base model; measure cumulative drift; record baseline for next 5-stage window |

Stage v5 is intentionally a zero-expansion validation pass. It runs no gradient updates — it only evaluates. Cost is one A100-hour for eval jobs on all banks. If cumulative drift on any bank exceeds 3pp from the raw base, the chain pauses for root-cause analysis before v6 is authorized.

---

## 9. Scaling-Up Rule

Only graduate the base lane (7B → 14B → 32B → 80B-A3B) when the 7B CPT chain demonstrably cannot lift on a target task even with focused, high-quality data. Evidence required:

1. At least 3 consecutive mid stages on 7B trained on focused data for the target task.
2. All 3 stages pass regression but fail the promotion gate (lift < threshold).
3. The data quality is confirmed good (spot-checked rows, schema-valid, no contamination).

If those three conditions hold, the limitation is model capacity, not data or recipe. Escalate to 14B for that task lane. Reference `reports/research/big_base_replacement_track.md` and `reports/research/scaling_ladder_extension_plan_2026-05-09.md` for the extended ladder plan (~$14 to eval base capability at 14B/32B/80B-A3B).

Do not escalate on intuition. The 3B regression data (HumanEval -6 to -10pp, all arms, 15/85 through 70/30 ratio sweep) showed that recipe failure and capacity failure are easily confused. Eliminate recipe causes first.

---

## 10. Operator Authorization Model

Every stage carries an `authorization_required` boolean in `run_meta`. The rule:

- `est_cost_usd <= $20`: auto-fire when parent stage `status=promoted`. No operator action needed. The `decision_after_run.decided_by` field is set to `"auto"`.
- `est_cost_usd > $20`: requires explicit operator green-light. Stage stays at `status=authorized` and does not fire until the operator updates the stage JSON with `status=running` or issues the compute command. The `decision_after_run.decided_by` field must name the operator or an agent acting on explicit operator instruction.

Rate-limit handling (per memory `feedback_runtime_fallback_on_ratelimit.md`): pretraining runs are not interactive API calls. If Modal or Together hits a capacity limit, hold the stage at `status=authorized` and retry during off-peak hours. Do not re-route pretraining to a different compute backend mid-run — checkpoint format and LoRA config must match the backend.

Big-base CPT stages ($50-200) require not just authorization but a decision entry in the GAD planning system (`gad decisions add`) documenting the capacity-failure evidence from §9 before any compute is committed.

---

*See also:* `schemas/cpt_stage.schema.json`, `data/registry/cpt_stage_plan.toml`, `reports/research/training_data_tower.md`, `reports/research/scaling_ladder_extension_plan_2026-05-09.md`
