---
candidate_slug: phase-44.5-project-editor-brood-editor-local-dev-ga
source_phase: "44.5"
source_phase_title: "Project Editor + Brood Editor — local-dev gamified species/brood/generation workspace"
pressure_score: 29
tasks_total: 15
tasks_done: 1
crosscuts: 7
created_on: "2026-04-15"
created_by: create-proto-skill
status: complete
---

# Provenance — phase-44.5-project-editor-brood-editor-local-dev-ga

Drafted from `.planning/candidates/phase-44.5-project-editor-brood-editor-local-dev-ga/CANDIDATE.md`
during the first real end-to-end run of the evolution pipeline (task
42.2-13, 2026-04-15).

## Raw source

`compute-self-eval.mjs` surfaced phase 44.5 with selection pressure 29
(15 tasks, 1 done, 7 crosscuts) — well above the drafting threshold. The
phase spans 15 tasks building a local-dev-only Project Editor surface
with a strict Visual Context System mandate.

## The recurring pattern

Reading the 15 tasks, the repeated structural obligation is **not** any
specific editor affordance (inventory grids, bestiary cards, iframe live
preview, etc.) — those are one-offs. The repeated obligation is the
**scaffolding-first Visual Context coverage loop**:

1. Gate the surface to dev (`NODE_ENV=development`).
2. Emit every interactive element with an explicit
   `SiteSection cid="<slug>-site-section"` literal.
3. Wire each cid to the Visual Context Panel + modal-footer CRUD.
4. Verify one round-trip against a real cid **before** any feature work
   begins (the "at least one prompt round-trips" acceptance from 44.5-01).

This pattern shows up in 44.5-01, 44.5-01c, 44.5-04, 44.5-05, 44.5-06,
44.5-07, 44.5-09, 44.5-10 — more than half the phase. It's enforced by
decisions gad-186 / gad-187 (Visual Context System mandatory for all GUI)
and by the `gad-visual-context-panel-identities` skill. The proto-skill
captures the procedural discipline so future gated-editor work in other
projects doesn't re-derive it.

## Related existing artifacts

- `references/skill-shape.md` — uniform skill contract (gad-191 bundle)
- `skills/gad-visual-context-panel-identities/SKILL.md` — the cid/identity
  side of the mandate (reference, not replacement)
- Decision gad-186 — dev-panel copy tokens must be source-searchable
- Decision gad-187 — Visual Context Panel naming contract (cid first)
- Visual Context System mandatory feedback memory (2026-04-15)

## Not in scope for this proto-skill

- The command-bridge security model (44.5-02 / 44.5-02b) — that's a
  separate pattern (dev-only API gating) and should get its own proto.
- Specific primitives (inventory grid, trait bar, diff tree) — those are
  one-off features, not reusable scaffolding patterns.
