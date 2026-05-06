# Repository Memory

## Status

`research-line`

## Owned by

Dr. Stein (research designer) + Archivist (memory ownership)

## Definition

A coding agent that remembers the history of the repo it's working in
makes better decisions than one that treats every task as fresh. This
concern tracks the research line — Microsoft's repository-memory work
+ SERA-style repo-specialized trajectories — and adapts both to GAD's
richer artifact set.

## Inspirations

| Source | Claim | Relevance to GAD |
|---|---|---|
| Microsoft, repository memory for coding agents | code-localization improves on SWE-bench-Verified when agents have memory of "modules change often / files fix which bug types" | Validates memory-as-context-engineering. We extend with phases / decisions / souls / skeletons. |
| SERA (open coding-agent line) | repository-specialized synthetic trajectories + soft verification, **26x cheaper than RL, 57x cheaper than earlier synthetic methods**, comparable performance | Our monorepo gives us trajectory seeds for free via tasks/handoffs/decisions. |
| Microsoft ExACT / Reflective MCTS | test-time search via worktree exploration → improvement on VisualWebArena and OSWorld | We already use worktrees in single sessions; multi-candidate verdict is the leap. |

These three together are **research validation of what GAD is already
trying to do**. The mission of this concern is to extend them, not
just reproduce them.

## What GAD memory looks like (extended)

Microsoft talks about repo memory. GAD's monorepo gives us four
intersecting memory types:

1. **Repository memory** — git commits, branches, deleted files,
   dependency graph, tmp/skeletons, test outcomes
2. **Project memory** — `.planning/{tasks,phases,decisions,notes,
   concerns}` + `STATE.xml` + handoff queue
3. **Agent memory** — `.planning/.trace-events.jsonl` per-agent
   trajectories, runtime outcomes, accepted/rejected outputs
4. **Evolution memory** — `experiments/runs/*/manifest.json` +
   eval results + adapter checkpoints + promotion verdicts

A repo-memory query for "how do we fix bug X in module Y" should be
able to consult all four memory types and return a context pack:
prior decisions touching Y, prior commits that fixed similar bugs,
prior agent trajectories that worked or failed, prior eval scores
relevant to the area.

## Memory entities (GAD-extended)

| Entity | Already exists at | Memory role |
|---|---|---|
| file | filesystem + git history | "what touched this and when" |
| module / package | dependency graph | "what depends on / is depended on" |
| task | `.planning/tasks/<id>.json` | "this work was planned, why" |
| phase | `.planning/phases/PHASE-NN-*.md` + ROADMAP.xml | "this batch of work, its goals" |
| decision | `.planning/DECISIONS.xml` | "why we chose this over alternatives" |
| commit | git | "the actual change + message" |
| branch / worktree | git | "parallel exploration spaces" |
| skeleton | `tmp/museum/` + `tmp/zoo/` (planned) | "what died and why" |
| agent | `.gad/agents/` | "tool usage shape" |
| skill | `.gad/skills/` (or framework) | "reusable methodology" |
| runtime | `scripts/runtime/check.py` outputs | "which CLI shell at what time" |
| model | `experiments/runs/*/manifest.json` | "which adapter, what it scored" |
| eval | `experiments/runs/*/eval/*.json` | "what we measured" |
| failure | error logs + state-log entries with "FALSIFIED" / "FAILED" | "what we tried that didn't work" |

Edges between them are the queryable graph.

## Implementation phases (proposed)

| Phase | Goal | Cost |
|---|---|---|
| **A — Index** | walk all four memory types, emit a unified entity-edge JSONL | 1 week |
| **B — Retrieval API** | `gad memory query <task>` returns top-N relevant entities + edges | 1 week |
| **C — Snapshot integration** | `gad snapshot --memory` injects retrieved context | 1 day |
| **D — Trajectory generation (SERA-style)** | for each closed phase, derive (task, before-repo, after-repo) → SFT pairs | 2 weeks |
| **E — Soft verification** | score each trajectory by patch similarity / line recall / schema validity / test cheap-pass / human accept | 1 week |
| **F — Repo-specialized model train** | use the trajectory + soft-verify pipeline to train a 7B coder specialized to GAD monorepo | 3 weeks |
| **G — Eval against bare frontier** | A/B/C suite (bare Opus / GAD-orchestrated frontier / GAD-specialist) on SWE-bench Verified slice | 1 week |

A → C is groundwork. D → F is SERA-inspired training. G is the
publishable measurement.

## Why this is publishable

Per `slm-learning-074` (research-paper goal), the GAD extension of
Microsoft + SERA has a real claim:

> Repository memory + soul-aligned council pattern + candidate-only
> continuous delta training produces a repo-specialized SLM that
> matches GAD-orchestrated frontier on bounded shape X at <Y% of cost.

That claim is testable, defensible, and not the kind of overclaim
slm-learning-070 / 071 prohibit. Evidence tier targetable: T2 (multi-run
with baseline) on first paper, T3 (versus published baseline at scale)
on follow-up.

## Pushback / risk register

- **Memory bloat.** A repo with N years of history will have a huge
  graph. Need a relevance-decay model and a top-K retrieval cap.
- **Stale memory.** A memory entry from 6 months ago about a
  now-removed module is worse than no memory. Skeleton-status flag
  must propagate into retrieval scoring (skeleton state pulls
  relevance to ~0).
- **Privacy / secrets.** Memory mining will surface secrets if the
  redactor isn't comprehensive. We have one (per
  `scripts/ingest_gad_telemetry.py`), needs to be applied at memory
  index time too.
- **Reproducibility.** SERA-style synthetic trajectories must be
  re-runnable from a snapshot of the repo at training time, not just
  the live tree. Trajectory generator must record the commit it ran
  against.

## Pending decisions

| ID | Question | Status |
|---|---|---|
| slm-learning-073 | Adopt repository memory as a research line + GAD artifact | proposed in this commit |
| slm-learning-074 | Research paper as project output goal — codify | proposed in this commit |

## References

- forwarded research summary 2026-05-06 (chat): Microsoft repo memory,
  SERA, ExACT
- decisions `slm-learning-051` (Continuous Local Delta Lab),
  `slm-learning-070` (realistic ceiling), `slm-learning-071`
  (evidence-tiered policy)
- concern `.planning/concerns/codebase-attention.md` — same kind of
  memory mining, narrower (per-file)
- concern `.planning/concerns/skeleton-system.md` — fossils ARE memory
- soul `narrative/souls/archivist.md` — owns memory artifacts
