---
name: scaffold-clerk-operator-attribution
description: >-
  Wire Clerk auth + solo-operator fallback + subagent env stamping + CLI
  parity into a Next.js platform app so every publish/edit action ties
  to a human operator regardless of the surface (UI click, agent CLI,
  headless script). One canonical `getOperatorId()` resolver, MANIFEST
  attribution, `via: ui|cli` distinction, hot-rebuild of marketplace
  index. Use when adding Clerk to a new platform app or when subagent
  attribution is breaking the audit trail.
status: stable
workflow: workflows/scaffold-clerk-operator-attribution.md
---

# scaffold-clerk-operator-attribution

Operator attribution has to thread three surfaces consistently: UI
clicks, subagent CLI calls, and headless scripts. Phase 51 found that
half-wiring (Clerk on the UI but no env stamping on subagent spawn)
produces an audit log where everything looks like the agent runtime
did the work, hiding the human intent.

This skill is the canonical wire-it-end-to-end recipe — one resolver,
one env contract, one manifest field, one CLI parity command.

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/phase-51-apps-platform-scaffold-clerk-supabase-da/CANDIDATE.md`
- Drafted: 2026-04-28 by `create-proto-skill`
- See [PROVENANCE.md](./PROVENANCE.md)
