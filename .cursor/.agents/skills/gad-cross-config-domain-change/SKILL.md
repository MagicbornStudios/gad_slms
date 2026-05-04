---
name: gad-cross-config-domain-change
description: >-
  Rename a domain concept (directory, vocabulary term, schema key) across a
  GAD monorepo in a way that keeps every `[[planning.roots]]` and `[[evals.roots]]`
  in `gad-config.toml` consistent and grep-clean. One entrypoint, two workflows
  chosen by scope — (A) monorepo-wide rename that walks the union of all planning
  and eval roots declared in the top-level `gad-config.toml`, and (B) single-project
  rename scoped to one `.planning/` root. Use when a user says "rename evals to
  species", "the term X is wrong everywhere", "normalize the vocabulary across all
  projects", or "this rename touches both the framework and the site". Both
  workflows begin with a pre-flight config audit so the operator sees exactly
  which roots will be touched before any file moves.
lane: meta
type: meta-framework
source_phase: "44"
source_evolution: 2026-04-14-002
status: proto
parent_skill: null
workflow: workflows/cross-config-domain-change.md
---


# gad-cross-config-domain-change

**Workflow:** [workflows/cross-config-domain-change.md](../../workflows/cross-config-domain-change.md)

Run the workflow. All procedural detail, examples, and tool sequencing live in the workflow file per the canonical skill shape (references/skill-shape.md, decision gad-190).
