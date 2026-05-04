---
name: monorepo-rename-and-relocate
description: >-
  Rename a workspace package and/or relocate an app directory atomically
  across a monorepo: inventory all package-name + path refs, `git mv`,
  update package.json, sweep references, update root scripts, optionally
  merge marketing surfaces from one app into another. Use when a
  workspace package or app directory needs reorgs, especially when the
  reorg crosses package boundaries (e.g. `apps/<x>` → `apps/species/<x>`).
status: stable
workflow: workflows/monorepo-rename-and-relocate.md
---

# monorepo-rename-and-relocate

Workspace renames are mechanical but the surface is wide — package.json,
cross-package imports, vendor refs, root scripts, turbo/pnpm config, dev
ports, doc references. Phase 68 shipped three such reorgs in one phase
by inventorying refs first, doing atomic moves, sweeping with grep +
sed, and verifying with typecheck + build.

This skill is the checklist that keeps the rename atomic.

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/phase-68-monorepo-reorg-rename-planning-app-platf/CANDIDATE.md`
- Drafted: 2026-04-28 by `create-proto-skill`
- See [PROVENANCE.md](./PROVENANCE.md)
