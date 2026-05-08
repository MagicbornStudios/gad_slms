# Handoff & Subagent Prompt Quality Rubric

**Status:** v1, locked 2026-05-08
**Decision:** companion to `slm-learning-128` (skills must produce
signal); applies to handoff prompts AND subagent dispatch prompts
**Companion memory:**
`feedback_session_end_handoff_prompt.md` (always end session with
a next-session prompt)

## Why this exists

Bad handoff prompts cause:
- Context loss between sessions
- Subagents producing wrong output (drift)
- Wasted compute on rediscovery
- Repeated user re-explanations

The 143MB OCR commit by the haiku subagent
(`SL-E:subagent-committed-143mb-ocr-raw-2026-05-08`) is one
example: the dispatch prompt didn't include the data-residency
policy. A scored rubric would have flagged that gap.

## The 8-dimension rubric (score 0-2 each, max 16)

| Dim | Question | 0 | 1 | 2 |
|---|---|---|---|---|
| **State** | Does the prompt say where we are now? | absent | partial | full SITREP |
| **Goal** | Is the desired outcome explicit? | vague | implied | named with success criteria |
| **Files** | Are relevant file paths cited? | none | 1-2 | 3-7 with line refs where helpful |
| **Decisions** | Are governing decisions referenced? | none | named without ids | named with `slm-learning-NNN` |
| **Constraints** | Are hard rules / forbidden actions listed? | none | implicit | explicit list |
| **Format** | Is the expected reply shape specified? | none | informal | structured (length cap, sections) |
| **Tools** | Are required tools / commands named? | none | hinted | exact CLI invocation |
| **Verification** | How will the result be checked? | none | manual eyeball | automated test / contract |

**Threshold for sending:**
- ≥ 12 → ship
- 8–11 → revise (which dimension is at 0?)
- < 8 → don't send; the prompt isn't ready

## Subagent-specific additions

For Agent spawns, additionally include:
- **Reply length cap** ("under 200 words", "single sentence", "structured 3-line summary")
- **Forbidden actions** ("do not commit", "do not edit files outside `<dir>`", "do not run network-fetching tools")
- **Failure mode** ("if X is missing, exit 2 with a clear message; do not continue")
- **Commit policy** ("commit if changes pass validation; otherwise leave staged for human review")

## Cross-project handoff additions

For handoffs filed to other lanes/projects (`.planning/handoffs/open/`):
- **Surface** field (`local | api-bound | human-loop | cross-project`)
- **Recipient** named (lane / soul / dispatcher)
- **Acceptance gate** — explicit checklist the receiver completes
- **Closeout protocol** — how to signal completion back

## The 143MB lesson encoded as a rule

Subagent dispatch prompts that may run `git add` or `git commit`
MUST include this clause:

> Data residency: do NOT commit files larger than 5MB. Anything
> >100MB MUST go to a Modal volume per `slm-learning-105`. Add new
> generated data paths to `.gitignore` BEFORE staging.

Without this clause, the prompt scores 0 on **Constraints** and
should not be sent.

## Self-grading at end of session

Before ending a session, the orchestrator scores its own
"next-session prompt" against this rubric. If < 12, revise before
posting. Log the score in the prompt itself for transparency:

```
[handoff-prompt-score: 14/16 — full state, explicit constraints,
files cited, decisions named, format specified; format dim docked
1 (no length cap). Verification dim docked 1 (manual eyeball).]
```

## When to use

- Every session end (next-session prompt)
- Every Agent dispatch (subagent prompt)
- Every cross-project handoff (`.planning/handoffs/open/`)
- Every skill `examples` field (the example prompts ARE training
  data; they should also score >= 12)

## See also

- `feedback_session_end_handoff_prompt.md` (operator memory)
- `slm-learning-128` (skills must produce signal — handoff prompts
  are skills too)
- `.planning/ERRORS-AND-ATTEMPTS.xml` (the SL-E records that
  motivate this rubric)
