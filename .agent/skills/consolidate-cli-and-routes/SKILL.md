---
name: consolidate-cli-and-routes
description: >-
  Rename a CLI command family while trimming the public route map and
  building the absorbing route in one phase. Inventory both surfaces
  first, land new + alias old, delete dead routes + collapse content,
  fix fallout, audit submodules. Use when a CLI rename and a route trim
  belong together; phase 46 collapsed `gad workspace` → `gad projects`,
  cut nav 20+ → 9, and absorbed glossary/formulas/standards into
  /how-it-works in 11 tasks.
status: stable
workflow: workflows/consolidate-cli-and-routes.md
---

# consolidate-cli-and-routes

CLI rename + route trim is one phase, not two. Doing them separately
leaves the operator-facing surface inconsistent for one cycle and forces
the same set of fix-the-fallout commits twice. Phase 46 made the case:
inventory both, land new + alias old, delete dead, build the absorbing
route, fix imports, audit submodules.

This skill is the assembly recipe. The route-move half (single route
moved with a deprecation stub) is a separate skill,
`move-route-with-deprecation-stub`.

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/phase-46-site-architecture-redesign-cli-consolida/CANDIDATE.md`
- Drafted: 2026-04-28 by `create-proto-skill`
- See [PROVENANCE.md](./PROVENANCE.md)
