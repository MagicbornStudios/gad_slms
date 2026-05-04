---
name: tui-track-slice-coordination
description: >-
  Coordinate a multi-track TUI build (7 tracks, 27+ specs) across
  parallel agents using the slice-by-track model: one agent owns one
  slice end-to-end, slice-level commits reference spec ids, cross-lane
  handoff protocol uses closeout-type frontmatter, self-resume handoff
  carries body schema (task_id, phase, last_commit, what's done /
  left / blocked). Use for TUI sprints with parallel agents or any
  multi-track sprint where coordination overhead would otherwise
  dominate.
status: stable
workflow: workflows/tui-track-slice-coordination.md
---

# tui-track-slice-coordination

Phase 65's 27-spec TUI sprint shipped via slice-based parallelization —
each agent owned one track end-to-end, slices were independent enough
to ship out of order, and cross-lane handoffs used the canonical
handoff queue with closeout type. This skill captures the requirements
doc shape, the slice contract, the cross-lane protocol, and the
liveness-inference + shell-profile + self-resume primitives that made
multi-agent dispatch tractable.

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/phase-65-2026-04-19-multi-agent-sprint-27-item-tu/CANDIDATE.md`
- Drafted: 2026-04-28 by `create-proto-skill`
- See [PROVENANCE.md](./PROVENANCE.md)
