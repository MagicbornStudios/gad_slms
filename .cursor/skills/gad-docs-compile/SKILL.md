---
name: gad-docs-compile
description: Compile planning docs from all roots into docs_sink as MDX files
lane: dev
type: command-wrapper
argument-hint: [--sink <path>]
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
workflow: workflows/docs-compile.md
---


# gad-docs-compile

**Workflow:** [workflows/docs-compile.md](../../workflows/docs-compile.md)

Run the workflow. All procedural detail, examples, and tool sequencing live in the workflow file per the canonical skill shape (references/skill-shape.md, decision gad-190).
