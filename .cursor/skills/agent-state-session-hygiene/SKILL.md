---
name: agent-state-session-hygiene
description: >-
  Inventory every shared-write path under `.planning/` + `.gad/` + user
  config and classify each into one of four contention patterns:
  contested aggregate (CLI-mediated), shared append-only (JSONL),
  contested single-owner (per-record dir), cross-agent intent (per-file
  dir + fs.rename). Author the lane manifest, the state-writes
  inventory, and the user-settings scaffold; wire session continuity
  + daily-tip + soul. Use when adding a new shared state surface, when
  multi-agent races produce data loss, or when subagent attribution
  holes appear.
status: stable
workflow: workflows/agent-state-session-hygiene.md
---

# agent-state-session-hygiene

When the working tree hosts more than one agent runtime, every shared
write is a race and every contested aggregate field is a corruption
risk. Phase 63 (highest-pressure candidate of the cohort at 219, 55
tasks) inventoried the surface, classified each write into one of four
patterns, and built the canonical fixes — handoff queue with fs.rename
lifecycle, per-task JSON files, JSONL append-only logs, CLI-mediated
state mutations.

This skill is the audit + classify + repair recipe. It is the most
load-bearing of the cohort because every multi-agent surface eventually
re-encounters the same contention classes.

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/phase-63-agent-state-session-hygiene/CANDIDATE.md`
- Drafted: 2026-04-28 by `create-proto-skill`
- See [PROVENANCE.md](./PROVENANCE.md)
