---
name: gad-evolution-validator
description: >-
  Run the advisory validator on a proto-skill and write VALIDATION.md alongside
  its SKILL.md. The validator extracts file references and `gad <subcommand>`
  CLI commands cited in the SKILL.md, then checks each against the actual repo
  — flagging files that don't exist and CLI commands that don't appear in
  `gad --help`. The output is ADVISORY, not blocking — the human reviewer
  reads VALIDATION.md alongside SKILL.md before promoting or discarding the
  proto-skill. Use when `gad-evolution-evolve` finishes drafting a proto-skill,
  or any time you want to validate an existing proto-skill in
  `.planning/proto-skills/<slug>/`.
lane: meta
type: meta-framework
workflow: workflows/evolution-validator.md
---


# gad-evolution-validator

**Workflow:** [workflows/evolution-validator.md](../../workflows/evolution-validator.md)

Run the workflow. All procedural detail, examples, and tool sequencing live in the workflow file per the canonical skill shape (references/skill-shape.md, decision gad-190).
