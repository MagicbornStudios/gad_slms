# Kael-house dataset manifest (escape-the-dungeon)

Built: 2026-05-08T23:08:40.947432Z
Builder: scripts/data/build_kael_house_dataset.py
Root context: qwen-7b-escape-the-dungeon-trajectory
Base model: Qwen/Qwen2.5-Coder-7B-Instruct

## Counts

- Delta packets: 10
- Retain rows: 4

## Packets by failure_type

- blank_screen_render: 3
- budget_exhaustion: 1
- content_missing: 2
- game_loop_stuck: 2
- parse_exception: 1
- tool_state_corruption: 1

## Sources

- 21 TRACE.json files at `custom_portfolio/vendor/get-anything-done/evals/escape-the-dungeon/species/{bare,emergent,gad}/v*/TRACE.json`
- Schema versions handled: None (pre-versioned), 3, 4

## Lineage

- Decision refs: slm-learning-167, slm-learning-186, slm-learning-189, slm-learning-191, slm-learning-193, slm-learning-197, slm-learning-198
- Filter: `composite < composite_threshold OR human_review < human_review_threshold`
- Skipped: rate-limited (`timing.rate_limited`) and API-interrupted (`timing.api_interrupted`) traces are infrastructure failures, not agent failures.
- Skipped: traces with both composite and human_review null (no signal).

## Skipped traces

| species/version | reason |
|---|---|
| bare/v5 | above_threshold (positive run) |
| bare/v6 | no_signal (composite + human_review null) |
| emergent/v4 | above_threshold (positive run) |
| emergent/v5 | no_signal (composite + human_review null) |
| emergent/v6 | no_signal (composite + human_review null) |
| gad/v1 | no_signal (composite + human_review null) |
| gad/v10 | infra_failure (rate_limited or api_interrupted) |
| gad/v11 | no_signal (composite + human_review null) |
| gad/v12 | no_signal (composite + human_review null) |
| gad/v4 | above_threshold (positive run) |
| gad/v9 | infra_failure (rate_limited or api_interrupted) |

## Build command

```
.venv/Scripts/python.exe scripts/data/build_kael_house_dataset.py --source-root C:/Users/benja/Documents/custom_portfolio/vendor/get-anything-done/evals/escape-the-dungeon --out-dir data/delta_packets/kael-escape-the-dungeon --retain-out-dir data/retain-banks/kael-escape-the-dungeon
```

## Packet ids

- qwen-7b-etd-bare-v1-blank_screen_render
- qwen-7b-etd-bare-v2-content_missing
- qwen-7b-etd-bare-v3-content_missing
- qwen-7b-etd-emergent-v1-parse_exception
- qwen-7b-etd-emergent-v2-game_loop_stuck
- qwen-7b-etd-gad-v2-budget_exhaustion
- qwen-7b-etd-gad-v5-blank_screen_render
- qwen-7b-etd-gad-v6-blank_screen_render
- qwen-7b-etd-gad-v7-game_loop_stuck
- qwen-7b-etd-gad-v8-tool_state_corruption

## Retain output

- data\retain-banks\kael-escape-the-dungeon/passed.jsonl (4 rows)
- data\retain-banks\kael-escape-the-dungeon/profile.json
