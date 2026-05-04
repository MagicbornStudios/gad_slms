---
name: gad-note
description: "Zero-friction idea capture. Append, list, or promote notes to todos."
---

<cursor_skill_adapter>
## A. Skill Invocation
- This skill is invoked when the user mentions `gad-note` or describes a task matching this skill.
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
Zero-friction idea capture — one Write call, one confirmation line.

Three subcommands:
- **append** (default): Save a timestamped note file. No questions, no formatting.
- **list**: Show all notes from project and global scopes.
- **promote**: Convert a note into a structured todo.

Runs inline — no Task, no conversational prompting, no Bash.
</objective>

<execution_context>
@workflows/note.md
@references/ui-brand.md
</execution_context>

<context>
{{GAD_ARGS}}
</context>

<process>
Execute the note workflow from @workflows/note.md end-to-end.
Capture the note, list notes, or promote to todo — depending on arguments.
</process>
