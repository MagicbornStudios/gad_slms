---
name: gad-generation-spawn
description: >-
  Kick off a GAD generation spawn from inside a Cursor session by wrapping
  `gad generation spawn --execute` to get the JSON spec, then spawning a
  worktree-isolated subagent against that spec. This skill is the seam between
  the orchestrating session (plan/review) and the spawned builder session
  (execute) per decision forge-09. Use when the user asks to "spawn a generation",
  "kick off a generation run", or invokes /gad-generation-spawn. The skill writes
  a session marker under `.planning/.generation-runs/<run-id>.json` so the
  orchestrator can poll status and preserve outputs via `gad generation preserve`
  after the builder session completes.
lane: dev
type: command-wrapper
argument-hint: <species> [--runtime claude-code] [--baseline HEAD]
allowed-tools:
  - Read
  - Write
  - Bash
  - Agent
workflow: workflows/generation-spawn.md
---

<objective>
Spawn a generation in a worktree-isolated subagent. This skill is the plan/build
seam (decision forge-09): the orchestrating session plans and reviews, the
spawned session builds. The orchestrator stays in charge of preservation —
after the builder finishes, this skill preserves outputs via
`gad generation preserve` and marks the session complete.
</objective>

<process>

Parse from `{{GAD_ARGS}}`:
- `<species>` (required, positional) — species name (the character build being spawned)
- `--runtime <id>` (optional, default `claude-code`) — runtime driving the spawned agent
- `--baseline <sha>` (optional, default `HEAD`) — git baseline the worktree branches from (brownfield parents use the preserved spawn SHA here)

1. **Resolve the species:**
   ```bash
   gad species list | grep -E "^\s*$SPECIES\b" || { echo "Species '$SPECIES' not found. Run 'gad species list' to see available species."; exit 1; }
   ```
   (`gad species list` is multi-root aware as of task 42.4-12; if that work has not yet landed the default root `vendor/get-anything-done/species/` is still used.)

2. **Generate the exec spec:**
   ```bash
   gad generation spawn --species "$SPECIES" --runtime "$RUNTIME" --baseline "$BASELINE" --execute
   ```
   This writes `generations/<species>/v<N>/EXEC.json` and also prints the JSON
   between `--- EXEC_JSON_START ---` / `--- EXEC_JSON_END ---` markers on stdout.
   Parse the JSON and capture: `species`, `version`, `runDir`, `prompt`,
   `promptFile`, `envVars`, `postSteps`. The `runId` for session-marker purposes
   is `<species>-<version>` (e.g. `escape-the-dungeon-v7`).

3. **Check for a stale session marker:**
   ```bash
   MARKER=".planning/.generation-runs/${SPECIES}-${VERSION}.json"
   if [ -f "$MARKER" ]; then
     echo "Run id $SPECIES-$VERSION already has a marker at $MARKER. Refusing to overwrite. Inspect, resolve, then delete the marker to retry."
     exit 1
   fi
   mkdir -p .planning/.generation-runs
   ```

4. **Create an isolated worktree:**
   ```bash
   WORKTREE_PATH=".claude/worktrees/agent-${SPECIES}-${VERSION}"
   git worktree add "$WORKTREE_PATH" "$BASELINE"
   ```
   Prefer `.claude/worktrees/agent-*` (already managed by `gad worktree list/clean`)
   over `mktemp` so the orchestrator can find the worktree later even across
   session boundaries.

5. **Write the session marker (status: running):**
   ```json
   {
     "runId": "escape-the-dungeon-v7",
     "species": "escape-the-dungeon",
     "version": "v7",
     "generation": 7,
     "runtime": "claude-code",
     "baseline": "HEAD",
     "worktreePath": ".claude/worktrees/agent-escape-the-dungeon-v7",
     "runDir": "vendor/get-anything-done/generations/escape-the-dungeon/v7",
     "agentId": null,
     "startedAt": "2026-04-14T18:00:00Z",
     "status": "running"
   }
   ```
   Write this to `.planning/.generation-runs/<runId>.json`. `version` (e.g. `v7`)
   is the authoritative version field; `generation` is the numeric suffix for
   convenience.

6. **Spawn the builder subagent via the Agent tool:**
   Launch with:
   - `subagent_type: "general-purpose"` (or a runtime-specific type once they exist)
   - `isolation: "worktree"`
   - `cwd: <WORKTREE_PATH>`
   - `description: <agentDescription from EXEC.json>`
   - `prompt: <prompt from EXEC.json>` — already contains all GAD context,
     trace env vars, and post-steps. Do not rewrap it.
   - `env: <envVars from EXEC.json>` — `GAD_RUNTIME`, `GAD_GENERATION_TRACE_DIR`,
     `GAD_LOG_DIR`, `GAD_SPECIES`, `GAD_GENERATION_VERSION`

   When the Agent call returns, capture the agent's final message / exit status
   and the token usage, then update the marker: set `agentId`, `endedAt`,
   `status: "agent-complete"`.

7. **Preserve outputs (mandatory, decision gad-38):**
   ```bash
   gad generation preserve "$SPECIES" "$VERSION" --from "$WORKTREE_PATH"
   ```
   On success, update the marker: `status: "preserved"`, `preservedAt: <ts>`.
   On failure, leave the marker at `agent-complete` and report the error —
   do NOT clean up the worktree, the user may need to inspect it.

8. **Clean up the worktree:**
   ```bash
   gad worktree clean "agent-${SPECIES}-${VERSION}"
   ```
   Update the marker one last time: `status: "cleaned"`, `cleanedAt: <ts>`.

9. **Report:**
   ```
   Spawned generation
     Species:    $SPECIES
     Version:    $VERSION
     Runtime:    $RUNTIME
     Baseline:   $BASELINE
     Worktree:   $WORKTREE_PATH
     Run dir:    $RUN_DIR
     Marker:     .planning/.generation-runs/$SPECIES-$VERSION.json
     Status:     preserved + cleaned
   ```

</process>

<failure_modes>
- **Spawn fails before the agent starts** — remove the session marker and
  `git worktree remove --force` the worktree. The `EXEC.json` and run dir stay
  in place; re-invoking `/gad-generation-spawn` will re-use the same `runId`,
  so you must either delete the existing `generations/<species>/v<N>/` or
  accept that the rerun will bump to `v<N+1>`.
- **Agent crashes mid-run** — mark the session `status: "agent-failed"`, leave
  the worktree in place for forensics, and surface the error to the user. Do
  NOT preserve — partial spawns pollute canonical paths.
- **Preserve fails** — mark `status: "preserve-failed"`, leave worktree intact,
  instruct the user to run `gad generation preserve` manually once they've
  fixed whatever the copy failure was.
- **Marker already exists** — refuse. A live run at the same `runId` means
  either a previous session is still going or a previous session crashed
  without cleanup. Let the user resolve manually.
- **`--execute` flag missing** — this skill depends on
  `gad generation spawn --execute` (already shipped). If the CLI doesn't
  recognize the flag, stop and tell the user to upgrade their GAD CLI rather
  than falling back to manual worktree plumbing.
</failure_modes>

<examples>
User: "Spawn a generation for escape-the-dungeon."
Agent: invokes `/gad-generation-spawn escape-the-dungeon` — generates EXEC.json
at `generations/escape-the-dungeon/v7/EXEC.json`, creates worktree at
`.claude/worktrees/agent-escape-the-dungeon-v7`, writes marker at
`.planning/.generation-runs/escape-the-dungeon-v7.json`, spawns builder subagent
with the prompt from EXEC.json, on completion runs
`gad generation preserve escape-the-dungeon v7 --from .claude/worktrees/agent-escape-the-dungeon-v7`,
cleans the worktree, updates marker to `status: "cleaned"`.

User: "Kick off a brownfield run from the v6 spawn SHA."
Agent: `/gad-generation-spawn escape-the-dungeon --baseline <sha-of-v6-spawn>` —
same flow, worktree branches off the preserved v6 spawn.
</examples>

<rules>
- Always write the session marker BEFORE spawning the agent — if the agent call
  fails, the marker lets the orchestrator recover.
- Never skip `gad generation preserve` (decision gad-38). Preservation failures
  must stop cleanup.
- Never clean the worktree on failure paths — the operator needs it for forensics.
- Never wrap or rewrite the prompt from EXEC.json. It's already fully hydrated
  with GAD context, trace hooks, and post-steps.
- Do not set `GAD_RUNTIME` or trace env vars manually — use the values from
  `EXEC.json.envVars` so the CLI stays the single source of truth.
- `.planning/.generation-runs/` is transient runtime state. Do not commit markers.
</rules>

<related>
- `gad-generation-run` — generates the prompt and (without `--execute`) creates
  the worktree itself; this skill is the `--execute`-mode counterpart.
- `gad-eval-bootstrap` — older bootstrap flow that injects context without
  spawning.
- decision forge-09 — plan/build separation; this skill is the documented seam.
- decision gad-38 — generation preservation contract.
- decision gad-212 — eval vocabulary replaced by species/generation.
- decision gad-219 — `gad spawn` verb replaces `gad eval run`.
</related>
