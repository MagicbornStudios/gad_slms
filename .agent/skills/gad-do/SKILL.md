---
name: gad-do
description: Route freeform text to the right GAD command automatically
---

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
$ARGUMENTS
</context>

<process>
Execute the do workflow from @workflows/do.md end-to-end.
Route user intent to the best GAD command and invoke it.
</process>
