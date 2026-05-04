---
name: gad-evolution-images
description: >-
  Audit and generate skill/proto-skill/installed-skill images through the GAD
  CLI. Use when you need a missing-image report, a structured prompt payload
  for image jobs, or an opt-in OpenAI generation pass. Generation is disabled
  by default and requires OPENAI_API_KEY.
lane: prod
type: command-wrapper
workflow: workflows/evolution-images.md
---


# gad-evolution-images

**Workflow:** [workflows/evolution-images.md](../../workflows/evolution-images.md)

Run the workflow. All procedural detail, examples, and tool sequencing live in the workflow file per the canonical skill shape (references/skill-shape.md, decision gad-190).
