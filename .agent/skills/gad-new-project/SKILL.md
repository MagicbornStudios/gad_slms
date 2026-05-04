---
name: gad-new-project
description: Initialize a new project with deep context gathering and PROJECT.md
---

<context>
**Flags:**
- `--auto` — Automatic mode. After config questions, runs research → requirements → roadmap without further interaction. Expects idea document via @ reference.
</context>

<objective>
Initialize a new project through unified flow: questioning → research (optional) → requirements → roadmap.

**Creates:**
- `.planning/PROJECT.md` — project context
- `gad-config.toml` — canonical workflow preferences
- `.planning/config.json` — generated compatibility mirror
- `.planning/research/` — domain research (optional)
- `.planning/REQUIREMENTS.md` — scoped requirements
- `.planning/ROADMAP.md` — phase structure
- `.planning/STATE.md` — project memory

**After this command:** Run `/gad-plan-phase 1` to start execution.
</objective>

<execution_context>
@workflows/gad-new-project.md
@references/questioning.md
@references/ui-brand.md
@templates/project.md
@templates/requirements.md
</execution_context>

<process>
Execute the new-project workflow from @workflows/gad-new-project.md end-to-end.
Preserve all workflow gates (validation, approvals, commits, routing).
</process>
