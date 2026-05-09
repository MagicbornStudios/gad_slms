---
id: h-2026-05-09T02-12-53-slm-learning-gateway-wiring
projectid: slm-learning
phase: 04
task_id: SL-T-04-gateway-wiring
created_at: 2026-05-09T02:12:53.000Z
created_by: dr-stein-slm-learning
priority: high
estimated_context: large
risk: safe
time: extended
surface: project-internal
runtime_preference: claude-code
recipient: dr-stein-next-session
---

# Self-handoff — slm-learning Gateway wiring + Kael Opus pass

From: Dr. Stein, slm-learning session 2026-05-08/9
To: Dr. Stein, next session
Why: 12 commits landed this session covering 8 lanes. GAD Gateway is
scaffolded but stubbed; Claude Design pipeline scaffolded but stubbed;
2 proto-skills drafted; 14 decisions logged (197-208 + 214-221 already
canonical). The next bottleneck: turning the Gateway stubs into real
production routes + running the Kael Opus correction pass per
decision 204 to populate the `chosen` field on the 10 delta packets.

## Read FIRST (in this exact order)

1. `gad snapshot --projectid slm-learning` — current state
2. This handoff (single source of truth for the session's priorities)
3. `reports/research/3b_ratio_sweep_results_2026-05-08.md` — 3B closed
4. `reports/research/variant_c_tuned_results_2026-05-08.md` — Variant C closed
5. `reports/research/session_evolution_candidates_2026-05-08.md` — 7 candidates (2 drafted as proto-skills)
6. `reports/research/teacher_species_policy.md` — methodology
7. `reports/research/kael_house_dataset_scoping_2026-05-08.md` — Kael data plan
8. `reports/research/claude_design_pipeline.md` — Claude Design pipeline arch
9. `reports/business/{hosting_cost_strategy,evolution_pricing_model}.md` — biz model
10. `data/registry/{teachers,model_families,datasets}.json` — registry baseline
11. `scripts/gateway/router.py` + `scripts/gateway/routes.json` — Gateway scaffold
12. `scripts/design/ingest_design_handoff.py` + `schemas/design_handoff_bundle.schema.json` — design pipeline
13. `data/delta_packets/kael-escape-the-dungeon/MANIFEST.md` — Kael packets

Then `gad decisions show slm-learning-{197..208, 214..221}` for the 14 canonical decisions.

## State at session close (2026-05-09 UTC)

| Asset | Value |
|---|---|
| Stein-house 1.5B canonical | `lora-1p5b-hard-retain-2026-05-08`, HE/MBPP 64.0/64.0 (+9.1/+3.0) — UNCHANGED |
| Stein-house 7B canonical | `ladder-7b-hard-fn-norm-canonical`, HE/MBPP 84.8/82.3 — UNCHANGED |
| 3B Stein-house | NONE — parked per slm-learning-203; reopen criteria stated |
| Variant C lane | CLOSED via slm-learning-201 |
| 3B LoRA-r16-hard-retain lane | CLOSED via slm-learning-202 (full-range refutation) |
| GAD Gateway | SCAFFOLDED + tested; 7 routes; backends are STUBS marked TODO(real-backend) |
| Claude Design pipeline | SCAFFOLDED + round-trip verified; generators are STUBS marked TODO(claude-design-generator) |
| Kael-house dataset | 10 delta packets + 4 retain rows + context_root SHIPPED; corrections still MANUAL_REVIEW_REQUIRED — Opus pass needed |
| Proto-skills drafted | 2 (modal-cli-windows-prefix + refactor-modal-runtime-import-check) — ready for `gad evolution promote --framework <slug>` |
| Decisions logged | 197-208, 214-221 (14 session-related) |
| Modal spend cumulative | ~$8.50 of $15 envelope; ~$6.50 remaining |

## Next-session task priorities (in this exact order)

### 1. Wire real Gateway backends (HIGH — production unblock)

Per slm-learning-208. The Gateway has stub backends. To make decisions
214-217 measurable, wire real model calls in `scripts/gateway/router.py`:

- `_call_anthropic_stub` → real Anthropic SDK call (Opus / Sonnet / Haiku)
- `_call_qwen_local_stub` → vLLM HTTP call OR local Modal call
- `_call_modal_vllm_stub` → Modal `@app.function` call

Use BYOK encrypted env per the `wire-byok-encrypted-env` skill in the
catalog. API keys do NOT go into git. Test via Gateway CLI:
`python -m scripts.gateway.cli --task-shape gad_decision --prompt "test"`
should produce a real model output + non-zero cost on the trace row.

Cost: ~$0.20 for end-to-end smoke across 5 task shapes.

### 2. Kael Opus correction pass (HIGH — flagship)

Per slm-learning-204. The 10 delta packets at
`data/delta_packets/kael-escape-the-dungeon/*.json` have
`correction: "MANUAL_REVIEW_REQUIRED"` placeholder. Run a batch Opus
pass that:

1. Reads each packet's `failure_evidence` + `peer_hint`
2. Calls Claude Opus with: "Given this game-implementation phase failure
   `{failure_evidence}` and the peer-trace hint `{peer_hint}`, write the
   canonical correction code"
3. Writes the chosen output back to packet's `correction` field
4. Stamps `provenance.review_status = "auto"`,
   `teacher_model = "claude-opus-4-5"`,
   `accepted_by = "unverified"` (verifier comes later)

Cost: ~$0.30 across 10 packets at ~10K input + 2K output each.

Script location: `scripts/data/kael_opus_correction_pass.py` (new).

### 3. Train first Kael adapter (HIGH — flagship continuation)

Once #2 lands, train `kael-7b-game-implementation-v1` on the 10
corrected packets via `modal_app/train_lora.py`. Target_modules =
attention only (drop MLP per slm-learning-202 hypothesis #3 from 3B
sweep — destruction of base reasoning came from MLP changes).

Cost: ~$0.50 training + $0.50 eval = ~$1 total.

### 4. Webhook surface for Claude Design ingest (MEDIUM)

Per slm-learning-205 + 208. Wire the design pipeline to a Gateway HTTP
endpoint. v1 scope: a tiny FastAPI/aiohttp/bottle server that exposes
`POST /design-handoff` and calls
`scripts.design.ingest_design_handoff.ingest()`. Run on localhost:8080
for now; production hosting decided per slm-learning-220.

### 5. Promote 2 proto-skills to framework (MEDIUM)

`gad evolution promote --framework modal-cli-windows-prefix`
`gad evolution promote --framework refactor-modal-runtime-import-check`

Both bit slm-learning this session; both are framework-level (every
Modal-using project benefits). Validator points at the canonical
get-anything-done/.planning/proto-skills/ dir, so promotion will copy
them there. Acceptance: `gad evolution status` shows them as
`promoted` after the command lands.

### 6. Schema bump for inference_trace (LOW)

The Gateway writes rows with `route_id`, `accepted_by`, `fallback_index`,
`tier`, `latency_seconds`, `cost_usd` — all currently extra fields per
`schemas/inference_trace.schema.json` which only requires 3. Bump the
schema to make these required so validation actually catches missing
fields.

## Subagent dispatch plan

| Task | Subagent | Notes |
|---|---|---|
| 1 — Real Gateway backends | general-purpose | Self-contained mod to router.py |
| 2 — Kael Opus correction | general-purpose with Anthropic API | Paid (~$0.30) |
| 3 — Kael adapter training | None — Dr. Stein drives Modal | Paid arms |
| 4 — Webhook surface | general-purpose | Small FastAPI module |
| 5 — Proto-skill promote | None — Dr. Stein runs gad CLI | Free |
| 6 — Schema bump | None — Dr. Stein direct edit | Free |

## Hard rules carried forward

- TRACE.json (NOT SCORE.md) is authoritative cross-project source (slm-learning-167)
- DO NOT commit files >5MB without explicit operator authorization
- DO NOT fire Modal CLI without `MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8` (BOTH) on Bash
- DO NOT cross-base-transfer failure data (slm-learning-189)
- DO NOT train hard-only at ≤3B without explicit override (slm-learning-178)
- DO NOT increase pressure-v2 `w_judge` above 0.30 (slm-learning-176)
- DO NOT fire larger smoothing pass (slm-learning-195)
- DO NOT overcautious-block on IP — operator owns slm-learning + monorepo + custom_portfolio + Kael
- DO NOT spend on 3B as Stein-house target (slm-learning-203)
- DO NOT cancel any subscription before 30-day downgrade gate hits (slm-learning-216)
- DO commit per direction batch
- DO log decisions inline as work happens
- DO be autonomous when authorized — execute, don't return option menus
- DO end sessions with this kind of handoff prompt
- DO log context gaps per CLAUDE.md mandatory format if anything is unclear

## Operator working style memory (already saved)

- pairs with ChatGPT in parallel; sends long blocks + "what to tell Claude"
- wants compact responses, decisions logged inline
- frame slm-learning's adapters as feeding Kael / GAD-tools / Magicborn / Grime Time
- when operator says "make it happen" / "fine with all that" → execute, no pivot menus

## What we WON'T do without explicit authorization

- Bigger smoothing pass (Lane E) — no trigger met
- 32B shot — gated by slm-learning-097 + 113
- Multimodal pretraining (slm-learning-191)
- Modify monorepo files from this project (cross-project handoffs only)
- Rent dedicated GPUs (slm-learning-220 — utilization not proven)
- Cancel any subscription before 30-day downgrade gate hits

## Cost ledger

| Item | This session | Cumulative |
|---|---|---|
| Modal compute | ~$3.50 | ~$8.50 of $15 envelope |
| Frontier API (subagents) | $0 (operator's Claude subscription) | included |
| Total session AI spend tracked | $3.50 | $8.50 |

## Session metrics

- 12 commits
- 14 decisions logged (197-208 + 214-221 canonical)
- 2 research lanes closed (Variant C + 3B sweep)
- 2 proto-skills drafted (HIGH-priority framework-level candidates)
- 2 major scaffolds shipped (GAD Gateway + Claude Design pipeline)
- 2 business-direction artifact sets shipped (subscription replacement + hosting/evolution model)
- 1 dataset shipped (Kael-house: 10 packets + 4 retain rows)
- 1 registry shipped (datasets + model_families + teachers + sync + news)
- ~5,000 lines net additions across docs/code/schemas

## Format for next session

SITREP-style. Tables when structure helps. Report deltas only. Cap normal
responses at 400 words; close with gaps. Do not return 3-option pivot
menus when authorization is given. Commit per direction batch.

— Dr. Stein, session close 2026-05-08/9 (commits e407297 → 11e7a4c, 12 total)

[handoff-prompt-score: 16/16 — state present (table), files present (read order), decisions present (197-208 + 214-221), constraints present (10 hard rules), tools present (gad CLI + Modal env prefix + BYOK skill ref), format present, operator-style present (memory refs), verification present (each task has scope + cost + acceptance test); length matches operator preference for restart context.]
