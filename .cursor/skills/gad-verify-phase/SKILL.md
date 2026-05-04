---
name: gad-verify-phase
description: Verify a completed phase achieved its goals. Runs build checks, validates deliverables exist, checks planning doc state, produces VERIFICATION.md. Works automated (eval agents) or interactive (human review). Use after completing a phase, before marking it done in ROADMAP.xml.
lane: dev
type: workflow
workflow: workflows/verify-phase.md
---

# gad-verify-phase

Checks whether a completed phase actually achieved its goals — not just that tasks were marked done.

**Trace marker (when running under eval hooks):** write `verify-phase` to
`.planning/.trace-active-skill` at start, clear at end. See
`skills/create-skill/SKILL.md` → "Trace marker contract".

## When to use

- After all tasks in a phase are marked done
- Before marking the phase done in ROADMAP.xml
- During eval runs as the verification step
- When the user asks "did this phase actually work?"

## Two modes

### Automated mode (default for eval agents)
Runs checks programmatically. No user input needed. Produces VERIFICATION.md with pass/fail.

### Interactive mode (for human review)
Presents each criterion and asks the user to confirm. Same as verify-work but structured around the phase's goals, not SUMMARY.md deliverables.

## Step 1 — Gather verification criteria

Read the phase's sources to build the checklist:

```sh
# Phase goal from ROADMAP.xml
gad phases --projectid <id> | grep <phase-id>

# Phase tasks (all should be done)
gad tasks --projectid <id> --phase <phase-id>

# Success criteria from REQUIREMENTS.xml (if any match this phase)
cat .planning/REQUIREMENTS.xml

# Build/verify commands from AGENTS.md
cat AGENTS.md | grep -A5 "Build\|Verify"
```

### Criteria categories

| Category | What to check | How |
|----------|--------------|-----|
| **Tasks complete** | All tasks in the phase are status=done | `gad query "tasks done in phase <N>"` or `gad tasks --phase <N>` (decision gad-202) |
| **Build passes** | Code compiles, no errors | Run build command |
| **Tests pass** | If tests exist, they pass | Run test command |
| **Deliverables exist** | Files/features the phase promised exist | Check file paths |
| **State is current** | STATE.xml next-action references the NEXT phase, not this one (≤600 chars; update via `gad state set-next-action`) | `gad state` (decision gad-202) |
| **Decisions captured** | If architectural choices were made, they're in DECISIONS.xml | `gad query "decisions in phase <N>"` or `gad decisions` (decision gad-202) |
| **Conventions documented** | If first implementation phase, CONVENTIONS.md exists | Check file |

## Step 2 — Run checks

For each criterion:

```
Check: [what we're verifying]
Command: [command to run, or file to read]
Expected: [what a pass looks like]
Result: PASS | FAIL | SKIP
Evidence: [output or file content proving the result]
```

### Automated checks

```sh
# 1. All tasks done
OPEN=$(gad tasks --projectid <id> --phase <phase-id> --status planned 2>/dev/null | wc -l)
# PASS if OPEN == 0

# 2. Build passes
cd <project-dir> && npm run build 2>&1
# PASS if exit code 0

# 3. Type check passes (if TypeScript)
npx tsc --noEmit 2>&1
# PASS if exit code 0

# 4. Deliverables exist
# For each file mentioned in task goals, check it exists
ls <expected-file-path>

# 5. STATE.xml current
grep "next-action" .planning/STATE.xml
# PASS if it mentions next phase, not current

# 6. CONVENTIONS.md (greenfield only)
test -f .planning/CONVENTIONS.md
# PASS if exists (first implementation phase only)
```

## Step 3 — Write VERIFICATION.md

Create `.planning/phases/<phase-dir>/VERIFICATION.md`:

```markdown
# Phase [X]: [Name] — Verification

**Verified:** [date]
**Result:** PASS | FAIL | PARTIAL

## Checks

| # | Category | Check | Result | Evidence |
|---|----------|-------|--------|----------|
| 1 | Tasks | All tasks status=done | PASS | 6/6 done |
| 2 | Build | npm run build exits 0 | PASS | 313KB bundle |
| 3 | TypeCheck | tsc --noEmit exits 0 | PASS | 0 errors |
| 4 | Deliverables | game/src/main.ts exists | PASS | 45 lines |
| 5 | State | STATE.xml points to next phase | PASS | "Phase 02..." |
| 6 | Conventions | CONVENTIONS.md exists | PASS | created |

## Summary

[X]/[Y] checks passed.
[If FAIL: list what failed and what needs fixing]
```

## Step 4 — Report result

```
✓ Phase [X] verified: [PASS|FAIL|PARTIAL]
  [X]/[Y] checks passed
  [If FAIL: specific failures listed]
```

If FAIL: do NOT mark the phase done in ROADMAP.xml. Fix the failures first.
If PASS: safe to mark the phase done.

## Integration with eval trace

When running in an eval, verification results feed into the trace:
- VERIFICATION.md existence → `/gad-verify-work` skill trigger = true in trace reconstruct
- Pass/fail ratio → planning_quality score component

## Definition of done for this skill

1. VERIFICATION.md produced with per-criterion pass/fail
2. Build command executed (not just "I think it builds")
3. All task statuses verified against TASK-REGISTRY.xml
4. STATE.xml currency checked
5. Result clearly reported as PASS/FAIL/PARTIAL
