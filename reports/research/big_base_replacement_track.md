# Big-Base Replacement Track — master plan

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Decision refs:** slm-learning-097, 100, 103, 105, 168, 188, 195, 197,
198, 199, 202, 207, 208, 210, 212, 213, 218, 219
**Status:** plan-only; Phase 1 (base evals) in flight per
`reports/research/scaling_ladder_extension_plan_2026-05-09.md`. Phase 3
authorized in budget envelope ($100-300) per slm-learning-213; not
fired. Subsequent phases gated.

## 1. Goal

Replace 70-90% of operator dependency on Opus / Claude / ChatGPT for
GAD-owned work using a 5-tier GAD-owned model stack, while keeping
Opus on the hard residual. This is **not** a frontier-parity goal.
It is a routing + integration goal: the owned stack handles daily
work, frontier handles the rare hard escalations, escalation rate
trends down over time as Phase 4 RL kicks in.

We do **not** do from-scratch pretraining (Chinchilla math: 67B needs
~1.5T tokens, funding-level work). We adapt + distill + route around
high-end open Qwen.

## 2. The 5-tier model stack

| Tier | Model | Role | Compute |
|---|---|---|---|
| 1.5B | Qwen2.5-Coder-1.5B-Instruct | cheap specialist (decision summary, paraphrase, simple tool-actions) | local + Modal A10G |
| 7B | Qwen2.5-Coder-7B-Instruct (Stein canonical) | workhorse + cheap gate (eval triage, failure mining, tool-use experiments, Kael routine) | Modal A10G/A100 |
| 32B | Qwen2.5-Coder-32B-Instruct | serious open baseline + bulk_labeler when budget burns | Modal A100-80GB |
| 80B-A3B | Qwen3-Coder-Next-80B-A3B (3.9B active) OR Qwen3-Next-80B-A3B-Instruct | high-end open teacher / fallback / long-context labeler | Together API ($0.50/$1.20 per Mtok) or Modal H100 |
| Opus | Claude Opus 4.5 | premium teacher + hard-reasoning residual ($5/$25 per Mtok) | Anthropic API |

Per `reports/research/teacher_species_policy.md` (slm-learning-197):
**Opus is THE teacher**; high-end open Qwen is bulk_labeler +
comparator + inspector + fallback, NOT a teacher rival. The Big-Base
candidate adapter is the *student* of Opus traces, hosted on a
high-end open Qwen *body*.

Crucially, 7B is **NOT** the proof of replacement on novel work
(slm-learning-212). 7B is the cheap gate. The replacement claim
rides on the 32B baseline + the Big-Base LoRA candidate (Phase 3).

## 3. Phase 1 — frontier/open baseline matrix

**Status:** in flight via slm-learning-210, fire-readiness checklist
in `data/registry/scaling_ladder_gates.json`. Cost cap ~$14.

Output: HE/MBPP/gad_tools rows for 14B + 32B + 80B-A3B base. Knee
defined as smallest rung that beats 7B Stein by ≥2pp on HE AND MBPP
simultaneously. Smallest passing rung is the next workhorse-base
candidate.

The full Phase-1 matrix lives at
`benchmarks/frontier_open_replacement_matrix.yaml` — extends the base
rungs with task-shape rows (humaneval+, swe-bench-verified-subset,
aider, terminal-bench, gad_tools, tool_action_json, kael_code,
gad_decision, gad_handoff, tech_stack_inference, bestiary_artifact)
across 6 model rows. Cells that aren't measured carry the eval-fire
command and `status: pending`.

Trigger to advance: all three base rungs land + the smallest-passing
rung has knee data. If no rung passes, ladder closes; we still run
Phase 2 + 3 against 32B as the open baseline.

## 4. Phase 2 — register high-end open Qwen as open-teacher route

**Status:** doc + small JSON edit, not a code project.

Action set (NOT executed in this plan; logged for the next operator
batch):

1. Add `qwen3-coder-next-80b-a3b` row to `data/registry/model_families.json`
   with `via: together`, `cost_per_mtok_input_usd: 0.50`,
   `cost_per_mtok_output_usd: 1.20`, `roles: [bulk_labeler,
   open_weight_comparator, fallback_teacher_open]`, license_class
   open_apache_2_0 (verify before commit).
2. Add a `policies[]` entry in `data/registry/teachers.json` for
   `task_shape: code_repair_long_context` with primary_teacher
   claude-opus-4-5, fallback_teacher qwen3-coder-next-80b-a3b,
   bulk_labeler qwen3-coder-next-80b-a3b. Same-family-with-Kael-body
   note flagged as hypothesis-pending per teacher_species_policy §4.
3. Add Gateway route entry (slm-learning-208 surface) once Gateway
   exists; until then this is a doc claim, not a wiring claim.

Phase 2 has no compute cost. It is the registry + routing setup that
makes Phase 3 + Phase 4 legible.

## 5. Phase 3 — Big GAD/Kael LoRA SFT on a high-end open base

**Status:** authorized in $100-300 envelope per slm-learning-213.
Not fired. Pre-conditions ungated.

This is the **first big-base experiment**. Two candidates costed in
`reports/research/big_run_cost_plan.md`:

- **Candidate A (cheaper, $50-80):** LoRA SFT on Qwen2.5-Coder-32B
  via Modal A100 BF16, 30M tokens, owned-stack data only.
- **Candidate B (high-end, ~$120):** LoRA SFT on Qwen3-Coder-Next
  80B-A3B via Together-hosted, 30M tokens × $2.90/Mtok + eval $30.

**Pre-fire gates (per slm-learning-097):**

1. Phase 1 base evals complete; knee identified (or formally absent).
2. Clean Kael/GAD SFT corpus exists: ≥200 rows with `accepted_by`
   metadata per `schemas/teacher_policy.schema.json` §6 contract;
   delta_packet rows from operator traces + Kael-house dataset
   (slm-learning-167) + GAD-tools owned-domain rows.
3. Holdout-gate thresholds pre-registered alongside
   `data/registry/scaling_ladder_gates.json` style — written before
   training, frozen.
4. Operator authorization for the specific candidate (A or B) before
   fire.

**Go/no-go criteria (post-fire):**

- The trained candidate must beat 7B Stein canonical on ≥7 of the
  task-shapes listed in `benchmarks/frontier_open_replacement_matrix.yaml`.
- Cost-per-successful-task on the candidate must be below Opus
  per-Mtok at the same task on routine rows (Tier 1 + Tier 2).
- gad_tools owned-domain delta vs 7B Stein ≥ 0 (no moat regression).

If both gates clear: candidate is promoted as the new Big-Base
workhorse for Tier 2 routine coding-agent work; Phase 4 is unblocked.

If gates fail: log the negative result, retain artifacts (registry
row + outputs corpus + regression journal per slm-learning-096),
**do not** silently relax thresholds.

## 6. Phase 4 — DPO/KTO/GRPO from accepted_by Gateway traces

**Status:** gated by Gateway production data accumulation
(slm-learning-208).

Once Gateway ships and 30 days of `accepted_by` traces accumulate,
the corpus becomes preference data. DPO is the cheapest first arm:

- Together pricing for Qwen3-235B-A22B DPO: $15/Mtok, ~10M tokens =
  ~$150 per shot.
- Smaller/faster: DPO at 32B via Modal A100 BF16 on owned-stack
  preference pairs derived from Gateway accept/reject signal.

GRPO/RLVR comes later when the verifier loop (test-suite truth) is
wired into Gateway.

This phase **does not fire** until Gateway has shipped and produced
real preference data. Until then, Phase 4 is a placeholder, not a
work item.

## 7. Phase 5 — periodic smoothing pass (slm-learning-195 Lane E)

**Status:** existing decision; gated to fire after each major Phase 3
or Phase 4 promotion.

Smoothing reconciles drift across souls/specialists/adapters by
re-running a small SFT pass on the canonical retain bank. Cap: ~$5
per smoothing run (per Lane E policy). Fires automatically after a
Phase 3 promotion that lands new task-shape coverage.

## 8. What we DO NOT do

- **No from-scratch pretraining.** Chinchilla math is funding-level.
- **No 80B-class LoRA on unproven data.** Phase 3 fires only when
  the corpus has cleared the ≥200-row `accepted_by` gate.
- **No another 3B sweep.** 3B is structurally incompatible at LoRA
  r=16 with this dataset; closed by slm-learning-202.
- **No morphism-only rabbit hole.** Variant C class closed by
  slm-learning-201; Variant A late+retain regressed by 185.
- **No vibes promotion.** Per slm-learning-103, no candidate is
  promoted without the 4-row compare-and-compete artifact.

## 9. Decision tree

```
Phase 1 (in flight): 14B/32B/80B-A3B base evals
  |
  +-- knee at 14B  -> Phase 3 fires Candidate A (32B unchanged) OR
  |                    Candidate A swapped for 14B
  |
  +-- knee at 32B  -> Phase 3 fires Candidate A (32B is the body)
  |
  +-- 80B-A3B clears gad_tools threshold (regardless of HE/MBPP)
  |    -> Phase 2 registers 80B-A3B as labeler/fallback_teacher_open
  |    -> Phase 3 Candidate B becomes preferred IF operator approves
  |       the +$40 cost vs Candidate A
  |
  +-- no knee anywhere
       -> Phase 3 fires Candidate A on 32B (the open baseline) anyway
          because the replacement claim still needs a body bigger
          than 7B; lower confidence in lift but cost-bounded at $80
       -> OR defer Phase 3 entirely; redirect $80 toward Phase 2
          registry work + Gateway bring-up

Phase 3 result
  |
  +-- candidate beats 7B on >=7 task shapes AND cost-per-success < Opus
  |    -> promote; fire Phase 5 smoothing; unblock Phase 4 once
  |       Gateway data accumulates
  |
  +-- candidate beats 7B on 3-6 task shapes
  |    -> partial promotion: route specific task shapes; keep 7B
  |       on the rest; capture failure rows as new delta_packets
  |
  +-- candidate fails
       -> log negative; don't retry without changing the recipe;
          consider: (a) stronger teacher (Opus rows up), (b) larger
          retain bank, (c) different LoRA target_modules
```

## 10. Cost projections per phase

| Phase | Compute | Data | Eval | Total |
|---|---|---|---|---|
| 1 — base evals | $14 (Modal) | 0 | bundled | ~$14 |
| 2 — registry + routing | 0 | 0 | 0 | $0 |
| 3a — Candidate A (32B LoRA Modal) | $40 | $5-30 | $10-30 | $55-100 |
| 3b — Candidate B (80B-A3B Together) | $90 | $5-30 | $10-30 | $105-150 |
| 4 — DPO (gated) | $50-150 | gated by Gateway | $20 | $70-170 |
| 5 — smoothing (gated) | $5 | 0 | $2 | ~$7 |

Phase 3 alone fits the $100-300 envelope (slm-learning-213). Phase 4
adds budget ask later; do not roll Phase 4 into the Phase 3 fire.

## 11. Success criteria

Per operator brief and slm-learning-213:

1. **Beats current 7B on GAD-owned tasks.** ≥7 task-shapes in the
   replacement matrix lift over 7B Stein canonical.
2. **Reduces Opus usage on at least 3-5 task shapes.** Routing data
   from Gateway shows Tier 1 + Tier 2 task shapes handled locally
   ≥80% of the time.
3. **Cost-per-successful-task is below Opus.** On routine rows, the
   Big-Base candidate's cost-per-success row in
   `benchmarks/cost_per_success_by_tenant.yaml`-shaped output is
   below Opus per-Mtok cost at the same task.

The 70-90% replacement target is **stack-level**, not single-model.
If 1.5B handles decision-summary, 7B handles tool-action JSON, and
Big-Base handles repo-debugging, the stack as a whole replaces 70%+
of operator routine work even if no single model does.

## 12. Composition with prior decisions

| Decision | Composition |
|---|---|
| slm-learning-103 | Compare-and-compete: every Phase 3 promotion needs the 4-row paper artifact (public + frontier + owned + lineage). |
| slm-learning-097 | Two-shot $50: this Big-Base run is the FIRST big-base; second one fires only if first clears gates. |
| slm-learning-105 | Hardware policy: weights to Modal volume, not local. |
| slm-learning-168 | 7B Stein canonical is the anchor row — every replacement claim is measured against it. |
| slm-learning-188 | LoRA r=16 retain canonical is the recipe baseline; Phase 3 may diverge from it (larger r, different target_modules) but must justify the diverge in the run spec. |
| slm-learning-195 | Lane E smoothing fires after each promotion. |
| slm-learning-197 | Opus is THE teacher; the Big-Base body is the student. |
| slm-learning-199 | Kael's moat is integration depth × speed × cost; Big-Base does not need to match Opus on hard reasoning. |
| slm-learning-207 | Kael as entry product — Big-Base is the body Kael lives in for Tier 2. |
| slm-learning-208 | Gateway provides Phase 4 data; Phase 4 is gated on it. |
| slm-learning-210 | Phase 1 base evals are the entry to this track. |
| slm-learning-212 | 7B is not the destination; Big-Base is. |
| slm-learning-213 | $100-300 budget envelope authorized for Phase 3 first fire. |
| slm-learning-218 | Evolution-as-product: customer evolutions amortize the Big-Base infra. |
| slm-learning-219 | Customer souls compose with Big-Base via the 5-layer adapter stack. |

— Dr. Stein, Big-Base Replacement Track master plan, 2026-05-08
