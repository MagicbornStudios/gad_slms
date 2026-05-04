---
name: wire-skill-provenance-tracking
description: >-
  Capture start/end skill snapshots around a generation run so site UI
  can show installed (blue) / inherited (green) / authored (amber) /
  framework (violet) badges per run. Phase 31 introduced the diff
  pipeline + frontmatter flag (`framework_skill: true`) + badge palette
  in decision gad-31. Use when wiring a new eval/generation system,
  extending the badge taxonomy, or adding a skill-source classification.
status: stable
workflow: workflows/wire-skill-provenance-tracking.md
---

# wire-skill-provenance-tracking

A generation that ships with N skills tells the operator nothing about
whether those skills were inherited, installed, or authored during the
run. This skill is the diff + classify + badge pipeline that turns
opaque skill catalogs into traceable provenance trails.

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/phase-31-skill-ecosystem-provenance-creation-work/CANDIDATE.md`
- Drafted: 2026-04-28 by `create-proto-skill`
- See [PROVENANCE.md](./PROVENANCE.md)
