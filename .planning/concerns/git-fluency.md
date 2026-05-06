# Git Fluency

## Status

`pending-decisions`

## Owned by

Dr. Stein (capability owner) + Executor (consumer)

## Definition

Coding agents — both frontier runtimes and our own SLMs — need to be
fluent in git as a tool, not just as a substrate they happen to be
running on top of. Git fluency is treated here as a first-class
capability target with a measurable rubric.

This is also the substrate for the skeleton system: git is the fossil
record. An agent that cannot read git history cannot mine fossils.

## Capability checklist

| Capability | Why it matters |
|---|---|
| commit (small, atomic, well-messaged) | reversibility + readable history |
| branch / worktree | parallel work, isolation |
| rebase (interactive, fixup) | clean history |
| blame / log mining | reading the fossil record |
| bisect | locating a regression |
| stash + index manipulation | mid-task interruptions |
| submodule (or absence policy) | monorepo navigation |
| reflog | crash recovery |
| diff (workdir / index / commits / merges) | situational awareness |
| merge conflict resolution | not destructive over the conflict |
| safe-default discipline | no `--force`, no `reset --hard`, no `--no-verify` without authorization |

## Training data candidates

- our own GAD git operations (every `git` command we run is a trace)
- monorepo git history at large (every commit is a paired
  before/after)
- failed PR / failed merge histories (skeleton-mining)
- commit messages that explain "why" — preferred over "what" — for
  preference-pair data

## Where this lives (pending D9)

| Option | Pros | Cons |
|---|---|---|
| Own SLM specialist (`gad-git-fluent` adapter) | cleanly evaluable, sharp | one more model to maintain |
| Sub-skill of the tool-use coder (decision `slm-learning-034`) | already on roadmap, cheap | risks dilution if tool-use coder gets too broad |
| Both: sub-skill first, graduate to specialist if eval pressure justifies | adapter-ladder discipline | more decisions later |

## Provisional rubric

A "git-fluent" output is one that:

- proposes the smallest correct commit, not the largest
- writes a commit message that explains *why* and references
  IDs (decision / task / issue)
- never proposes a destructive op without an authorization clause
- correctly answers "what did this code look like before commit X"
- correctly answers "which commit introduced this regression"
- preserves user uncommitted work when given a destructive request
- distinguishes staged / unstaged / untracked / committed

## Pending decisions

| ID | Question |
|---|---|
| D9 | Own specialist, sub-skill of tool-use coder, or both (ladder)? |

## References

- decision `slm-learning-034` — tool-use Tier 1 model
- decision `slm-learning-032` — promotion gate (a git-fluency adapter
  must pass it before being baked)
- `.planning/concerns/skeleton-system.md` — git is the fossil substrate
