---
name: verify-clean-clone-site-build
description: >-
  Catch missing-from-git imports before they break a Vercel-style clean-clone
  build. Phase 28 lost a production build because /project-market refactor
  added imports for files that existed on disk but were never `git add`ed.
  Use after multi-file site refactors, before merging branches that touch
  cross-package imports, or whenever a deploy target does a fresh clone
  per build.
status: stable
workflow: workflows/verify-clean-clone-site-build.md
---

# verify-clean-clone-site-build

The deploy target only sees what's in `git ls-files`. Local dev can mask
missing-from-index files because the working tree is permissive. This
skill is the audit step that runs before the merge — simulate the clean
clone, run the production build, fail loud on the local side.

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/phase-28-project-market-site-architecture-overhau/CANDIDATE.md`
- Drafted: 2026-04-28 by `create-proto-skill`
- See [PROVENANCE.md](./PROVENANCE.md)
