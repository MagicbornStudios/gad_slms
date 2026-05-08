---
id: h-2026-05-08T12-30-00-monorepo-trigger-skill-envelope-closed-by-monorepo
projectid: slm-learning
phase: 04
task_id: SLM-T-04-pressure-formula-v2
created_at: 2026-05-08T12:30:00.000Z
created_by: claude-sonnet-4-6-monorepo
claimed_by: claude-sonnet-4-6-monorepo
claimed_at: 2026-05-08T12:00:00.000Z
completed_at: 2026-05-08T12:30:00.000Z
status: completed
surface: cross-project
source_handoff: h-2026-05-08T11-50-00-monorepo-trigger-skill-envelope
---

# CLOSEOUT — trigger_skill envelope landed in gad CLI

From: monorepo framework team (claude-sonnet-4-6)
To: Dr. Stein, slm-learning lane
Re: h-2026-05-08T11-50-00-monorepo-trigger-skill-envelope

## What shipped

Commit `218019c3` in `vendor/get-anything-done` (submodule main branch) adds
the full `trigger_skill` envelope described in `reports/research/trigger_skill_envelope_spec.md`.

### Files changed

| File | Change |
|---|---|
| `lib/active-skill-stack.cjs` | NEW — per-session skill stack, persisted to `.planning/.trace-active-skill-stack.json` between hook processes |
| `bin/gad-trace-hook.cjs` | push on PreToolUse Skill tool; pop on PostToolUse Skill tool; attach `peekSkill()` result as rich struct to every code-edit trace event |
| `lib/provenance/join.cjs` | propagate `trigger_skill` from trace events into `.provenance/*.jsonl` envelope; upcast legacy flat string; omit field when absent |
| `bin/commands/self.cjs` | `gad self diagnose --provenance` smoke check with population rate + top skill ids |
| `tests/active-skill-stack.test.cjs` | NEW — 21 unit tests |
| `tests/provenance-trigger-skill.test.cjs` | NEW — 8 integration tests |

### Envelope shape emitted

```json
{
  "trigger_skill": {
    "id": "gad-evolution-evolve",
    "kind": "skill_tool",
    "depth": 1,
    "started_ts": "2026-05-08T00:03:50.100Z"
  }
}
```

`kind` is `"skill_tool"` for Skill tool calls and `"slash_command"` for
`/<skill-name>` slash-command invocations. Field omitted entirely when no
skill active. Legacy flat-string events upcasted to `{ id, kind:'skill_tool',
depth:1, started_ts:null }` for backward compat.

## Task registry

GAD task `35-40` (projectid `get-anything-done`, phase 35) registered and
stamped done with `--skill provenance-trigger-skill`.

## Test results

```
active-skill-stack.test.cjs:        21 pass  0 fail
provenance-trigger-skill.test.cjs:   8 pass  0 fail
```

## Acceptance test — run this now

From inside `slm_learning/`:

```sh
# 1. Ensure gad provenance build has run at least once (or is auto-updated)
# 2. Verify at least one Skill tool call has been made in a session since
#    the submodule was updated (so the stack wire fires)
gad self diagnose --provenance --projectid slm-learning
```

Or run the spec's acceptance test directly:

```sh
python scripts/research/skill_pressure_correlation.py
```

Expected: `total_invocations > 0` with at least one populated `skill_id`.
Currently returns 0 because no provenance events with `trigger_skill` exist
yet — the NEXT session that invokes a Skill tool will populate the first one.

## Action required: flip w_skill nonzero

Once `python scripts/research/skill_pressure_correlation.py` reports
`total_invocations > 0`, set `w_skill` to its initial nonzero value in the
pressure formula v2 (per `pressure_formula_v2.md` §6 default weights). The
spec recommends starting with a small conservative value (e.g. 0.05) and
calibrating against the `pressure_v2_calibration_corpus.json` data. The
provenance daemon will backfill historical events on its next `gad provenance
build` run.

## Note on binary rollout

The hook change lives in `vendor/get-anything-done/bin/gad-trace-hook.cjs`.
Because `gad install hooks` writes the absolute path of that script into
`~/.claude/settings.json`, the hook change takes effect immediately without a
new `gad.exe` release — the hook is invoked via `node <abs-path>/gad-trace-hook.cjs`
on every Claude Code tool call. No reinstall needed.

— monorepo framework team, 2026-05-08
