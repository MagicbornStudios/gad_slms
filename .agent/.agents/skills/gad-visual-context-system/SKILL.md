---
name: gad-visual-context-system
description: >-
  Build and maintain a UX pattern for visual-context identity in any app where a coding
  agent needs to act on "the thing I'm pointing at". The skill has two workflows —
  one for bringing the system into a project that doesn't have it yet (design/spec),
  and one for enforcing/extending the system in a project that already has it
  (maintenance/rollout). Use when a user says "I can't find the component I'm
  looking at", "we need a dev panel", "hook up the visual context system in
  <new app/game>", or "normalize the ids across <existing app>".
lane: dev
type: system-requirements
source_phase: "44"
source_evolution: 2026-04-14-001
status: stable
canonicalized: 2026-04-15
canonicalization_rationale: >-
  Framework staple — every UI-based consumer project is expected to start with
  this methodology. Bare minimum requirement: app-wide visual-context
  coverage, a dev-only searchable id surface with explicit show/hide
  control, and performance-minded behavior when tooling is disabled.
  Canonicalized via `gad skill promote-folder` metadata
  flip per decision gad-196 (task 42.2-32). Parent skill
  gad-visual-context-panel-identities remains available as the lower-level
  component-id methodology.
parent_skill: gad-visual-context-panel-identities
workflow: workflows/visual-context-system.md
---


# gad-visual-context-system

**Workflow:** [workflows/visual-context-system.md](../../workflows/visual-context-system.md)

Run the workflow. All procedural detail, examples, and tool sequencing live in the workflow file per the canonical skill shape (references/skill-shape.md, decision gad-190).
