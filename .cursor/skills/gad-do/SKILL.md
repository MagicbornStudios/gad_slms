---
name: gad-do
description: "Route freeform text to the right GAD command automatically"
---

<cursor_skill_adapter>
## A. Skill Invocation
- This skill is invoked when the user mentions `gad-do` or describes a task matching this skill.
- Treat all user text after the skill mention as `{{GAD_ARGS}}`.
- If no arguments are present, treat `{{GAD_ARGS}}` as empty.

## B. User Prompting
When the workflow needs user input, prompt the user conversationally:
- Present options as a numbered list in your response text
- Ask the user to reply with their choice
- For multi-select, ask for comma-separated numbers

## C. Tool Usage
Use these Cursor tools when executing GAD workflows:
- `Shell` for running commands (terminal operations)
- `StrReplace` for editing existing files
- `Read`, `Write`, `Glob`, `Grep`, `Task`, `WebSearch`, `WebFetch`, `TodoWrite` as needed

## D. Subagent Spawning
When the workflow needs to spawn a subagent:
- Use `Task(subagent_type="generalPurpose", ...)`
- The `model` parameter maps to Cursor's model options (e.g., "fast")
</cursor_skill_adapter>

<objective>
Analyze freeform natural language input and dispatch to the most appropriate GAD command.

Acts as a smart dispatcher — never does the work itself. Matches intent to the best GAD command using routing rules, confirms the match, then hands off.

Use when you know what you want but don't know which `/gad-*` command to run.
</objective>

<execution_context>
@workflows/do.md
@references/ui-brand.md
</execution_context>

<context>
{{GAD_ARGS}}
</context>

<process>
Execute the do workflow from @workflows/do.md end-to-end.
Route user intent to the best GAD command and invoke it.
</process>
