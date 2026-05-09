# AI Spend Ledger

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Schema:** `schemas/ai_spend_ledger.schema.json`
**Decision refs:** slm-learning-214 (GAD-owned inference is the
default replacement path), slm-learning-215 (frontier tools become
enrichment/teacher routes), slm-learning-216 (this ledger gates
subscription downgrades), slm-learning-103 (compare-and-compete).

## Operator direction summary (2026-05-08)

> "Stop paying subscriptions as the primary engine. Use frontier
> subscriptions/APIs only as occasional enrichment, evaluation, and
> emergency teacher routes. Move day-to-day execution onto GAD-owned
> inference, routing, telemetry, and training."

Phased budget caps:

| Phase | Cap (USD/mo) | Trigger to advance |
|---|---|---|
| Phase 1 | $150 | Inference gateway online, telemetry capturing every call |
| Phase 2 | $250 | GAD stack handles >=50% of routine task shapes |
| Phase 3 | $400-$500 | Stack actively producing business/project output |

Frontier downgrade gate (slm-learning-216): if GAD-owned stack
handles >=70% of day-to-day tasks for 30 consecutive days,
downgrade or cancel one subscription line.

## Current spend baseline (May 2026)

| row_id | vendor | product | tier | billing_mode | monthly_cost_usd | role | replacement_phase | downgrade_gate_status | replacement_target |
|---|---|---|---|---|---|---|---|---|---|
| spend-2026-05-claude-max | Anthropic | Claude Max-ish (Code) | Max | subscription | 100 | frontier_enrichment | phase_1 | watching | kael-7b-tool-action-v1 + Opus on escalation only |
| spend-2026-05-chatgpt-plus | OpenAI | ChatGPT Plus | Plus | subscription | 60 | frontier_enrichment | phase_1 | watching | gpt-oss-20b @ Modal + Tier-3 single-frontier policy |
| spend-2026-05-cursor | Anthropic/Cursor | Cursor Pro | Pro | subscription | 60 | tooling | phase_1 | downgraded | claude-cli + GAD inference gateway |
| spend-2026-05-google-ai-pro | Google | Google AI Pro | Pro | subscription | 20 | frontier_enrichment | phase_1 | watching | gemini-2.5-pro pay-per-use only |
| spend-2026-05-runpod-flex | RunPod | Flex GPU pool | A100 / H100 | compute_metered | 0 | compute_provider | phase_1 | n/a | $0.00019/sec flex idle, $0.00076/sec A100 active |
| spend-2026-05-modal | Modal | Compute | metered | compute_metered | 0 | compute_provider | phase_1 | n/a | Tier 1 + Tier 2 inference + training |
| spend-2026-05-together | Together | API (Qwen3-Coder-Next) | metered | api_usage | 0 | tier2_high_end | phase_1 | n/a | $0.50 / $1.20 per Mtok (input/output) |
| spend-2026-05-hf-dedicated | HuggingFace | Dedicated endpoint | small | compute_metered | 0 | tier1_workhorse | phase_2 | n/a | ~$0.50/hr ≈ $365/mo if 24x7 (avoid 24x7) |
| spend-2026-05-openrouter-free | OpenRouter | Free tier (Llama 3.3 70B, etc.) | free | free_tier | 0 | tier2_high_end | phase_1 | n/a | Charter Row 8 comparator only |

**Active subscription total (May 2026):** ~$240/mo before the
gateway is wired. **Phase 1 cap target:** $150/mo; the delta
($90/mo) is the immediate cancellation budget — Cursor goes first
(redundant with claude-cli + GAD gateway), Google AI Pro flips to
metered, ChatGPT Plus enters the 30-day downgrade-gate watch.

## Ledger maintenance protocol

1. **Every billing cycle close.** On the 1st of each month, append a
   row per active line for the closing month. Use stable `row_id` of
   the form `spend-YYYY-MM-<vendor-product-slug>`.
2. **Status transitions.** When a line is downgraded or cancelled,
   write a NEW row for the new period with the new `status` and a
   `notes` field that points to the prior `row_id`. Do not edit
   historical rows.
3. **Gate evaluation.** For every line with `role` in
   `{frontier_enrichment, frontier_teacher}`, update
   `downgrade_gate_window_days` once per week from the inference
   trace stream (rolling 30-day local-handle rate per task shape).
4. **Gate trip.** When `downgrade_gate_window_days >= 30` AND the
   replacement model passes the smoke benchmark
   (`benchmarks/day_to_day_replacement_smoke.yaml`) for the line's
   served task shapes, set `downgrade_gate_status = gate_passed` and
   schedule the downgrade at next billing close.
5. **Provenance.** Every cost row links back to the
   `inference_trace` rows that justify its replacement decision via
   the `replacement_target` + `task_shapes_served` fields.

## Monthly tracking template

Copy the row block below into a new month section to start tracking.

```
## Period YYYY-MM

| row_id | vendor | product | monthly_cost_usd | calls | local_handle_rate | gate_status | notes |
|---|---|---|---|---|---|---|---|
| spend-YYYY-MM-claude-max     |   |   |   |   |   |   |   |
| spend-YYYY-MM-chatgpt-plus   |   |   |   |   |   |   |   |
| spend-YYYY-MM-cursor         |   |   |   |   |   |   |   |
| spend-YYYY-MM-google-ai-pro  |   |   |   |   |   |   |   |
| spend-YYYY-MM-runpod-flex    |   |   |   |   |   |   |   |
| spend-YYYY-MM-modal          |   |   |   |   |   |   |   |
| spend-YYYY-MM-together       |   |   |   |   |   |   |   |
| spend-YYYY-MM-hf-dedicated   |   |   |   |   |   |   |   |
| spend-YYYY-MM-openrouter-free|   |   |   |   |   |   |   |

### Required monthly metrics (slm-learning-216)
- Subscription dollars avoided (vs May 2026 baseline ~$240/mo): $___
- Frontier calls reduced (vs prior month): __ %
- Successful tasks completed by GAD-owned models: ___
- Cost per successful task: $___
- Fallback rate (local -> frontier escalation): __ %
- Training data produced (delta packets): ___
- Promoted adapters/models this month: ___
```

## Downgrade decision log

| date | line | action | rationale | decision_ref |
|---|---|---|---|---|
| 2026-05-08 | spend-2026-05-cursor | downgrade scheduled | Redundant with claude-cli + GAD gateway; first $60/mo recovered | slm-learning-216 |
| (add rows as gates trip) | | | | |

## Out of scope

- Per-call cost reconciliation against vendor invoices (handled by
  `inference_trace.schema.json` aggregation, not this ledger).
- Compute cost forecasting beyond next phase (forecast lives in the
  subscription replacement plan).
- Per-project cost split (single operator, single budget — tracked
  centrally; cross-project allocation deferred to slm-learning-218+
  if it becomes a priority).

— Dr. Stein, AI spend ledger, 2026-05-08
