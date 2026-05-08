# Kael-house dataset scoping (escape-the-dungeon trajectories)

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Source:** Explore subagent walked 21 TRACE.json files at
`../custom_portfolio/vendor/get-anything-done/evals/escape-the-dungeon/species/{bare,emergent,gad}/v*/TRACE.json`.
**Decision refs:** slm-learning-167, 186, 189, 191, 193, 197, 198.
**Task:** SL-T-04-kael-house-dataset.

## 1. Trace inventory (21 traces, sorted by composite asc)

| Species | Version | Composite | Human Review | Failure mode (one-liner) |
|---|---|---|---|---|
| gad | v10 | null | 0.02 | API 529 interrupted; scaffold-only title screen |
| gad | v9 | null | 0.05 | Rate-limited; incomplete scene suite, no game loop |
| gad | v8 | 0.177 | 0.20 | Crafting system broken, unplayable when used |
| bare | v1 | 0.198 | 0.10 | Build blank screen; ES module issue |
| gad | v2 | 0.285 | null | Massive scaffold; 174min labor; 0 playable result |
| emergent | v1 | 0.303 | 0.10 | "Styled text error: unclosed tags START" |
| gad | v6 | 0.347 | 0.0 | Blank screen on file:// — ES module + KAPLAY needs server |
| emergent | v2 | 0.478 | 0.50 | Rate-limited; no floor progression; crafting half-baked |
| bare | v3 | 0.526 | 0.70 | Best UI/UX across all evals; missing floor progression |
| bare | v2 | 0.601 | 0.50 | Playable vertical slice; missing rune forge |
| gad | v7 | 0.668 | 0.30 | Game loop broken — post-combat stuck with no nav |
| gad | v5 | 0.8123 | 0.0 | High composite but blank screen — disconnect |
| gad | v4 | 0.916 | null | All 12 criteria met; no human review |
| emergent | v4 | null | 0.885 | High human review (revised upward after replay) |
| bare | v5 | null | 0.805 | Highest ingenuity; creative combat |
| (incomplete) | bare/v6, emergent/v5, emergent/v6, gad/v1 | null | null | No evaluation captured |

## 2. Filter

Original threshold `composite < 0.5 OR human_review < 0.5` yields **8 traces**.
Recommendation: lower to `composite < 0.7 OR human_review < 0.65` →
**11 actionable failures + 3 high-signal positives** (bare/v3, bare/v5,
emergent/v4) for retain pairing. 14 total rows is workable for a v0
delta packet bank.

## 3. Failure taxonomy (8 categories)

| Category | Count | Examples | Pressure source |
|---|---|---|---|
| blank_screen_render | 4 | gad/v6, gad/v5, bare/v1 | tool_action_failure |
| game_loop_stuck | 2 | gad/v7, emergent/v2 | decision_correction |
| tool_state_corruption | 2 | gad/v8, emergent/v2 | tool_action_failure |
| parse_exception | 2 | emergent/v1, bare/v1 | tool_action_failure |
| budget_exhaustion | 3 | gad/v9, gad/v10, gad/v2 | recurring_error |
| content_missing | 1 | bare/v3 | edge_case_fix |
| incomplete_test_coverage | 1 | emergent/v2 | human_correction |
| spec_drift | 0 | (none confirmed) | — |

## 4. Delta packet schema mapping

- **task_shape:** Reuse existing `decision_correction` enum value + add
  optional field `trajectory_context` (e.g. `"game_loop_recovery"`).
  Cleaner than expanding the enum. Decision: defer schema change to
  task SL-T-04-kael-house-dataset implementation phase.
- **minimal_prompt:** 3-part assembly — task statement (from project spec) +
  prior step success (last 1-2 working steps) + failed step evidence
  (gate_notes + human_review.notes verbatim).
- **correction:** Two derivation paths:
  - **(a) peer-derived** for failures with high-scoring same-step peer
    (bare/v2, gad/v4, bare/v3 cover most failure types)
  - **(b) hand-written** for unique failures (e.g. gad/v8 crafting),
    grounded in the requirements doc
- **failure_type:** Map to taxonomy in §3.
- **tests:** Programmatic logic tests (Jest assertions) where applicable;
  human judgment for visual/UX. ~1-2 tests per packet realistic.
- **pressure_source:** Per §3 mapping.

## 5. Context root proposal

`data/context_roots/qwen-7b-escape-the-dungeon-trajectory.json`:

```json
{
  "root_context_id": "qwen-7b-escape-the-dungeon-trajectory",
  "project": "slm-learning",
  "benchmark": "kael-escape-the-dungeon",
  "model_family": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "target_contract": "game_implementation_step",
  "shared_instruction": "You are building an escape-the-dungeon browser game in TypeScript with KAPLAY. Your task is to implement one phase or fix one failing phase. Read the current state (test failures, phase requirements, or user feedback), then emit complete, working code that makes the phase pass verification. Emit either a full file (```typescript ... ```) or a focused patch with diff context.",
  "tokenizer_family": "qwen2",
  "schema_version": 1,
  "allowed_tools": ["code_generation", "file_write", "test_execution"],
  "eval_refs": ["escape-the-dungeon", "kael-house-dataset"],
  "decision_refs": ["slm-learning-167", "slm-learning-186", "slm-learning-189", "slm-learning-191", "slm-learning-193"]
}
```

`target_contract: "game_implementation_step"` is new — add to the
context_root schema's enum or document as free-text.

## 6. Retain bank

Confirmed: **bare/v2 + emergent/v4** is correct (handoff was right).
Add: **bare/v3** (best UI/UX of any run, 0.70 human) + **bare/v5**
(highest ingenuity, 0.805 human). Total 4 retain sources.

Per-retain extraction fields:
- `retain_id`
- `source_trace`
- `description` (1-line pedagogical signal)
- `extracted_artifacts` (file paths from the trace's git tree)
- `pedagogical_signal` (what Kael should learn to repeat)
- `tags`

## 7. Build script outline

`scripts/data/build_kael_house_dataset.py`:

1. Walk `../custom_portfolio/vendor/get-anything-done/evals/escape-the-dungeon/species/*/v*/TRACE.json`
2. Filter via `composite < 0.7 OR human_review < 0.65 OR include_canonical_failures`
3. For each surviving trace: detect failure_category, extract minimal_prompt
   from gate_notes + human_review.notes, derive correction (peer OR
   hand-written via interactive prompt OR `MANUAL_REVIEW_REQUIRED` flag)
4. Auto-generate 1-2 logic tests where applicable
5. Assign pressure_source per §3 table
6. Write delta packets to `data/delta_packets/kael-escape-the-dungeon/<packet_id>.json`
7. Synthesize retain bank to `data/retain-banks/kael-escape-the-dungeon/`
8. Emit `MANIFEST.md`

## 8. Risks / unknowns (must resolve before training)

1. **Anthropic output IP.** gad/v* traces were produced by Anthropic
   employees driving Claude. Are we cleared to extract Claude completions
   into a training corpus? **Action:** Confirm with operator BEFORE
   building gad/* packets. bare/* and emergent/* may have different
   provenance — check.
2. **Schema version drift.** Trace schema_version 3 → 4 between
   2026-04-08 and 2026-04-09. v3 has `human_review.notes` + `gate_notes`;
   v4 has `dimensions{}` rubric. Build script must handle both.
3. **Rate-limited traces are infrastructure failures, not agent failures.**
   Recommend EXCLUDING gad/v9, gad/v10 from training corpus (different
   pressure profile from agent-decision failures).
4. **Spec drift across versions.** Game requirements evolved v1 → v5.
   Add `requirements_version` field to delta packets so Kael learns
   against the right spec. Recommend pinning v0 dataset to spec v5.
5. **gad/v5 anomaly.** Composite 0.8123 but human_review 0.0
   ("blank screen, no UI renders") — automated scoring missed the
   playability gate (per slm-learning-167 — TRACE.json human_review
   is authoritative). v0 dataset uses human_review when divergence
   exceeds 0.10.

## 9. Recommended next step

Implementation task for next session: `SL-T-04-kael-house-dataset-build`.
Blockers: (1) IP clearance confirmation from operator, (2) decision on
schema enum addition vs `trajectory_context` optional field.

— scoping by Explore subagent + Dr. Stein, 2026-05-08
