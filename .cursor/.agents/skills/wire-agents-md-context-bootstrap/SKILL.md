---
name: wire-agents-md-context-bootstrap
description: >-
  Standardize the per-project entry contract (AGENTS.md / .cursor/rules/ beside
  `.planning/`) so every coding agent — claude-code, codex, cursor,
  subagent — opens with a working projectid + canonical CLI surface +
  lane discipline. Use when adding a new project root, after a CLI
  rename, or when an agent reports stale entry instructions.
status: stable
workflow: workflows/wire-agents-md-context-bootstrap.md
---

# wire-agents-md-context-bootstrap

The entry contract (AGENTS.md / .cursor/rules/ beside a `.planning/` dir) is
the first file every cold agent reads. Phase 11 found that drift between
that file and the live `gad` CLI surface costs ~5-10% of every session
on archaeology before the first real tool call. This skill is the audit
+ patch loop that keeps the entry contract honest.

The skill targets multi-root monorepos where every root needs a
projectid, a canonical CLI surface, and (when multi-agent) a lane map.
For single-root projects, the steps still apply — the lane map collapses
to one paragraph.

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/phase-11-agents-md-and-context-system/CANDIDATE.md`
- Drafted: 2026-04-28 by `create-proto-skill`
- See [PROVENANCE.md](./PROVENANCE.md)
