---
name: move-route-with-deprecation-stub
description: >-
  Move a route or small route family between apps in a monorepo,
  rewriting imports + AppShell nav + cross-link CTAs, leaving a
  server-rendered deprecation stub at the old location with install +
  run CLI snippet, and threading an env-driven URL helper
  (`NEXT_PUBLIC_*_URL`) through every cross-app link. Use when a route
  is moving hosts and inbound traffic needs a soft landing.
status: stable
workflow: workflows/move-route-with-deprecation-stub.md
---

# move-route-with-deprecation-stub

Route moves between apps require more than `git mv`. Inbound traffic
hits the old URL via bookmarks and internal cross-links; without a
deprecation stub the operator-facing experience is "the route 404s".
Phase 70 captured the canonical move shape: file move + import rewrite,
deprecation stub, env-driven URL helper.

This skill is the three-step checklist for any route move in a multi-app
monorepo.

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/phase-70-marketplace-move-vendor-project-market-a/CANDIDATE.md`
- Drafted: 2026-04-28 by `create-proto-skill`
- See [PROVENANCE.md](./PROVENANCE.md)
