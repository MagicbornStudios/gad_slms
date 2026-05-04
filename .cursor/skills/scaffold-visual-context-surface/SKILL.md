---
name: scaffold-visual-context-surface
description: >-
  Scaffold a new dev-only UI surface (editor, inspector, admin pane,
  modal stack) under the Visual Context System mandate. Triggers on
  "scaffold a new editor", "build a gated dev route", "add a Project
  Editor pane", "new admin surface", or any task whose acceptance
  requires `SiteSection cid="..."` literals, Visual Context Panel
  registration, and a modal-footer CRUD round-trip before feature work
  starts. Enforces the six-step scaffolding-first checklist: dev gate
  first, then enumerate panes and cids, emit literals, register
  identities, round-trip one prompt, only then build features. Prevents
  the retrofit tax of adding Visual Context coverage after features
  already exist. See decisions gad-186 + gad-187 and the 2026-04-15
  Visual Context mandatory feedback for the source constraints.
lane: dev
type: system-requirements
status: stable
workflow: workflows/scaffold-visual-context-surface.md
---

# scaffold-visual-context-surface

Scaffolding-first discipline for new dev-only UI surfaces. Every new
editor pane, admin route, or inspector modal in this repo must ship with
complete Visual Context coverage before any feature affordance is built
— stable literal cids on every interactive element, Visual Context Panel
identities registered, and at least one modal-footer CRUD round-trip
green against a real cid.

This proto-skill captures the checklist as a reusable pattern so future
gated-editor work does not re-derive it from scratch or ship drift.

**Workflow:** Inline in this SKILL.md (six-step checklist described in the
"When this fires" / "When NOT to use this" sections below). The parent skill
`gad-visual-context-system` has the full methodology at
`workflows/visual-context-system.md`.

## When this fires

- Task acceptance mentions `SiteSection cid` or Visual Context Panel
- Building a new `/<surface>` route behind a dev-mode gate
- Adding an editor, inspector, admin console, or modal stack
- Cleanup pass on a surface that skipped the mandate ("retrofit")

## When NOT to use this

- You're adding a single element to an already-compliant surface — use
  `gad-visual-context-panel-identities` directly.
- You're building a production-facing page (no dev gate) — the gate is
  part of this skill's contract; different rules apply.
- You're refactoring internals with no visible surface change.

## Provenance

Drafted by `create-proto-skill` from
`.planning/candidates/phase-44.5-project-editor-brood-editor-local-dev-ga/CANDIDATE.md`
on 2026-04-15 as the first end-to-end run of the evolution pipeline
(task 42.2-13). Selection pressure: 29 (phase 44.5, 15 tasks, 7
crosscuts). See PROVENANCE.md for source metadata and reasoning about
what the skill abstracts.

## Related

- `gad-visual-context-panel-identities` — identity registration mechanics
- Decisions gad-186, gad-187, gad-189, gad-191
- Feedback memory `feedback_visual_context_system_mandatory.md`
