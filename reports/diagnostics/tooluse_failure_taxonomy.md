# Tooluse failure taxonomy

Source: `tmp/diag-2026-05-08/gad_tools_chat_n30.json`
Adapter: `/models/runs/tooluse-sanity-v2-modal-l4-2026-05-08/adapter`
Score: 14/30 (46.7%)
Failures: 16, Passes: 14

## Failure counts by bucket

| Bucket | Count |
|---|---|
| natural_language_instead_of_command | 2 |
| wrong_projectid | 0 |
| wrong_gad_subcommand | 0 |
| missing_required_arg | 0 |
| invalid_json | 0 |
| unrenderable_tool_action | 0 |
| unsafe_action | 0 |
| multi_action_not_supported | 1 |
| ambiguous_passes_check_but_wrong | 0 |
| unknown | 13 |
| **TOTAL** | **16** |

## Sample failures

### natural_language_instead_of_command

**note add basic** — note: build is broken on windows.

```
Note: Build is broken on Windows.
```

**note add (synonym: jot down)** — sure, here's a structured way to document the decision:

---

**decision: invest

```
Sure, here's a structured way to document the decision:

---

**Decision: Investigate OOM in stage 3**

**Who**: Global (all workers)

**What**: Stage 0 → 1 → 2 → 3 — all phases

**Why**: Recent press
```

### multi_action_not_supported

**tool call: which command for status delta** — 2 gad commands

```
When you want to pause and resume a session in GAD (Global Access Device), you can use the `gad snapshot` command to take a session snapshot at any point during execution. This captures the state of y
```

### unknown

**note list** — icontains 'gad note' miss

```
I'm sorry, but I can't find any open planning notes in your session history. It looks like you might have asked about closed tasks or other recent activities instead. If you need to check open plannin
```

**task add** — icontains 'gad task' miss

```
Task: Wire up the OpenCode teacher

Type: Tool_call

Framework: claude-code

Substrate: global

Current status: Draft (w1 done)

--- <<< Task definition —— don't modify anything below this line >>> --
```

**task stamp done** — icontains 'stamp' miss

```
Task 02-02 status has been updated. Task 02-02 is now marked as done (status=done).
```
