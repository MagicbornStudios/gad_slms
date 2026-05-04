---
name: gad-workspace-sync
description: Crawl monorepo for .planning/ directories and sync gad-config.toml roots
lane: dev
type: command-wrapper
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
workflow: workflows/workspace-sync.md
---


# gad-workspace-sync

**Workflow:** [workflows/workspace-sync.md](../../workflows/workspace-sync.md)

Run the workflow. All procedural detail, examples, and tool sequencing live in the workflow file per the canonical skill shape (references/skill-shape.md, decision gad-190).
