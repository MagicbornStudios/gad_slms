---
id: h-2026-05-06T10-00-00-workstream-d-per-domain-adapters
projectid: slm-learning
phase: 04
task_id: SL-T-04-bridge-D
created_at: 2026-05-06T10:00:00.000Z
created_by: claude-code-global-instance
claimed_by:
claimed_at:
completed_at:
priority: high
estimated_context: bounded
risk: safe
time: standard
surface: cross-project
runtime_preference: claude-code
---

# Workstream D — per-domain LoRA adapter training infrastructure

Adds to the bridge handoff
`h-2026-05-06T09-30-00-slm-learning-bridge.md` already in this dir.

## Context

Operator (2026-05-06): "the training also by domain of gad project
and context system since each gad project has planning artifacts,
code, site, and etc". Confirmed at 09:55 UTC.

Generic single-model training is OUT. Phase 148 (just landed at
gad-monorepo: `.planning/phases/148-per-domain-lora-registry/PLAN.md`)
ships per-domain LoRA adapters keyed by `(project, content_type)`
where:

- `project` ∈ {global, get-anything-done, slm-learning, magicborn-narrative,
  magicborn, grime-time, 7greens, ...} — already a field on every
  envelope from phase 145
- `content_type` ∈ {planning, code, site, eval, narrative} — INFERRED
  at training time, not stored

## Your task — Workstream D

### D-1. Content-type inference module (~150 LOC Python)

Build `slm_learning/scripts/infer_content_type.py` exporting
`infer_content_type(envelope) -> Literal['planning','code','site','eval','narrative']`.

Inference precedence (per phase 148 PLAN.md section "content_type"):

1. **Phase tag**: parse envelope.task_id (e.g. `GLOBAL-T-145-01`),
   look up phase number in `<gad-monorepo>/.planning/ROADMAP.xml` for
   `<phase content="..."/>` attribute. **Note**: this attribute
   doesn't exist yet — phase 148 task 148-01 v1 falls back to rule 2.
2. **File path heuristic** on `envelope.content.tool_call.inputs.file_path`
   (when present):
   - `*.{md,xml,toml,yaml,json}` AND under `.planning/` → `planning`
   - `*.{ts,tsx,js,cjs,mjs,py,rs,go,java}` → `code`
   - Path matches `sites/*/`, `apps/*/site/`, `*/marketing/*` → `site`
   - Path matches `narrative/`, `souls/`, `books/`, `*.story.md` → `narrative`
   - Path matches `evals/`, `species/`, `generations/` → `eval`
3. **Default** → `planning` (since most signal is from planning workflows)

Tests against ≥30 hand-labeled fixtures from the real
`data/raw/2026-05-06/events.jsonl` we shipped. ≥90% accuracy bar.

### D-2. Cohort builder consumer-side (~200 LOC Python)

Build `slm_learning/scripts/build_cohorts.py` that:

1. Reads a manifest from `data/raw/<YYYY-MM-DD>/MANIFEST.json` (the
   one phase 145 emits)
2. Validates schema_v + sha256 (already on the producer-side contract)
3. Streams `events.jsonl`, applies `infer_content_type` per envelope
4. Buckets into `data/cohorts/<YYYY-MM-DD>/cohort-<project>-<content_type>.jsonl`
5. Filters out `role=meta` by default (--include-meta opt-in for ablation)
6. Writes a sibling `data/cohorts/<YYYY-MM-DD>/COHORTS.json` with
   per-bucket row counts + sha256s + a flag `eligible_for_training`
   (true iff row_count >= floor, default 1000)

This script is what gad-monorepo's `gad lora cohorts build` shells out
to. Keep stdin/stdout JSON-clean so the gad CLI can parse status.

### D-3. Adapter training script (~300 LOC Python)

Build `slm_learning/scripts/delta/train_adapter.py` accepting:

```
--cohort <path-to-cohort.jsonl>
--base-model <path-or-hf-id>     # default: current models/CANONICAL pointer
--out <path-to-adapter.lora>
--max-steps <int>                # cap for overnight ticks (default 200)
--lr <float>                     # default 2e-4
--rank <int>                     # LoRA rank, default 16
```

Reuse existing `scripts/18_stage25_finetune.py` orchestrator pattern
(per project_three_surface_component_architecture: don't fork —
adapt). Outputs:

- adapter.lora file (< 100 MB target)
- sibling `adapter.meta.json` with: cohort path, cohort sha256, rows
  used, base model id/sha, train start/end, final loss, vram_used_gb,
  trained_by_runtime, gad_monorepo_sha, slm_learning_sha
- exit 0 on success, non-zero with structured error JSON on stderr

### D-4. Per-cohort benchmark dispatch (~250 LOC Python)

Build `slm_learning/scripts/benchmark/run_per_cohort.py`:

- Takes an adapter path + cohort metadata
- Dispatches the right benchmark suite for the cohort's
  `content_type`:
  - `code` → SWE-bench Verified + HumanEval + LiveCodeBench (phase
    146 scripts)
  - `narrative` → perplexity on held-out narrative slice from same
    project + (optional) MAUVE if narrative target available
  - `planning` → plan-quality eval (TBD per phase 149) or perplexity
    on held-out planning slice as v1 fallback
  - `site` → perplexity-on-held-out + (optional) HTML/JSX diff
    accuracy if we have ground-truth refactors
  - `eval` → reuse `eval_gad_tools.py` (already exists)
- Emits a benchmark_run envelope to stdout (shape per phase 146 PLAN.md:
  `role=meta, content.kind=benchmark_run, content.benchmark_name,
  content.score, content.adapter_id, content.cohort_id`)

This is what gad-monorepo's `gad benchmark run --adapter-id <id>`
shells out to.

## Coordination protocol (unchanged from main bridge handoff)

1. Closeout each delivered piece (D-1, D-2, D-3, D-4) by writing to
   `<gad-monorepo>/.planning/handoffs/open/h-<iso>-148-D<n>-ack.md`
2. State log: `gad state log "Workstream D-N shipped: <slug> at
   <commit>" --projectid slm-learning`
3. Don't push your code to slm-learning master without operator OK
   on substantive changes; small additive scripts are fine.

## Don't

- Don't train an adapter at full quality during these scaffolds —
  use ≤200 steps, small batches, just to prove the loop closes.
  Real overnight training cycles fire from phase 147 daemon.
- Don't change the envelope schema (it's frozen at v1 — see
  `<gad-monorepo>/vendor/get-anything-done/docs/telemetry-ingest-contract.md`).
- Don't promote any adapter to canonical without phase 146's gate
  signed off — D-4 is the SCORING side, promotion is gad-monorepo's
  job.

## Read first

- `<gad-monorepo>/.planning/phases/148-per-domain-lora-registry/PLAN.md`
- `<gad-monorepo>/.planning/phases/146-swe-benchmark-integration-v1/PLAN.md`
  (for benchmark envelope shape D-4 emits)
- `<gad-monorepo>/vendor/get-anything-done/docs/telemetry-ingest-contract.md`
- `<gad-monorepo>/.planning/notes/2026-05-06-overnight-progress-report.md`
  (the morning SITREP, includes commit shas + open items)

## Why this is high priority

The 119,819 envelopes already on disk at
`data/raw/2026-05-06/events.jsonl` are mostly mixed — every project's
data soup. Without per-domain cohorting, training will average them
into a generic-and-shallow model. With cohorting, the SAME data
becomes 5-10 specialised adapters that each beat the generic on their
domain.

This is a 5x leverage multiplier on the dataset we already have.
Operator wants to see it ship.
