---
name: create-proto-skill
description: >-
  Bulk drafter for proto-skills inside the GAD evolution loop. Enumerates
  every raw candidate under `.planning/candidates/`, filters to ones that
  don't yet have a finished proto-skill bundle at `.planning/proto-skills/
  <slug>/`, and drafts each pending candidate in turn. Per-candidate
  checkpoint protocol: write PROVENANCE.md FIRST as a lock marker, then
  workflow.md, then SKILL.md — so a crash or context compaction mid-batch
  leaves half-written bundles identifiable and resumable on the next run.
  Triggers on "draft a skill", "draft proto-skills", "convert candidates
  to proto-skills", or whenever `gad-evolution:evolve` invokes the
  drafting step. Output bundles follow decision gad-191: SKILL.md with
  `status: proto` + `workflow: ./workflow.md`, sibling workflow.md,
  PROVENANCE.md, optional CANDIDATE.md copy. For high-stakes skills that
  need real test runs, use `gad-skill-creator` (heavy path) instead.
lane: meta
type: meta-framework
status: stable
---

# create-proto-skill

Lightweight bulk drafter inside the GAD evolution loop. Reads candidates,
writes proto-skill bundles, hands off to `gad evolution validate`.

## When / When NOT to use

**Use:** `gad-evolution:evolve` drafting step; user says "draft proto-skill
for X" / "convert candidates"; you want SKILL.md without `gad-skill-creator`'s
full eval loop.

**Skip:** high-stakes skill needing real test runs → `gad-skill-creator`.
Improving an existing tested skill → `gad-skill-creator`. Pattern not clear
yet → `gad note`, let next evolution surface it.

## Draft quality bar

Prefer the **compartmentalized-system-as-skill** shape (requirements contract
+ named UX pattern + host-agnostic rollout). One-off fix recipes use the
lighter captured-answer shape instead. Full definition and decision rule:
`references/skill-authoring-patterns.md` (§ Compartmentalized-system-as-skill).
Compartmentalized-system review is drafting-time, not a post-hoc audit.

## Step 1 — enumerate pending candidates

Run `gad evolution status` first to see the current state. The command
renders three counts for the proto-skill backlog:

- **pending** — candidates under `.planning/candidates/<slug>/` with no
  matching `.planning/proto-skills/<slug>/` directory at all.
- **in-progress** — proto-skill dirs with PROVENANCE.md but no SKILL.md
  yet (a previous run crashed or was compacted mid-draft, lock marker left
  behind).
- **complete** — proto-skill dirs with both PROVENANCE.md and SKILL.md.

Your batch is `pending ∪ in-progress`. Skip `complete`.

Enumerate explicitly:

```sh
gad evolution status
# Or, to get the raw list:
ls .planning/candidates/
ls .planning/proto-skills/
```

For each candidate slug, decide its state:

- PROVENANCE.md missing → **pending** (fresh draft)
- PROVENANCE.md present, SKILL.md missing → **in-progress** (resume; keep
  the existing PROVENANCE.md, do not rewrite)
- Both present → **complete** (skip)

## Step 2 — per-candidate checkpoint protocol

Loop over the pending+in-progress list. For each slug, **in this order**:

### 2a. Write PROVENANCE.md FIRST (lock marker)

Create `.planning/proto-skills/<slug>/` and write PROVENANCE.md before
anything else — it is the lock marker that tells the next run "this slug
is in-progress, don't re-draft from scratch". Required frontmatter:
`candidate_slug`, `source_phase`, `pressure_score`, `created_on`,
`created_by: create-proto-skill`, `status: in-progress`. Body: one
sentence stating the source candidate path and evolution turn number.
Output contract: `references/proto-skills.md` (§ Output contract).

If PROVENANCE.md already exists (resume case), **do not overwrite it**.
Read its `status:` field — if `in-progress`, you're resuming a crashed run.

### 2b. Read the candidate

Read `.planning/candidates/<slug>/CANDIDATE.md`. Not curated — no proposed
name, no hand-picked decisions. Decide what matters yourself. Raw input is
intentional: curators filter, raw input pulls in more decisions.

For direct user requests where no candidate exists, write a minimal
CANDIDATE.md from whatever the user is pointing at, then continue.

### 2c. Write workflow.md

Write the procedural body to `.planning/proto-skills/<slug>/workflow.md`:
step-by-step instructions, guardrails, failure modes. Imperative form,
explain *why* not just *what*. Split deeper content into
`references/<file>.md` and reference from there. Pick the kebab-case skill
name yourself from phase or context — do not ask the human.

### 2d. Write SKILL.md (thin entry point)

Write `.planning/proto-skills/<slug>/SKILL.md` per decision gad-191. Required
frontmatter: `name`, `description` (folded `>-`), `status: proto`,
`workflow: ./workflow.md`. Body: one-paragraph summary, a `**Workflow:**`
link to `./workflow.md`, and a `## Provenance` block citing the candidate
path, date, and a pointer to PROVENANCE.md. Shape contract:
`references/skill-shape.md` (§ Proto-skill layout).

Hard rule: **SKILL.md under 200 lines.** Long body → move to workflow.md.

### 2e. Flip PROVENANCE.md status to `complete`

After both workflow.md and SKILL.md land, update PROVENANCE.md `status:`
from `in-progress` to `complete`. This closes the lock marker.

### 2f. Commit checkpoint (if in a long batch)

For batches over ~5 candidates, commit after each completed proto-skill so
partial progress survives independent of the working tree. Commit message
shape: `evolution: draft proto-skill <slug> from candidate`.

## Step 3 — hand off to the validator

`gad-evolution:evolve` runs `gad-evolution-validator` after the batch.
Validator writes `VALIDATION.md` — advisory file-ref, CLI-command, and
shape checks. Not blocking. Human reviews SKILL.md + workflow.md +
VALIDATION.md before promote/discard.

## Step 4 — stop

Do not iterate, run test prompts, or ask for review. Proto-skills stay in
`.planning/proto-skills/<slug>/` until a human runs `gad evolution install`,
`promote`, or `discard`.

## Resume protocol (crash / auto-compact recovery)

1. `gad evolution status` — `in-progress` count is your work queue.
2. For each in-progress slug, read PROVENANCE.md to confirm it's a lock
   marker, not a false positive.
3. Resume at step 2b (re-read the candidate, then 2c → 2d → 2e).
4. Never regenerate PROVENANCE.md — original timestamp is part of the audit trail.

## Failure modes

- **Asking the user questions / running test prompts.** Make the call,
  document in workflow.md. Stop at SKILL.md + workflow.md — that's
  `gad-skill-creator` territory.
- **CANDIDATE.md is sparse.** Pull from the file references it cites —
  that's where the depth lives.
- **Forgot PROVENANCE.md first.** Re-run from step 2a. Without a lock
  marker, crash-resume can't tell "never started" from "half-done".
- **Existing proto-skills dir from a prior run.** `complete` → skip,
  `in-progress` → resume. Never overwrite `complete`.

## Reference

- `references/skill-shape.md` — uniform shape contract
- `references/proto-skills.md` — proto-skill bundle contract
- `references/skill-authoring-patterns.md` — quality bar and compartmentalized-system pattern
- `gad-skill-creator` — heavy path with full eval loop
- `gad-evolution-evolve` — orchestrator that calls this in a batch
- Decision gad-171 — bulk batching + per-candidate checkpoints
- Decision gad-191 — proto-skill bundle shape at `.planning/proto-skills/`
