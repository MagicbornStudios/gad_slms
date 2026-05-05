---
name: gad-handoffs
description: >-
  Work-stealing handoff queue across parallel agent runtimes. Use whenever you
  need to hand off work to another agent (different runtime / different lane / next
  session), pick up assigned work on session open, or check what's waiting. Per-file
  directory layout under .planning/handoffs/{open,claimed,closed}/, atomic fs.rename
  lifecycle, every gad CLI call is safe against concurrent agents. Required reading
  for every session start; supersedes the old .continue-here.md pattern.
lane: dev
type: workflow
allowed-tools:
  - Bash
---

# gad-handoffs

Canonical workflow for the `gad handoffs` CLI family (shipped 2026-04-18, task
60-09). Every agent in every runtime consults this skill when they need to
either produce a handoff (pause / cross-lane request / end-of-session) or
consume one (session-start pickup / reassignment).

## When to use

| Moment | Direction | Reach for |
|---|---|---|
| Session open | Consume | `gad handoffs list --mine-first` as step 2 of the daily workflow |
| Pausing mid-work | Produce | `gad handoffs create` with a self-contained body |
| Touching a file outside your lane | Produce | `gad handoffs create --runtime-preference <owning-lane>` |
| Reassigning stalled work to another agent | Produce | same |
| Context exhaustion near auto-compact | Produce | write the handoff BEFORE compaction so future-you has the state |

## When NOT to use

- A task you'll finish in the same session — just do it. Handoffs are for work
  that crosses an agent / session / lane boundary.
- Architectural decisions — those go in `DECISIONS.xml` via `gad decisions add`.
- Design sketches that aren't action items — those go in `.planning/notes/`.
- Purely internal state (e.g. "what's the current test count") — that goes in
  the `STATE.xml` state-log or the task registry, not the queue.

## The five verbs

```sh
gad handoffs list [--unclaimed|--claimed|--closed|--all] [--projectid <id>] [--mine-first] [--json]
gad handoffs show <id>
gad handoffs claim <id> [--agent <name>]
gad handoffs complete <id>
gad handoffs create --projectid <id> --phase <N> --task-id <t> \
  --priority <low|normal|high> --context <mechanical|reasoning> \
  [--runtime-preference <claude-code|codex|cursor>] \
  --body "<self-contained instructions>"
```

`list` defaults to the `open` bucket. `--mine-first` sorts by matching
`runtime_preference` so a codex agent sees codex-targeted handoffs first.
`--json` emits `[]` when empty (needed for shell gating in hooks).

## Lifecycle

```
open/     ─ gad handoffs claim ────> claimed/ ─ gad handoffs complete ─> closed/
  │                                     │                                   │
  │ created by `gad handoffs create`    │ owner works it                    │ audit trail
  │ or author's own fs.rename           │                                   │
```

Transitions are `fs.renameSync` — atomic on both POSIX and Windows on the
same filesystem. No lock file. The directory listing IS the index.

## Writing a good handoff body

Self-contained. The claiming agent should never need to come back to you
(the author) for scope. Minimum elements:

1. **Context pointers** — which references/notes/decisions explain why.
2. **What to do** — numbered steps, with file paths.
3. **Constraints** — lane deny lists, avoided patterns, external blockers.
4. **Acceptance** — how the claimant knows they're done.
5. **When done** — literal CLI command to close (`gad handoffs complete <id>`).

If the body is over ~150 lines, the work probably deserves a proper phase
(`gad phases add`) and the handoff points at that phase instead. Handoff
bodies are transient; phase goals are canonical.

## Frontmatter fields

Set by `gad handoffs create`, readable in every listing:

| field | meaning |
|---|---|
| `id` | `h-<ISO-timestamp>-<projectid>-<phase>` (generated) |
| `projectid` | scoping — which planning root this touches |
| `phase` | phase id (string — supports decimals like `42.4`) |
| `task_id` | optional — existing TASK-REGISTRY task id this refines |
| `priority` | `low` / `normal` / `high` — only `high` should break other work |
| `estimated_context` | `mechanical` (Haiku-doable) / `reasoning` (Opus-worth) |
| `runtime_preference` | target lane — `claude-code` / `codex` / `cursor` / empty for any |
| `created_by` / `claimed_by` | runtime + agent id (auto-filled) |
| `created_at` / `claimed_at` / `completed_at` | ISO timestamps |

## Interaction with TASK-REGISTRY.xml

Handoffs are **intent**, tasks are **commitments**. Typical relationship:

- Task 63-02 sits in TASK-REGISTRY as the canonical commitment.
- One or more handoffs reference it via `task_id=63-02` to pass specific
  sub-work between lanes.
- When the handoff is closed, the task may also close (via
  `gad tasks release <id> --done`) if the handoff was the last piece.

Never put the handoff body content in TASK-REGISTRY goal — goals are
long-lived summaries, not action queues.

## Cross-lane protocol

If you need a file outside your lane (per `references/agent-lanes.md`),
**do not silently edit it**. File a handoff:

```sh
gad handoffs create \
  --projectid get-anything-done \
  --phase <N> --task-id <id> \
  --priority normal --context reasoning \
  --runtime-preference <owning-lane> \
  --body "$(cat <<'EOF'
# Short title

## Before you start
- Read `references/agent-lanes.md` — you are on the <owning-lane> lane.
- Relevant files: <paths>

## Implementation
1. ...
2. ...

## Acceptance
- ...

## When done
gad handoffs complete <this-id>
EOF
)"
```

Keep your own lane's work moving; the target lane drains the queue on
their next session.

## Common gotchas

| Symptom | Cause | Fix |
|---|---|---|
| Hook shows "Unclaimed handoffs" but count is garbled | Installed binary predates 60-09; text output bleeds into JSON parse | Upgrade when 44-38 ships |
| `gad handoffs list --json` prints help instead of `[]` | Same — stale binary | Same |
| Two agents both try to claim the same handoff | Race between `list` and `claim` | The second `claim` errors `ALREADY_CLAIMED` — no state corruption |
| Claimed handoff abandoned (agent dead) | No TTL enforcement today | Manually `fs.rename` back to `open/` or `gad handoffs list --claimed` and re-file |

## Resume protocol (session open / returning to a project)

This skill now owns the `resume-work` / `resume-project` methodology (folded
2026-04-22, tasks 63-35/63-39). On session open, any time a user says
"continue", "where were we", "resume", or the agent has just returned to a
project, run the resume protocol in this order.

### 1. Ingest canonical state

```sh
gad snapshot --projectid <id> --session <id>
```

The snapshot is the primary source of truth — STATE.xml, ROADMAP.xml,
TASK-REGISTRY.xml, open handoffs, and recent state-log entries are all
rolled into one call. Do not hand-read 10+ files; that's what snapshot
exists to prevent.

### 2. Drain the queue (assigned-work first)

```sh
gad handoffs list --mine-first --projectid <id>
```

If a handoff matches your runtime_preference, claim and execute it before
picking arbitrary roadmap work. This is the *work-stealing* half of the
queue. If nothing targets your runtime but unclaimed handoffs exist, you
may still claim them — priority > lane in the default picker.

```sh
gad handoffs claim <id>
gad handoffs show <id>   # read the body
# …do the work…
gad handoffs complete <id>
```

### 3. Incomplete-plan / interrupted-agent detection

Past-session artifacts that aren't handoffs still surface work-in-flight:

| Artifact | Meaning | Where to look |
|---|---|---|
| `PLAN.md` without matching `SUMMARY.md` | Phase execution started but not closed out | `ls .planning/phases/*/` and diff PLAN vs SUMMARY presence |
| `TASK-REGISTRY` entry with `status=in_progress` and no recent state-log activity | Task was claimed and abandoned | `gad tasks list --projectid <id> --status in_progress` |
| Subagent session file referencing a task that never closed | Interrupted subagent | inspect `.planning/sessions/` for `agent_id`, stale `last_activity` |

For each of these, prefer creating a handoff (`gad handoffs create`)
rather than silently resuming — the handoff is the audit trail and lets
another agent claim the pickup if you are the wrong runtime.

### 4. STATE.xml reconstruction (missing / corrupt state file)

Skip this step if `gad snapshot` returned a non-empty STATE section. If
STATE.xml is missing (fresh clone, accidental deletion, project predates
current schema), reconstruct by composing from sibling artifacts:

1. `PROJECT.md` (or `.planning/PROJECT.xml`) → "what this is" + core value
2. `ROADMAP.xml` → current phase position
3. `*-SUMMARY.md` across phases → recent decisions + concerns
4. `TASK-REGISTRY.xml` → open blockers, in-progress tasks
5. `.planning/handoffs/open/*.md` → anything unresolved
6. `.planning/.gad-log/*.jsonl` (last 7 days) → recent activity

Then:

```sh
gad state log "<one-line what-next>" --tags "<phase-id>" --projectid <id>
gad state log "state reconstructed from artifacts on <date>" --projectid <id>
```

Do NOT hand-write a long STATE.xml body. The immediate next move now comes
from the latest relevant state-log entry, then planned tasks, then the
active phase goal. Everything else belongs in the state-log entries or in
`.planning/notes/`.

### 5. Route to a concrete next action

Given the above inputs, route to ONE of:

| Condition | Next |
|---|---|
| Matching handoff claimed | Execute handoff body, then `gad handoffs complete` |
| Task-registry task in `in_progress` with your agent id | Continue the task; `gad tasks stamp` on finish |
| Incomplete PLAN with no SUMMARY | Resume the phase via `/gad-execute-phase <N>` or hand off if wrong lane |
| Phase ready to plan (CONTEXT.md present) | `/gad-plan-phase <N>` |
| Phase ready to discuss (no CONTEXT.md) | `/gad-discuss-phase <N>` |
| Nothing open and roadmap exhausted | Confirm milestone complete path, surface to user |

Each of these is *one concrete action*, not a menu. Pick the best-match
row and execute.

## Pause protocol (end of a work session)

Whenever you need to stop
mid-work and hand state to the next runner (same runtime next session,
different lane, or different runtime), file a handoff.

### 1. Commit what's committable

WIP commits beat lost shas. If there is uncommitted code, commit it first
(even as `wip:` prefix). The handoff body will reference the sha.

### 2. File the handoff

```sh
gad handoffs create \
  --projectid <id> \
  --phase <N> \
  --task-id <task-id-you-were-on> \
  --priority <low|normal|high> \
  --context <mechanical|reasoning> \
  --runtime-preference <next-runner's-lane-or-empty> \
  --body "$(cat <<'EOF'
# Short title — <what stopping point>

## Where I am
- Current phase, current task, current commit sha.
- What's done: <bullets>.
- What's half-done: <files modified but not committed, or half-written>.

## Where to pick up
1. `git status` — see uncommitted work (if any).
2. <next concrete step>.
3. <the test / verify command that confirms completion>.

## Blockers / open questions
- <anything paused on a decision needed>.

## When done
gad handoffs complete <this-handoff-id>
gad tasks release <task-id> --projectid <id> --done  # if this was the final piece
EOF
)"
```

### 3. Log the pause in state-log

```sh
gad state log "paused <task-id> at <stopping point> — handoff h-<id>" \
  --tags "<task-id>,paused" --projectid <id>
```

State-log is the append-only timeline; handoffs are the claimable queue.
Both are needed — the log tells the next agent *what happened*, the
handoff tells them *what to do*.

### Deprecation note — `.continue-here.md` is retired

The earlier `.continue-here.md` + `HANDOFF.json` dual-file pattern is
gone. Reasons:

- Single-slot queue: next pause overwrote the last one.
- Invisible to other runtimes — only the skill that wrote it knew where
  to look.
- No atomic claim; two agents could resume the same file and diverge.

`gad handoffs` solves all three: per-file directory, atomic
`fs.renameSync` through open/claimed/closed, visible via one CLI to every
runtime. If you encounter a legacy `.continue-here.md` or `HANDOFF.json`,
migrate its content into a `gad handoffs create` body and delete the old
file in the same commit.

## Related

- `references/agent-lanes.md` — which lane owns what, when cross-lane is OK
- `references/communication-style.md` — SITREP register for handoff bodies
- `.planning/notes/2026-04-18-handoff-queue-design.md` — original design doc
- `.planning/notes/2026-04-18-handoff-snapshot-integration.md` — pending snapshot surface
