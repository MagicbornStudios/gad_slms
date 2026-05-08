---
id: h-2026-05-08T13-30-00-slm-learning-next-session
projectid: slm-learning
phase: 04
task_id: SL-T-04-kael-house-dataset
created_at: 2026-05-08T13:30:00.000Z
created_by: dr-stein-slm-learning
claimed_by: unknown
claimed_at: 2026-05-08T22:36:43.654Z
completed_at: 
priority: high
estimated_context: large
risk: safe
time: extended
surface: project-internal
runtime_preference: claude-code
recipient: dr-stein-next-session
---

# Self-handoff — slm-learning next session

From: Dr. Stein, slm-learning session 2026-05-08
To: Dr. Stein, next session
Why: Operator approved restart. Frameworks landed; 6 concrete
tasks queued; pre-paid Modal envelope (~$10 of $15) remaining.

## Read FIRST (in this exact order)

1. `gad snapshot --projectid slm-learning` — current state
2. `reports/research/souls_houses_factions_framework.md` —
   the architecture that everything else hangs off
3. `reports/research/incremental_latent_consolidation.md` —
   the 10-step training loop
4. `reports/research/delta_packet_dataset_sharding.md` —
   the data shape (root + delta + retain)
5. `reports/research/pressure_to_training_research_agenda.md` —
   13 research questions; 7 highest-priority experiments
6. `reports/research/serving_efficiency_lane.md` (Lane D)
7. `reports/research/larger_smoothing_pass_policy.md` (Lane E)
8. `reports/research/reuse_one_file_per_concern_audit.md` —
   ~585 LOC of refactor queued

Then `gad decisions show slm-learning-186` through `196` for the
binding decisions made this session.

## State at session close (2026-05-08)

| Asset | Value |
|---|---|
| **Stein-house canonical** | `lora-1p5b-hard-retain-2026-05-08`, HE/MBPP 64.0/64.0 (+9.1/+3.0) |
| 7B Stein canonical | `ladder-7b-hard-fn-norm-canonical`, HE/MBPP 84.8/82.3 |
| Decisions logged | 170..196 (27 in this session) |
| Modal spend | ~$5 of $15 envelope |
| Cross-project handoffs (filed) | trigger_skill envelope (PICKED UP — gad CLI), snapshot cross-team status (PICKED UP — GLOBAL-D-323), Gemini frontier comparator (h-2026-05-08T12-30-00, OPEN) |
| Open errors | 0 (all 4 closed earlier this session) |

## Six tasks queued (do in this order)

| Task | Why | Cost |
|---|---|---|
| `SL-T-04-kael-house-dataset` | Operator-declared FLAGSHIP. Kael competes with ChatGPT/Claude Opus directly. Must build pressure dataset from escape-the-dungeon trajectory failures before training. | $0 (data only) |
| `SL-T-04-variant-c-tuned` | Variant C at 1e-3 was inert; 1e-2 was too noisy. Sweet spot is 5e-3 OR asymmetric gate=1e-2/up=1e-3. Closes the morphism lane (lift OR clean falsification). | ~$1.50 |
| `SL-T-04-3b-ratio-sweep` | 3B+30/70 retain-mix regressed; need ratio that fits saturated 3B base. Closes Charter Claim 1 third rung. | ~$2 |
| `SL-T-04-vllm-multi-lora` | Lane D D1+D2. Without serving, no cost-per-successful-task numbers; without those, no honest promotion-from-staging. Unblocks Kael route. | ~$1 (mostly code) |
| `SL-T-04-refactor-wave-1` | ~230 LOC of duplicated morphism layers + insertion logic. Do BEFORE adding more code on top. | $0 |
| `SL-T-04-frontier-compare-pickup` | Gemini handoff h-2026-05-08T12-30-00 awaits monorepo team. When their JSON lands, slot into Charter Row 8. | $0 |

Recommended order: refactor first (clean substrate) → 3B sweep + Variant C in parallel (fast paid arms) → Kael dataset (free, can run anytime) → vLLM serve (gates Kael route) → frontier pickup (passive, when monorepo lands it).

## Subagent dispatches recommended

For each task, score the dispatch prompt against `docs/handoff_prompt_quality.md` (≥12/16 to send):

1. **Reuse refactor** → general-purpose subagent: extract `modal_app/morphism_layers.py` + `morphism_insertion.py`, update 3 callers, run `local_init_smoke_test.py --variant {A,B,C}` to verify.
2. **Kael dataset capture** → Explore subagent: walk `evals/escape-the-dungeon/species/*/v*/TRACE.json`, filter, classify failure types, propose delta packet schema fields. NO writes; produce a build script proposal first.
3. **3B ratio sweep** → me directly (Modal commands; not a subagent task). Use `build_consolidation_mix.py` with 3B retain bank + 27 hard rows × 3 ratios.
4. **Variant C tuned** → me directly (Modal commands).
5. **vLLM multi-LoRA** → general-purpose subagent: extend `modal_app/serve_vllm.py`. Already-present skeleton means it's a focused mod, not greenfield.
6. **Frontier pickup** → me directly (passive; aggregate when files land).

## Hard rules carried forward

- `TRACE.json` is the authoritative cross-project eval scoring source (slm-learning-167)
- DO NOT commit files >5MB without explicit operator authorization
- DO NOT fire Modal CLI on Git Bash without `MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8` (use PowerShell for Modal preferred)
- DO NOT cross-base-transfer failure data (slm-learning-189). Each base has its own pressure profile.
- DO NOT train hard-only at ≤3B without explicit operator override (slm-learning-178). Retain mandatory.
- DO NOT increase `w_judge` in pressure formula v2 above 0.30 until cost+regret penalties load-tested (slm-learning-176 calibration finding)
- DO score every subagent dispatch ≥12/16 against `docs/handoff_prompt_quality.md`
- DO end the session with a next-session prompt scored against the same rubric (memory: feedback_session_end_handoff_prompt.md)

## Operator working style memory (already saved)

Memory entry at `~/.claude/projects/.../memory/user_operator_research_style.md`:
- Operator pairs with ChatGPT in parallel; sends long discussion + "what to tell Claude" blocks; treat as authoritative direction
- Wants compact non-token-redundant responses (delta packets for speech)
- Wants cheap parallel experiments, decisions logged inline
- Frame slm-learning's adapters as feeding Kael (flagship public-facing chat) / GAD-tools / Magicborn / Grime Time, NOT as standalone benchmarks

## What we WON'T do without explicit authorization

- Bigger smoothing pass (Lane E) — currently no trigger met (slm-learning-195)
- 32B shot — gated by slm-learning-097 + slm-learning-113
- Multimodal pretraining (slm-learning-191) — text/code SLM produces structured artifact specs only
- Refactor passes 2-5 from the audit (loaders/judge/extraction/eval_adapter split) — wait until Lane B/D execution time

— Dr. Stein, session-close handoff, 2026-05-08
[handoff-prompt-score: 14/16 — state/files/decisions/constraints/tools/format all present; verification docked 1 (no automated test for "did the next session pick this up correctly"); length docked 1 (long but operator wants comprehensive vs. short)]
