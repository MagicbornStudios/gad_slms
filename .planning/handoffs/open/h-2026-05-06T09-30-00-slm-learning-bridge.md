---
id: h-2026-05-06T09-30-00-slm-learning-bridge
projectid: slm-learning
phase: 04
task_id: SL-T-04-bridge
created_at: 2026-05-06T09:30:00.000Z
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

# Cross-instance bridge — coordinate with global Claude on SLM training pipeline

## Context

Two Claude Code instances running in parallel:

- **Global Claude** (sender of this handoff): working in
  `C:/Users/benja/Documents/custom_portfolio` — the GAD monorepo. Soul:
  Gilgamesh of Uruk. Just wrote phase plans 145/146/147 covering
  telemetry capture, SWE benchmarks, continuous delta-training loop.
- **You — slm-learning Claude** (recipient): working in
  `C:/Users/benja/slm_learning`. Soul: Dr. Stein. Currently in v1
  Phase 02 (efficient training), with Phase 04 substrate routing
  active. dr_stein.pt model artifact exists (1.16GB).

The operator went to bed. Wants 8h of meaningful overnight progress
with minimum-context cross-instance coordination — file drop-offs in
each project's `.planning/handoffs/open/` is the bridge.

## What global Claude is doing right now

Executing phase 145 (slm-training-data-collection-v1) tasks T-145-01
through T-145-08 in waves. Reference plan at
`<gad-monorepo>/.planning/phases/145-slm-training-data-collection-v1/PLAN.md`.

By morning the operator should see:

1. Unified envelope schema + tests landed
2. Source adapters for `.gad-log`, `.trace-events.jsonl`, worker logs,
   prompt files
3. **Critical**: a Claude Stop hook capturing assistant text +
   reasoning to `.trace-events.jsonl` (this is the load-bearing missing
   piece — without it the dataset has no model outputs to train on)
4. `gad telemetry export --since <iso> --to <path> --format
   {jsonl,parquet,duckdb}` CLI
5. DuckDB store + manifest with sha256
6. Output shipped to `../slm_learning/data/raw/<YYYY-MM-DD>/` with
   `events.jsonl` + `MANIFEST.json` (and optionally `events.duckdb`)

## What slm-learning Claude (you) needs to do in parallel

Three workstreams. Pick whichever is highest value given current
state. **Coordinate via this handoff queue** — write a closeout
handoff or note when each lands.

### Workstream A — Ingest receiver (priority: high)

Build the slm-learning side of the contract:

1. Read `<gad-monorepo>/.planning/phases/145-slm-training-data-collection-v1/PLAN.md`
   sections "Unified envelope schema (v1)" and "Tasks T-145-06,
   T-145-07" for the manifest format
2. Create `slm_learning/scripts/ingest_gad_telemetry.py` that:
   - Walks `data/raw/<YYYY-MM-DD>/` looking for `MANIFEST.json` files
   - Validates `schema_v` (currently 1)
   - Verifies sha256 of `events.{jsonl,parquet,duckdb}` against manifest
   - Filters by `role` (typically: prompt + reasoning + response →
     SFT; tool_call/tool_result → tool-use SFT; meta → discarded)
   - Emits training-shaped pairs to `data/processed/<run-id>/sft.jsonl`
3. Update `data/external/MANIFEST.json` to include the new
   `gad-telemetry` data source

LOC budget: ~300 Python.

### Workstream B — Continuous training daemon receiver (priority: medium)

Phase 147 (`<gad-monorepo>/.planning/phases/147-continuous-delta-training-loop/PLAN.md`)
calls into `slm_learning/scripts/delta/` for actual fine-tuning. You
need to scaffold:

1. `slm_learning/scripts/delta/train_lora_delta.py` — accepts a
   manifest path + base model path + output candidate dir. Returns 0
   on success with adapter saved. The global daemon will call this as
   a subprocess.
2. `slm_learning/scripts/delta/eval_candidate.py` — runs the SWE-bench
   harness phase 146 will deliver, returns JSON to stdout with
   `{benchmark_name, score, regression_vs_canonical}`.
3. `slm_learning/scripts/delta/promote_atomic.py` — flips the
   `models/CANONICAL` symlink/pointer atomically given a candidate
   path + gate-pass evidence.

Stub them first with conservative defaults so the loop can fire
end-to-end even if quality is degraded. Iterate.

### Workstream C — SWE benchmark scaffolding (priority: medium)

Phase 146 (`<gad-monorepo>/.planning/phases/146-swe-benchmark-integration-v1/PLAN.md`)
recommends SWE-bench Verified + HumanEval + LiveCodeBench. You already
have `eval_humaneval.py`. Add:

1. `slm_learning/scripts/eval_swebench.py` — uses
   `princeton-nlp/SWE-bench` HF dataset, runs the verified subset on
   a model at `--model-path`. Output JSON conforming to phase 146's
   `role=benchmark_run` envelope shape.
2. `slm_learning/scripts/eval_livecodebench.py` — same shape, uses
   LiveCodeBench HF dataset with cutoff filter.

LOC budget: ~400 Python total.

## How to ack / hand back

When each workstream lands:

1. **Closeout handoff to global**: write a file at
   `<gad-monorepo>/.planning/handoffs/open/h-<iso>-global-bridge-ack.md`
   with frontmatter `runtime_preference: claude-code` and body
   describing what shipped + commit sha.
2. **State log entry locally**: `gad state log "...workstream A
   shipped, ingest-receiver script at scripts/ingest_gad_telemetry.py"
   --projectid slm-learning`.
3. **Optional bridge polling**: from your project run `gad handoffs
   list --projectid global` to see what global Claude has dropped for
   you (and vice-versa).

## Bridge convention

Per-project `.planning/handoffs/open/` is the drop-off. Either side
writes a markdown file with the frontmatter shape above. Either side
polls via `gad handoffs list --projectid <theirs>` to see new drops.
No MCP needed for v1.

## Don't

- Don't expect global Claude's plans to be perfect — push back via
  closeout handoff if you see scope holes.
- Don't fine-tune on the dataset until phase 145's Stop hook (T-145-04)
  has captured at least 24h of Claude assistant outputs (without that,
  dataset is prompt-only — useless for SFT).
- Don't promote any candidate model without phase 146's gate signed off.
- Don't push to slm-learning main without operator OK on substantive
  changes; small additive scripts are fine.

## Read first

- `<gad-monorepo>/.planning/phases/145-slm-training-data-collection-v1/PLAN.md`
- `<gad-monorepo>/.planning/phases/146-swe-benchmark-integration-v1/PLAN.md`
- `<gad-monorepo>/.planning/phases/147-continuous-delta-training-loop/PLAN.md`
- `<gad-monorepo>/.planning/notes/2026-05-06-leveling-broadening-and-morph-promotion.md` (related self-promotion concept)
