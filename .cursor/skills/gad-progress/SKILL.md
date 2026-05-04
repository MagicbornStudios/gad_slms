---
name: gad-progress
description: "Check project progress, show context, and route to next action (execute or plan)"
---

<cursor_skill_adapter>
## A. Skill Invocation
- This skill is invoked when the user mentions `gad-progress` or describes a task matching this skill.
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
Check project progress, summarize recent work and what's ahead, then intelligently route to the next action - either executing an existing plan or creating the next one.

Provides situational awareness before continuing work.
</objective>

<execution_context>
@workflows/progress.md
</execution_context>

<process>
Execute the progress workflow from @workflows/progress.md end-to-end.
Preserve all routing logic (Routes A through F) and edge case handling.
</process>
