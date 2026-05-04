---
name: trace-analysis
description: Analyze GAD trace data (.gad-log JSONL + .trace-events.jsonl + preserved eval traces) to produce usage reports such as tool mix, skill invocations, commit rhythm, token coverage, runtime mix, and per-project breakdowns.
lane: meta
type: meta-framework
---

# trace-analysis

Analyze the telemetry that GAD captures during sessions and eval runs. This skill is for measurement and reporting, not for syncing roots or compiling docs.

## Data sources

1. `.planning/.gad-log/*.jsonl`
   Raw CLI and hook-adjacent log entries.
2. `.planning/.trace-events.jsonl`
   Session trace events such as tool use, skill invocation, subagent spawn, and file mutation.
3. Project-local `.planning/.trace-events.jsonl`
   Additional trace logs inside specific tracked projects when those projects maintain their own planning root.
4. `evals/<project>/<version>/TRACE.json`
   Preserved eval artifacts with runtime identity, tokens, review outcomes, and derived metrics.

## What to produce

### Per-session report

```text
Session: <session_id>
Duration: <first_event_ts> -> <last_event_ts>
Runtime: <claude-code | codex | unknown>
Tool calls: <count>
GAD CLI calls: <count>
Skills invoked: <list with counts>
Subagents spawned: <count>
Files mutated: <count>
```

### Per-day or per-project report

- projects touched
- runtime mix
- skill usage distribution
- planning doc update rate
- token coverage and missingness
- commit rhythm or checkpoint discipline

### Self-eval or framework report

- total sessions
- total tool calls
- total or estimated tokens
- eval token totals
- runtime attribution coverage
- loop compliance
- framework-overhead ratio versus implementation work

## How to use it

- Read the available log files.
- Group by session, runtime, project, or eval version.
- Call out where data is exact versus estimated.
- Highlight missing instrumentation honestly instead of smoothing it over.

## What this is not

- Not `gad-workspace-sync` — that manages planning roots.
- Not `gad-docs-compile` — that compiles planning docs into a sink.
- Not `portfolio-sync` — that publishes public-facing artifacts.

This skill answers: "what happened in the framework?" not "where are the roots?" or "what should we publish?"
