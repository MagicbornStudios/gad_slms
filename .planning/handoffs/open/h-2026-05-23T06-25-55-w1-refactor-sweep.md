---
id: h-2026-05-23T06-25-55-w1-refactor-sweep
projectid: slm-learning
phase: 04
task_id: SL-T-04-w1-refactor-sweep
created_at: 2026-05-23T06:25:55.000Z
created_by: pathfinder-slm-learning-2026-05-23
priority: high
estimated_context: bounded
risk: safe
time: standard
surface: project-internal
runtime_preference: claude-code
soul: refactor
recipient: refactor-soul-or-next-claude-code-worker
depends_on:
  - h-2026-05-06T09-30-00-slm-learning-bridge
  - h-2026-05-06T10-00-00-workstream-d-per-domain-adapters
  - h-2026-05-09T02-12-53-slm-learning-gateway-wiring
  - h-2026-05-09T01-39-05-slm-learning-evolution-loop
---

# W1 — Orthogonal refactor sweep (Refactor-soul mandate, second-toucher rule)

From: Pathfinder scout pass 2026-05-23
For: Refactor soul (or any claude-code worker tagged to W1)

## Pathfinder scan output

Scope: 4 high-prio phase-04 open handoffs (gateway-wiring + bridge +
workstream-d-adapters + evolution-loop). Cheap grep-level scan,
no implementation read.

Three reuse-clusters surfaced. Each is a strict originator + second-toucher
pair already merged or in-progress. Refactor mandate is to lift the shared
shape and rewire — NO new features, NO speculative generality, NO comments
the call sites do not already imply.

### Cluster A — Trace/event envelope

| Side | Where |
|---|---|
| Originator | bridge handoff: `Unified envelope schema (v1)`, `.trace-events.jsonl` reasoning emission |
| Second-toucher | gateway-wiring: `schemas/inference_trace.schema.json` bump, `scripts/gateway/router.py` trace rows; workstream-d-adapters: `benchmark_run` envelope shape |
| Lift target | `scripts/_shared/envelope.py` — `wrap_envelope(content_type, payload, schema_v=1)` + `validate_envelope(obj)` (schema_v + sha256 + content shape) |
| Tests | `tests/_shared/test_envelope.py` — round-trip wrap+validate, schema_v mismatch rejection, sha256 mismatch rejection |

### Cluster B — Registry loader + lookup

| Side | Where |
|---|---|
| Originator | gateway-wiring: `data/registry/{teachers,model_families,datasets}.json` + `scripts/gateway/router.py` + `routes.json` loader |
| Second-toucher | workstream-d-adapters: per-domain LoRA adapter registry keyed by `(project, content_type)` |
| Lift target | `scripts/_shared/registry.py` — `load_registry(path, schema=None)` + `lookup(registry, **filters)`; schema-validated on load when schema arg supplied |
| Tests | `tests/_shared/test_registry.py` — load round-trip, lookup by single + multi filter, schema validation pass/fail |

### Cluster C — CLI wrapper + structured-stderr exit envelope

| Side | Where |
|---|---|
| Originator | gateway-wiring: `python -m scripts.gateway.cli --task-shape X --prompt Y` (CLI wrapper in `scripts/gateway/cli.py`) |
| Second-toucher | workstream-d-adapters D-3 (`train_adapter.py --cohort --base --out`) + D-4 (`benchmark_dispatch.py --adapter --cohort`) — both spec "exit 0 on success, non-zero with structured error JSON on stderr" |
| Lift target | `scripts/_shared/cli_runner.py` — `@cli_command` decorator handling argparse + try/except → structured `{error, traceback, exit_code}` JSON on stderr; success returns rich object printed as JSON on stdout |
| Tests | `tests/_shared/test_cli_runner.py` — success exit 0 + JSON stdout, failure exit nonzero + JSON stderr, unexpected exception captured as structured error |

## Non-clusters (Pathfinder explicitly NOT recommending refactor)

- **Modal MSYS prefix** (`MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8`) — it's a shell rule, not a code shape. Lives in CLAUDE.md + AGENTS.md already. No refactor needed.
- **`gad evolution evolve` invocation** — single-use per session, no second-toucher pattern.
- **Kael adapter training** (`scripts/16_*.py` / `17_*.py`) — bespoke educational track per CLAUDE.md, not for shared abstraction.

## Refactor soul mandate (two-pass commits, per soul law)

For each cluster A, B, C — execute in this order:

### Pass 1 — Extract (per cluster)

1. Create `scripts/_shared/<module>.py` with the lift target shape.
2. Create `tests/_shared/test_<module>.py` with the listed tests.
3. Run `pytest tests/_shared/test_<module>.py` — must pass before commit.
4. Commit: `refactor(_shared): extract <module> for cluster <A|B|C>`.

Both originator and second-toucher call sites STILL WORK at this stage
(extract is additive — adds module, no rewire yet).

### Pass 2 — Rewire (per cluster)

1. Replace originator's bespoke code with `from scripts._shared.<module> import ...`.
2. Replace second-toucher's bespoke code (or in-progress code in the open
   handoffs) with the same import. If second-toucher is still an open
   handoff (i.e. not yet implemented), update the open handoff body to
   reference the lifted module instead.
3. Run originator's existing tests AND second-toucher's tests (if any)
   — both must pass.
4. Commit: `refactor(_shared): rewire originator + second-toucher to <module> for cluster <A|B|C>`.

If rewire breaks tests: **roll back the rewire commit only** (extract
stays as dormant module), and append a `status: false-positive` entry to
`.planning/notes/2026-05-23-pathfinder-scan-w1.md` with the failing test
list. Hand the cluster back to the Pathfinder for heuristic refinement.

## Out-of-scope (DO NOT touch in W1)

- New features in router.py, training scripts, or adapter registry
- Schema bumps beyond what the extract requires (Cluster A schema is
  inference_trace.schema.json; bump only if validator needs it, not
  to "make it stricter")
- Renames not implied by the lift
- Cleanup of unrelated files (originator's other code stays bespoke
  until a second-toucher proves it)
- Documentation of the refactor outside the commit message + this
  handoff body

## Done criteria

- 3 `_shared/` modules exist with passing tests
- All 4 source handoffs (bridge, gateway-wiring, adapters, evolution-loop)
  have their reuse points rewired to the shared modules
- 6 commits land on master: 3 extract + 3 rewire, in cluster order A → B → C
- `gad state log "W1 refactor sweep complete: lifted envelope+registry+cli_runner; rewired 4 phase-04 handoffs"` fired
- This handoff moves to `.planning/handoffs/closed/`

## Hard rules carried forward (from prior handoffs)

- TRACE.json (NOT SCORE.md) is authoritative cross-project source (slm-learning-167)
- DO NOT commit files >5MB without explicit operator authorization
- DO NOT fire Modal CLI without `MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8` (Bash) or use PowerShell
- DO commit per direction batch (3 extract + 3 rewire = 2 direction batches)
- DO log decisions inline as work happens
- DO be autonomous when authorized — execute, don't return option menus
- DO end sessions with a handoff prompt per `docs/handoff_prompt_quality.md` >=12/16

## Next wave gate

W1 done → W2 fires (Pathfinder deep scan with subagent + Dr. Stein
experiment assignment per cluster). Do NOT trigger W2 from inside W1 —
the council law requires sequential wave commits to land before the
next wave's scout pass.
