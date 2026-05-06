# GAD telemetry ingest contract (received 2026-05-06)

Cross-project note received from GAD monorepo Claude (global instance).
Reciprocal of `vendor/get-anything-done/docs/telemetry-ingest-contract.md`
in the producer repo.

## Summary

Phase 145 (slm-training-data-collection-v1) shipped. The producer
emits a unified envelope per training-relevant signal (prompt,
reasoning, tool_call, tool_result, response, meta) from every gad
runtime (claude-code, codex-cli, gemini-cli, opencode, gad-cli). Each
day's batch lands at `data/raw/<YYYY-MM-DD>/{events.jsonl, MANIFEST.json}`
with sha256 + schema_v=1 + role histogram.

First real snapshot: **2026-05-06**. 119,819 envelopes / 80 MB. See
`data/raw/2026-05-06/MANIFEST.json` for exact stats.

## Pull command (run on producer side)

```sh
# In the GAD monorepo at C:/Users/benja/Documents/custom_portfolio
gad telemetry export \
  --to ../slm_learning/data/raw/<YYYY-MM-DD>/ \
  --since <ISO-8601> \
  --format jsonl
```

Schedule this nightly on the operator's machine via task scheduler /
cron / `gad cron` (when phase 147 daemon ships).

## Schema (frozen at v1)

See producer-side doc for full envelope and manifest shapes. Key
fields slm-learning consumes:

| Field | Use |
|---|---|
| `id` | Dedup primary key — stable across re-exports |
| `role` | Filter: `prompt`+`response` → SFT pairs; `reasoning` → reasoning corpus; `tool_call`+`tool_result` → tool-use SFT |
| `content.text` | Training material body |
| `runtime` | Cohort grouping (claude/codex/gemini/opencode) |
| `model` | Model attribution for ablations |
| `parent_id` | Joins tool_call → tool_result for tool-trace training |
| `task_id` | Phase context (cohort by domain) |
| `handoff_id` | Inter-runtime continuation (multi-turn studies) |
| `agent_id` | Subagent / worker identity |
| `ts` | Time-window slicing |
| `schema_v` | MUST equal 1 — fail closed on mismatch |

## Open workstreams for slm-learning Claude (Dr. Stein)

Per bridge handoff at `.planning/handoffs/open/h-2026-05-06T09-30-00-slm-learning-bridge.md`:

### Workstream A — ingest receiver (priority: high)

- `scripts/ingest_gad_telemetry.py`: validate manifest, sha256, stream
  envelopes, write training-shaped pairs to `data/processed/<run-id>/`.
- Update `data/external/MANIFEST.json` to register `gad-telemetry` source.
- Estimated: 300 LOC Python.

### Workstream B — continuous delta-training stubs

For phase 147 (continuous-delta-training-loop) which runs in global
project but invokes scripts here:

- `scripts/delta/train_lora_delta.py` — fine-tune on a manifest path
- `scripts/delta/eval_candidate.py` — run benchmark suite, return JSON
- `scripts/delta/promote_atomic.py` — flip `models/CANONICAL` on pass

Stub first, iterate quality later.

### Workstream C — SWE benchmark scaffolding (phase 146)

- `scripts/eval_swebench.py` (Verified subset, the gateway)
- `scripts/eval_livecodebench.py` (contamination canary)
- HumanEval already exists per inventory.

Output JSON conforming to phase 146's `role=benchmark_run` envelope so
results flow through the same telemetry pipeline.

## Coordination protocol

1. **Each workstream**: write a closeout handoff to global at
   `<gad-monorepo>/.planning/handoffs/open/h-<iso>-global-bridge-ack.md`
   with `runtime_preference: claude-code` and body = what shipped +
   commit sha.
2. **State log**: `gad state log "...workstream X shipped" --projectid slm-learning`.
3. **Polling**: `gad handoffs list --projectid global` to see what
   global Claude dropped for you.

## Don't

- Don't start fine-tuning on the dataset until the Stop hook
  (T-145-04) has been installed into Claude settings.json AND has
  captured at least 24h of new assistant text. Today's snapshot has
  3,497 `response` envelopes (most from codex stdout, NOT Claude
  assistant text). Without Claude's responses the dataset is
  prompt-+-codex-only — useful but lopsided.
- Don't promote any candidate model without phase 146's gate signed off.
- Don't push to slm-learning master without operator OK on substantive changes.

## Related

- Phase plans (in GAD monorepo):
  - `.planning/phases/145-slm-training-data-collection-v1/PLAN.md`
  - `.planning/phases/146-swe-benchmark-integration-v1/PLAN.md`
  - `.planning/phases/147-continuous-delta-training-loop/PLAN.md`
- Producer commit: `MagicbornStudios/get-anything-done@9a8e6acd`
- Monorepo commit: `B2Gdevs/get-anything-done-monorepo@a314c779`
