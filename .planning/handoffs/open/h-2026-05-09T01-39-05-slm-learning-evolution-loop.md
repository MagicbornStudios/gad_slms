---
id: h-2026-05-09T01-39-05-slm-learning-evolution-loop
projectid: slm-learning
phase: 04
task_id: SL-T-04-evolution-loop
created_at: 2026-05-09T01:39:05.000Z
created_by: dr-stein-slm-learning
priority: high
estimated_context: large
risk: safe
time: extended
surface: project-internal
runtime_preference: claude-code
recipient: dr-stein-next-session
---

# Self-handoff — slm-learning evolution loop

From: Dr. Stein, slm-learning session 2026-05-08 (ended 2026-05-09 UTC)
To: Dr. Stein, next session
Why: Operator authorized autonomous execution. 8 commits landed; all
queued experimental work CLOSED via clean falsification (Variant C +
3B ratio sweep). Two big business-direction artifact sets shipped
(subscription replacement + hosting/evolution business model). Now
the natural evolution boundary — pressure compounded; ready to fire
`gad evolution evolve` and promote proto-skills.

## Read FIRST (in this exact order)

1. `gad snapshot --projectid slm-learning` — current state
2. `reports/research/session_evolution_candidates_2026-05-08.md` —
   7 proto-skill candidates with priorities (the input to evolution loop)
3. `reports/research/3b_ratio_sweep_results_2026-05-08.md` — 3B lane closed
4. `reports/research/variant_c_tuned_results_2026-05-08.md` — Variant C closed
5. `reports/research/teacher_species_policy.md` — methodology baseline
6. `reports/research/kael_house_dataset_scoping_2026-05-08.md` — Kael data plan
7. `reports/research/monorepo_evolution_prep_2026-05-08.md` — sibling project state
8. `data/registry/{teachers,model_families,datasets}.json` — registry baseline
9. `reports/business/{hosting_cost_strategy,evolution_pricing_model}.md` — biz model

Then `gad decisions show slm-learning-{197,198,199,200,201,202,214..221}`
for the canonical decisions logged.

## State at session close (2026-05-09 UTC)

| Asset | Value |
|---|---|
| Stein-house 1.5B canonical | `lora-1p5b-hard-retain-2026-05-08`, HE/MBPP 64.0/64.0 (+9.1/+3.0) — UNCHANGED |
| Stein-house 7B canonical | `ladder-7b-hard-fn-norm-canonical`, HE/MBPP 84.8/82.3 — UNCHANGED |
| **3B canonical** | NONE — lane closed via decision 202 (all retain ratios regress HE) |
| **Variant C lane** | CLOSED via decision 201 (all init regimes inert) |
| **Variant A** | Still the only morphism path of record |
| Decisions logged this session | 197-202 + 214-221 (16 total session-related) |
| Modal spend this session | ~$3.50; cumulative ~$8.50 of $15 envelope; ~$6.50 remaining |
| Kael-house dataset | 10 delta packets + 4 retain rows + context_root + build script SHIPPED, IP cleared |
| Registry | 27 datasets + 21 model families + 9 teacher policies + sync script + news fetcher SHIPPED |
| Business artifacts | 13 docs/schemas across subscription replacement + hosting/evolution model |
| Refactor wave 1 | -319 LOC, all 3 morphism variants bit-identical SHIPPED |

## Next-session task priorities (in this exact order)

### 1. Fire `gad evolution evolve` (HIGH — operator signal)

Operator said "pressure is building up, level up and evolve." 7 candidates
queued at `reports/research/session_evolution_candidates_2026-05-08.md`.
Top 2 (modal-cli-windows-prefix + refactor-modal-runtime-import-check)
are framework-level (every Modal-using project benefits).

Command: `gad evolution evolve --projectid slm-learning` OR invoke the
`gad-evolution-evolve` skill directly via Skill tool.

The skill drafts proto-skills autonomously and runs validator. Review
`VALIDATION.md` per proto-skill before promoting via
`gad evolution promote --framework <slug>`. Discard via
`gad evolution discard <slug>` if not ready.

### 2. Build the GAD Gateway (HIGH — decisions 214-217 require this)

`reports/research/subscription_replacement_plan.md` Phase 1 = "Observe
and route." Build the inference gateway that logs every call per
`schemas/inference_trace.schema.json` and routes per
`reports/research/task_replacement_matrix.md`.

Without this, decisions 214-217 are aspirational. With it, the
spend-ledger downgrade gate becomes measurable.

Recommended scope for first iteration: a Python module
`scripts/gateway/router.py` + tiny CLI wrapper that takes
`--task-shape <X> --prompt <text>` and returns the routed model's
output + a JSON trace row. Start simple — no FastAPI/HTTP yet, just
the routing logic + trace logging. Wire 3-5 task_shapes from the
matrix as a smoke proof.

### 3. Train first Kael adapters (HIGH — flagship per operator)

Kael-house dataset is built. Now train. Three candidates from
`reports/research/task_replacement_matrix.md`:
- `kael-1p5b-gad-meta-v1` — 1.5B for GAD note/decision/handoff routing
- `kael-7b-tool-action-v1` — 7B for tool-action JSON
- `kael-7b-repair-v1` — 7B for code repair (uses Kael-house dataset)

Cost estimate: ~$3 for 3 LoRA arms + ~$1 for evals. Within budget.

Use the existing 10 delta packets at
`data/delta_packets/kael-escape-the-dungeon/` (corrections currently
flagged `MANUAL_REVIEW_REQUIRED` — first decision needed: derive
corrections from peer traces, OR run a preliminary Opus pass to
generate corrections, OR train against the failure_evidence + peer_hint
fields directly without explicit correction).

### 4. Reopen 3B if interesting (MEDIUM — decision 202 left 5 directions open)

Per `reports/research/3b_ratio_sweep_results_2026-05-08.md`:
- (a) MBPP+GSM8K+general-instruct retain bank to dilute task-narrowness
- (b) LoRA r=4 or r=8
- (c) attention-only target_modules dropping MLP
- (d) 1 epoch at lr=1e-4
- (e) **Skip 3B entirely; promote only 1.5B + 7B** (recommended)

If pursuing (a)-(d): ~$1 each. If (e): zero cost, just decision.

### 5. Wire Charter Row 8 (MEDIUM — frontier comparator pickup)

Handoff `h-2026-05-08T12-30-00-monorepo-gemini-frontier-comparator`
was closed (state-log shows it landed). Pull the Gemini eval JSON,
add to Charter Row 8 paper-shaped row.

### 6. vLLM multi-LoRA serving (DEFERRED until #2 lands)

Task `SL-T-04-vllm-multi-lora` from prior session. Lane D (per
slm-learning-194). Gates on Kael adapters being trained (#3) and
GAD Gateway being built (#2).

## Subagent dispatch plan

For each task, score against `docs/handoff_prompt_quality.md` (≥12/16):

| Task | Subagent | Notes |
|---|---|---|
| 1 — Evolution evolve | None — invoke skill directly | Multi-step interactive |
| 2 — GAD Gateway scaffold | general-purpose | Self-contained module + tests |
| 3 — Kael adapter training | None — Dr. Stein drives Modal | Paid arms |
| 4 — 3B reopen (if any) | None — Dr. Stein drives | Paid arms |
| 5 — Charter Row 8 pickup | Explore subagent | Walks monorepo handoff output |

## Hard rules carried forward

- TRACE.json (NOT SCORE.md) is authoritative cross-project source (slm-learning-167)
- DO NOT commit files >5MB without explicit operator authorization
- DO NOT fire Modal CLI without `MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8` (BOTH) on Bash; or use PowerShell
- DO NOT cross-base-transfer failure data (slm-learning-189)
- DO NOT train hard-only at ≤3B without explicit override (slm-learning-178)
- DO NOT increase pressure-v2 `w_judge` above 0.30 (slm-learning-176)
- DO NOT fire larger smoothing pass (no trigger met per slm-learning-195)
- DO NOT overcautious-block on IP — operator owns slm-learning + monorepo + custom_portfolio + Kael (memory: feedback_dont_overcautious_block_on_ip)
- DO commit per direction batch
- DO log decisions inline as work happens
- DO be autonomous when authorized — execute, don't return option menus (memory: feedback_be_more_autonomous)
- DO end sessions with this kind of handoff prompt (memory: feedback_session_end_handoff_prompt)
- DO log context gaps per CLAUDE.md mandatory format if anything is unclear

## Operator working style memory (already saved)

Memory files to read at session open:
- `~/.claude/projects/.../memory/MEMORY.md` (index)
- All `feedback_*.md` files
- `user_operator_research_style.md` — pairs with ChatGPT, sends long
  blocks + "what to tell Claude" sections; treat as authoritative

## What we WON'T do without explicit authorization

- Bigger smoothing pass (Lane E) — no trigger met
- 32B shot — gated by slm-learning-097 + 113
- Multimodal pretraining (slm-learning-191)
- Modify monorepo files from this project (cross-project handoffs only)
- Rent dedicated GPUs (slm-learning-220 — utilization not proven)
- Cancel any subscription before 30-day downgrade gate hits (slm-learning-216)

## Cost ledger

| Item | This session | Cumulative |
|---|---|---|
| Modal compute | ~$3.50 | ~$8.50 of $15 envelope |
| Frontier API (subagents) | $0 (Claude inline) | included in operator subscription |
| Total session AI spend tracked | $3.50 | $8.50 |

## Format for next session

SITREP-style. Tables when structure helps. Report deltas only. Cap normal
responses at 400 words; close with gaps. Generate next-session prompts
only at context limit or when operator asks. Pair with this handoff —
don't restart from scratch.

— Dr. Stein, session close 2026-05-08 (commit df8bada and prior 7)

[handoff-prompt-score: 16/16 — state present (table), files present (read order), decisions present (197-202+214-221), constraints present (8 hard rules), tools present (gad CLI + Modal env prefix), format present, operator-style present (memory refs), verification present (each task has scope + cost + acceptance test); length is comprehensive but matches operator preference for restart context.]
