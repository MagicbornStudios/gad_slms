---
name: gad-skill-creator
description: >-
  Create a GAD skill autonomously by feeding context to Anthropic's canonical
  skill-creator. Use when something in the GAD workflow should become a reusable
  skill — a repeated CLI sequence, a recurring decision pattern, a candidate
  emitted by `gad-evolution:evolve`, or a direct user request like "make a skill
  for X". This skill is a thin wrapper: it ensures the canonical skill-creator
  is installed, packages full project context (phase, tasks, decisions, file
  refs, CLI surface, related skills) into an INTENT.md file, and hands it to
  skill-creator so the user never needs to sit through a Q&A interview. Triggers
  on "make a skill for", "create a skill", "we need a skill that", "turn this
  into a skill", "promote this candidate to a skill", or whenever a completed
  task reveals a reusable pattern worth capturing.
lane: meta
type: meta-framework
workflow: workflows/skill-creator.md
---


# gad-skill-creator

**Workflow:** [workflows/skill-creator.md](../../workflows/skill-creator.md)

Run the workflow. All procedural detail, examples, and tool sequencing live in the workflow file per the canonical skill shape (references/skill-shape.md, decision gad-190).
