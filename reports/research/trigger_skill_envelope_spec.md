# trigger_skill envelope spec

**Date:** 2026-05-08
**Author:** Dr. Stein (slm-learning lane)
**Decision refs:** `slm-learning-128`, `slm-learning-166` (proposed v2 formula)
**Status:** SPEC ONLY — implementation is a **framework-level (gad CLI)** change, NOT a slm-learning-internal fix.
**Consumer:** `scripts/research/skill_pressure_correlation.py` (currently returns 0)

---

## 1. Current envelope shape

Provenance events are emitted by the gad CLI hook-runtime (PreToolUse / PostToolUse hooks installed via `gad install hooks --claude` into Claude Code's `settings.json`). One JSON object per line in `.planning/.provenance/<YYYY-MM-DD>.jsonl`:

```json
{
  "event_id": "359-4e184952-...",
  "ts": "2026-05-08T00:03:53.909Z",
  "seq": 359,
  "tool": "Write",
  "file_path": "C:\\Users\\benja\\...\\reports\\evals\\humaneval_chat_vs_completion.md",
  "diff": { "kind": "write", "content": "..." },
  "runtime": { "id": "claude-code", "model_id": "claude-opus-4-7",
               "session_id": "...", "source": "hook-runtime" },
  "agent": { "id": null, "role": null, "parent": null, "depth": null, ... },
  "handoff": { "id": "h-2026-05-07T15-50-09-slm-learning-04", ... },
  "task": null,
  "project": { "id": "slm-learning", "root_path": "..." },
  "label": { "verdict": "in_progress", "reason": "...", "confidence": 1 }
}
```

**No `trigger_skill` field exists.** The extractor at `scripts/research/skill_pressure_correlation.py:101` reads `event.get("trigger_skill")`, which is always `None`, so `s_skill = 0` in the v2 pressure formula.

## 2. Proposed envelope shape

Add ONE optional top-level field, `trigger_skill`, populated when the tool-use was invoked from inside an active Skill tool call or `/<skill-name>` slash-command:

```json
{
  "event_id": "...", "ts": "...", "tool": "Write",
  "trigger_skill": {
    "id": "gad-evolution-evolve",
    "kind": "skill_tool",          // or "slash_command"
    "depth": 1,                    // nested skill calls increment
    "started_ts": "2026-05-08T00:03:50.100Z"
  },
  "runtime": { ... }, "agent": { ... }, "project": { ... }
}
```

When no skill is active, omit the field entirely (do not write `null`) so existing parsers stay compatible.

## 3. Where the writing happens

The hook-runtime that already stamps `runtime.source = "hook-runtime"` writes these envelopes. Source lives in the gad CLI binary at `C:\Users\benja\AppData\Local\Programs\gad\bin\gad.exe` — the **canonical repo is `MagicbornStudios/get-anything-done`** (per `build-and-release-locally` skill). It is NOT in this slm_learning tree. This change must land there and ship in a new gad release.

Suggested code locations (in get-anything-done, not here):
1. The PreToolUse hook handler — push `{skill_id, kind, started_ts}` onto a per-session active-skill stack on Skill / slash invocation, pop on completion.
2. The provenance writer — read top-of-stack, attach as `trigger_skill` if non-empty.
3. CLI surface: `gad self diagnose --provenance` should show recent `trigger_skill` populations as a smoke check.

## 4. What constitutes a `trigger_skill`

Both, with `kind` distinguishing them:
- `Skill` tool call (Claude harness `Skill` tool with `skill: "<name>"`) → `kind = "skill_tool"`
- `/<skill-name>` slash-command invocation surfaced via the harness → `kind = "slash_command"`

Plain tool calls (Read, Write, Bash) outside any skill envelope leave the field absent. Nested skill invocations increment `depth` and the innermost skill is the one stamped onto child tool events.

## 5. Cross-project handoff status

**Framework-level. STOP.** Per the hard constraint of this spec task, slm-learning cannot fix this. Open a handoff to the gad CLI maintainers (canonical repo `MagicbornStudios/get-anything-done`) referencing `slm-learning-128` and this spec. Until the gad release lands, set `w_skill = 0` in the v2 pressure formula (already done — see `pressure_formula_v2.md` §6 default weights).

## 6. Acceptance test

After the gad CLI change ships and an agent session runs at least one Skill tool call:

```
python scripts/research/skill_pressure_correlation.py
```

must report **at least one nonzero invocation count** in `reports/research/skill_pressure_correlation.json` (i.e. the top-level `total_invocations` field > 0, with at least one `skill_id` populated from `trigger_skill.id`). The current run reports 0 invocations because the field is never emitted; a single populated event is the binary pass/fail signal.

— Dr. Stein, 2026-05-08
