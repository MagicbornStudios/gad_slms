# Provenance

This proto-skill was authored on 2026-04-14 under task 44-26 in the
`get-anything-done` project. It replaces the earlier `phase-43-eval-vocabulary`
draft, which was discarded because it baked in submodule-specific paths like
`apps/public/evals` and treated the `evals` → `species` rename as a one-shot
migration rather than an instance of the general cross-config domain-change
pattern. The new skill is intentionally scope-independent: it reads
`gad-config.toml` at the monorepo root as the single source of truth (per
decision gad-160), walks the union of `[[planning.roots]]` and `[[evals.roots]]`
in Workflow A, scopes down to a single `.planning/` root in Workflow B, and
uses the `evals` → `species` rename only as a worked example rather than a
hard-coded path. Authored by task 44-26 on 2026-04-14, source evolution
2026-04-14-002.
