---
name: framework-upgrade
description: Ship a change to the GAD framework itself (new skill, new subagent, reworked command, altered loop) in a way that preserves the ability to interpret eval results across versions. Trigger this skill whenever a framework change could affect how an agent behaves during an eval run — e.g. adding a mandatory skill, changing a command's spawned subagent, rewording AGENTS.md, changing the plan-phase flow, anything that would make "the same agent prompt" produce different output. The goal is to make framework drift visible so we don't mistake a framework improvement for an agent improvement (or vice versa) when scores move.
lane: meta
type: meta-framework
---

# framework-upgrade

The GAD framework is the experimental apparatus. When you upgrade the apparatus while running experiments, cross-round comparisons get noisy — a run might score better because the agent got better, OR because you rewrote a skill, OR because you swapped in a different subagent. This skill is the methodology for shipping framework changes without poisoning the eval dataset.

## When to trigger this skill

- Adding, removing, or meaningfully editing a skill document.
- Adding, removing, or changing the tools list of a subagent.
- Rewiring a command's `agent:` frontmatter (different subagent spawned).
- Editing `AGENTS.md` anywhere in the framework root.
- Changing the `gad snapshot` / `gad context` output format.
- Revising the composite scoring formula or weights.
- Upgrading the trace schema.
- Anything else that would cause "re-run the v5 escape-the-dungeon test" to behave materially differently than the original v5 run.

## What NOT to trigger it for

- Typo fixes in documentation comments.
- Adding a test that doesn't change runtime behaviour.
- Refactoring internal CLI code where the public interface is unchanged.
- Cosmetic edits to the portfolio site (that's `portfolio-sync` territory).

## Branch strategy

```
main                 — current framework, what eval agents run against by default
version/v1.0         — frozen snapshot, tagged at the v1.0 milestone close
version/v1.1         — frozen snapshot, tagged at the v1.1 milestone close
version/v1.2-wip     — work in progress for an upcoming version bump
```

**Rules:**

1. **`main` = current.** Eval agents always run against `main` unless explicitly told to check out a frozen version branch.
2. **Frozen branches are read-only.** Once a `version/vX.Y` branch is cut, it does not receive new commits except for critical security fixes. Framework work continues on `main`.
3. **Every TRACE.json stamps its framework commit.** The `gad_version` field already exists; we extend it to also record the branch (`main`), the commit hash (`<short-sha>`), and the HEAD timestamp. This is how we later distinguish "agent improved" from "framework improved".
4. **When you cut a version:** branch from `main`, tag the commit (`v1.2`), update `package.json` version, push both the branch and the tag. Then update `.planning/STATE.xml` milestone to the next version.

## The upgrade procedure

### Step 1 — capture the baseline

Before you change anything, know where you stand. Pick a representative eval project (usually `escape-the-dungeon` for GAD-condition runs) and re-run it against the *current* framework. This is your "before" data point. Preserve the run per `gad eval preserve`.

```sh
gad eval run escape-the-dungeon
gad eval preserve escape-the-dungeon v<N> --from <worktree>
```

Note the `gad_version` and commit hash stamped into the resulting `TRACE.json`. That's your baseline for the comparison.

### Step 2 — make the change

Work on `main`. Small, atomic commits with task ids as usual (per decision gad-18). Track the work in `.planning/` — this is a GAD phase like any other.

### Step 3 — re-run the same eval

Immediately after the change lands, re-run the same eval project:

```sh
gad eval run escape-the-dungeon
gad eval preserve escape-the-dungeon v<N+1> --from <worktree>
```

Now you have two runs: one "before" the framework change, one "after." Both are recorded with their framework commit hashes.

### Step 4 — compare scores honestly

Before declaring "the framework change worked" or "the change was neutral":

- Was the delta larger than normal run-to-run variance? Look at previous consecutive runs in the same project to get a sense of typical variance.
- Did the human reviewer score change? A 0.05 shift in composite with no reviewer shift is probably noise.
- Did any dimension move in an unexpected direction? A "simpler skill doc" that drops skill_accuracy is worth investigating.
- Did the gate status change? That's a big signal — either fixed or broken.

Write up the comparison as a finding in `evals/FINDINGS-YYYY-MM-DD-framework-upgrade-<slug>.md`. Reference both run versions and the framework commit range.

### Step 5 — cut a version if the change is significant

If the upgrade is substantial enough that you wouldn't want future comparisons to span it without acknowledgement:

```sh
git checkout main
git tag -a v1.2 -m "Framework v1.2 — <one-line summary>"
git branch version/v1.2 v1.2
git push origin main v1.2 version/v1.2
```

Update `STATE.xml` milestone, bump `package.json` version, commit with a task id, push.

### Step 6 — update the portfolio

Run `portfolio-sync`: the site's `/methodology` page should show the new formula if scoring changed, the `/gad` overview should reflect the new catalog, the `/planning` page picks up the new milestone automatically, and any cross-version comparison docs should note which framework version each run ran against.

## Re-running old evals against the current framework

This is how you detect framework drift:

```sh
git checkout main
gad eval run escape-the-dungeon
gad eval diff escape-the-dungeon v<old> v<new>
```

If scores shifted significantly with no corresponding agent change (same model, same prompt), the framework moved. Document what changed and why the shift makes sense.

## Trace schema versioning

The trace schema itself is versioned in `trace_schema_version`. When you add a field (phase 25 ships schema v4 with full tool_use + subagent_spawn breakdown):

1. Increment `trace_schema_version` in the TRACE emitter.
2. Keep the old fields around — additive schema, not replacement.
3. The site's prebuild script handles mixed schemas: older runs show what they have, newer runs render the extra detail.
4. Don't backfill old runs. They're historical records; rewriting them is rewriting history.

## How this interacts with other skills

- `portfolio-sync` — after a framework upgrade, the site needs to resync. Both should fire.
- `create-skill` — if you're adding a new skill as part of the upgrade, use `create-skill` for authoring and `framework-upgrade` for the surrounding procedure.
- `eval-run` / `eval-preserve` — the re-run steps depend on these; this skill just sequences them correctly.
- `plan-phase` / `execute-phase` — the upgrade itself should be a GAD phase (phase 25 in the current roadmap) with tracked tasks.

## Expected cadence

Framework upgrades should be rare and deliberate. If you're touching this skill more than once a month, you're iterating on the framework while running experiments — that's how you poison your dataset. Batch framework changes into proper version bumps, cut a branch, freeze, move on.

The invariant: **you should always be able to tell a reader which framework version each score was recorded against, and what changed between versions.** If you can't answer that, you've lost the ability to interpret your own results.
