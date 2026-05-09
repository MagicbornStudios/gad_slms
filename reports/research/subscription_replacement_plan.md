# Subscription Replacement Plan

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Decision refs:** slm-learning-214 (GAD-owned inference is the
default replacement path), slm-learning-215 (frontier tools become
enrichment/teacher routes), slm-learning-216 (spend ledger gates
downgrades), slm-learning-217 (replacement matrix determines training
priorities), slm-learning-103 (compare-and-compete), slm-learning-168
(hybrid runtime), slm-learning-197-200 (teacher policy + Kael moat).

## Operator direction summary (2026-05-08)

Stop paying subscriptions as the primary engine. Frontier APIs become
enrichment, evaluation, and emergency-teacher routes. Day-to-day
execution moves onto GAD-owned inference, routing, telemetry, training.

Phase budgets: P1 $150, P2 $250, P3 $400-$500. Gate: 70% local handle
for 30 consecutive days downgrades one subscription line.

Replacement priority order (highest to lowest):

1. GAD notes / decisions / handoffs
2. tool_action JSON
3. eval summaries
4. tech-stack inference
5. dataset cleanup / delta packets
6. simple code patches
7. game / bestiary / artifact generation
8. repo repair
9. hard architecture review (last)

## Tier model

| Tier | Role | Examples | Hosting |
|---|---|---|---|
| Tier 0 | Local always-on | Classification, tech-stack inference, delta-packet creation, context compression, small eval smoke, GAD note/decision/handoff parsing | Local laptop CPU/GPU, llama.cpp / vLLM small models |
| Tier 1 | Cheap remote workhorse | Routine code patches, tool_action JSON emission, eval summary, dataset cleanup | vLLM/SGLang on Modal flex / RunPod flex ($0.00019/sec idle) |
| Tier 2 | High-end open teacher/fallback | Hard tasks, teacher labels, long-context repo work, batch correction, weekly benchmark runs | Modal A100 ($0.00076/sec) / Together API (Qwen3-Coder-Next $0.50/$1.20 per Mtok) |
| Tier 3 | Frontier enrichment | Research synthesis, hard architecture review, paper-writing critique, very-hard debugging, teacher-panel disagreement, sanity checks before $50 shots | Anthropic Opus/Sonnet, OpenAI GPT-5, Gemini 2.5 Pro — pay-per-use, ONE primary frontier line at a time during transition |

## Phased plan

### Month 1 — Observe and route

**Goal:** Build the GAD inference gateway and capture every call.

| Workstream | Output | Artifact |
|---|---|---|
| Gateway | Single `gad infer` entrypoint that routes by `task_shape` and emits an `inference_trace` row per call | `schemas/inference_trace.schema.json`, `cmd/gad-infer/` |
| Task-shape classifier | Tier-0 local model that labels every call against teacher.json + replacement-plan vocabulary | Adapter: `kael-1p5b-task-shape-classifier-v1` |
| Cost logging | Every trace carries `cost_usd` resolved from registry pricing | `data/registry/model_families.json` cost fields |
| Fallback logging | `fallback_reason` + `fallback_chain` per trace | inference_trace schema |
| Edit-distance capture | Track human edit between model output and accepted text | Editor hook, claude-cli wrapper |
| Spend ledger | Monthly close + 30-day rolling local-handle rate per task shape | `reports/costs/ai_spend_ledger.md` |

**Outcome:** Every task is logged with `{task_shape, used_model,
could_local_handle, fallback_reason, value, training_candidate}`. We
know exactly where the $240/mo is going.

**Spend cap:** $150/mo. Cancel Cursor immediately (redundant). Flip
Google AI Pro to metered. ChatGPT Plus and Claude Max stay through
Month 1 for observation; route every Claude call through the gateway.

### Month 2 — Replace routine tasks

**Goal:** Move the easy half of priority items 1-5 onto Tier 0/1.

| Replacement priority | Task shape | Tier 0/1 target | Pass criterion |
|---|---|---|---|
| 1 | gad_note / gad_decision / gad_handoff | kael-1p5b-gad-meta-v1 (LoRA over Qwen2.5-Coder-1.5B) | >=90% schema-valid, operator edit distance < 10 tokens median |
| 2 | tool_action_json | kael-7b-tool-action-v1 (LoRA over Qwen2.5-Coder-7B) | >=85% on BFCL + GAD-tools owned-domain row |
| 3 | eval_summary | qwen2.5-coder-3b-instruct + retain LoRA | Operator-accept rate >=80% |
| 4 | tech_stack_inference | kael-1p5b-classifier-v1 | >=90% top-1 accuracy on held-out 200 prompts |
| 5 | dataset_cleanup, delta_packet_creation | qwen2.5-coder-7b-instruct + verifier loop | >=95% schema-valid packets, verifier passes |

**Frontier role flip.** Frontier becomes reviewer, not primary worker.
Pattern: Tier 1 emits, Tier 3 reviews ONLY when verifier disagrees or
confidence is low. Per slm-learning-197 — Opus stays the gold-label
teacher for hard rows; routine rows skip Opus entirely.

**Outcome target:** Claude/ChatGPT usage drops 30-50% by traffic.
Cursor cancelled. Spend cap $150/mo enforced.

### Month 3 — Replace coding-agent routine work

**Goal:** Claude Code is used for HARD tasks only; routine coding
moves to Tier 1/2.

| Workstream | Output |
|---|---|
| 7B/14B coding route | vLLM multi-LoRA serving Kael-7B + Kael-14B (Modal) for repo-aware tool-action and code patches |
| tool_action specialist | Promote `kael-7b-tool-action-v1` after smoke benchmark passes |
| Repo context packs | Per-repo summary + decision snapshot bundled into every Tier 1/2 call (per slm-learning-186 root context) |
| Root + delta memory | Inference traces flagged `training_candidate: true` flow into the delta-packet pipeline |
| Multi-LoRA vLLM | Single Modal endpoint hosting 3-5 specialist LoRAs hot-swappable |
| Fallback correction capture | Every Tier-3 escalation produces a delta packet for next-cycle SFT |

**Spend ceiling:** Phase 2 cap rises to $250/mo when Month-2 outcome
is hit. Spend rises temporarily because Modal/Together usage grows
while subscriptions are still active; net spend should stay flat
through the gate window.

**Outcome target:** Claude Code is used for hard architecture review
+ disagreement panels only. Daily code-edit traffic is Tier 1/2.

### Month 4+ — Distill and consolidate

**Goal:** Subscriptions become optional enrichment, not dependency.

| Specialist model | Trained from | Replaces |
|---|---|---|
| GAD tool-use model (Kael-7B-tooluse-v2) | Month 2-3 tool_action traces + Opus corrections | Most claude-cli tool emissions |
| Kael assistant model | GAD note/decision/handoff trace corpus | ChatGPT for project meta |
| Repo debugging specialist | Failed-test trace corpus + repair corrections | Cursor / claude-cli for routine repair |
| Game artifact generator | Magicborn + Grime Time output corpora | Most ChatGPT artifact prompts |
| Marketing/email assistant | Operator edit-pass corpus | ChatGPT for prose drafts |

**Spend ceiling:** Phase 3 cap $400-$500/mo, ONLY if the stack is
actively producing business/project output. If the gate has tripped
on any Tier-3 line, that line is downgraded BEFORE any cap rise.

**Outcome target:** ONE frontier subscription remains (Claude OR
ChatGPT, not both at high tier). All others are pay-per-use or
cancelled.

## Gate triggers (binding)

A line is downgraded WHEN AND ONLY WHEN all of:

1. `downgrade_gate_window_days >= 30` for the line's served task
   shapes.
2. The smoke benchmark
   (`benchmarks/day_to_day_replacement_smoke.yaml`) passes its
   threshold for those task shapes.
3. The replacement target has at least one row in the comparator
   matrix (slm-learning-103 — bare-base + frontier comparator + open
   high-end) showing the gap is acceptable.
4. The training corpus from the inference trace stream has produced
   at least one promoted adapter or has documented why no further
   training is needed.

If any condition fails, the line stays. The gate is asymmetric — easy
to fail closed, hard to fail open.

## Non-negotiable constraints

- **Single-frontier rule (Tier 3).** During transition, ONE primary
  frontier subscription. Currently Claude Max-ish; ChatGPT Plus is the
  fallback if Anthropic rate-limits and stays as enrichment-only after
  Month 2.
- **Verifier first.** Per slm-learning-197 the strictest teacher is
  the test runner / schema validator / contract checker. Every Tier
  0/1 replacement claim must show verifier pass rate, not vibes.
- **No drive-by cancellations.** A line is only cancelled after the
  gate trips. Until then, the line is downgraded (lower tier) but
  available for emergency teacher escalation.
- **Compare-and-compete.** Every promoted replacement adapter ships
  with the four comparator rows (slm-learning-103). No exceptions.
- **Hardware policy (slm-learning-105).** Anything >100MB to Modal,
  base weights on HF Hub, no >5MB local commits. Adapters live on HF
  Hub primary.

## Risks and known unknowns

| Risk | Mitigation |
|---|---|
| Tier-1/2 latency spikes on Modal cold starts | Pre-warm pool + Tier-3 emergency fallback wired into router |
| Operator edit-distance metric is noisy on prose tasks | Score by task_shape, not aggregated; prose tasks weighted lower in gate |
| GAD-owned task_shape classifier mis-routes a class of tasks | Monthly classifier retrain on operator-corrected rows; track confusion matrix |
| Cost-per-successful-task higher than frontier on small-volume task shapes | Accept higher per-task cost where total cost is lower because frontier subscription is cancelled |
| Compute provider outages (Modal / RunPod) | Multi-provider routing in gateway; OpenRouter free tier as last-ditch |

## Cross-references

- `data/registry/teachers.json` — task_shape vocabulary canonical
- `data/registry/model_families.json` — model registry with cost rates
- `reports/research/teacher_species_policy.md` — Opus-is-teacher,
  open-Qwen-is-comparator
- `reports/costs/ai_spend_ledger.md` — monthly close + downgrade log
- `reports/research/task_replacement_matrix.md` — task_shape ×
  replacement model mapping
- `benchmarks/day_to_day_replacement_smoke.yaml` — gate benchmark
- `schemas/inference_trace.schema.json` — per-call log schema
- `schemas/ai_spend_ledger.schema.json` — ledger row schema

— Dr. Stein, subscription replacement plan, 2026-05-08
