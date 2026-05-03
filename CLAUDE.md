# slm_learning Agent Contract

This file mirrors `AGENTS.md` for runtimes that read `CLAUDE.md`.
If the two files diverge, regenerate the mirror from the `AGENTS.md` source.

Project name: `slm_learning`
Project id: `slm_learning`

## Soul pointer

Read `SOUL.md` first, then read the active soul body at
`narrative/souls/speech-native-builder.md`. This project values
terminal-native speech capture, visible device/listening state, live transcript
output, and honest constraints.

## Loop

Use this loop every session:

1. `gad snapshot --projectid slm_learning`
2. Pick one task
3. Implement the task
4. `gad tasks stamp <task-id> --projectid slm_learning --status done --agent <agent> --runtime <runtime>`
5. `gad state log "<delta>" --projectid slm_learning`
6. Commit

## Planning IDs

Use canonical IDs exactly:

| Entity | Format |
|---|---|
| decisions | `SLM_LEARNING-D-<n>` |
| tasks | `SLM_LEARNING-T-<phase>-<n>` |
| handoffs | `h-<ISO>-slm_learning-<phase>` |
| requirements | `SLM_LEARNING-R-<n>` |
| errors | `SLM_LEARNING-E-<n>` |

## Communication style

- SITREP format.
- Tables when structure helps.
- Report deltas only.
- Always close with gaps.
- Call entities by registered name, not shorthand.

## GAD CLI quick reference

| Command | Purpose |
|---|---|
| `gad snapshot --projectid slm_learning` | Hydrate planning context before work |
| `gad tasks list --projectid slm_learning` | Inspect available work |
| `gad tasks stamp <task-id> --projectid slm_learning --status done --agent <agent> --runtime <runtime>` | Stamp task completion |
| `gad state log "<delta>" --projectid slm_learning` | Append a state-log entry |
| `gad decisions add SLM_LEARNING-D-<n> --projectid slm_learning --summary "..."` | Record a decision |
| `gad handoffs list --projectid slm_learning` | Inspect open handoffs |
| `gad handoffs claim <handoff-id>` | Claim a handoff |
| `gad handoffs complete <handoff-id> --by <runtime>` | Close a handoff |

## Lane discipline

Single-agent by default. Use multi-agent execution only when `gad team`
is active and the work has been explicitly split into lanes.

## Files

- `AGENTS.md` is the source contract.
- `CLAUDE.md` is the runtime mirror.
- `.planning/AGENTS.md` narrows the rules for planning-only edits.
