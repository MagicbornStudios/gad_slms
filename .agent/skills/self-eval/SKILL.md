---
name: self-eval
description: Score a round of GAD development work on this monorepo — framework overhead ratio, loop compliance, planning doc freshness, real-world brownfield metrics.
lane: meta
type: meta-framework
---

# self-eval

Score how well GAD performed on its own development. This is the brownfield evaluation that
uses real work data, not isolated game generations.

## Context

We use GAD to build GAD. 7 workspaces, 93+ decisions, 141+ completed tasks, 2300+ traced tool calls. This is the most honest test of whether GAD helps or hurts productivity — no cherry-picking, no controlled conditions, just actual work.

## Dimensions (rubric)

### 1. Framework overhead ratio (0.0 – 1.0)
What percentage of tool calls target .planning/ files vs source code?
- < 15% overhead = 1.0 (framework stays out of the way)
- 15-25% = 0.7 (acceptable)
- 25-40% = 0.4 (concerning)
- > 40% = 0.1 (framework is the bottleneck)

### 2. Loop compliance (0.0 – 1.0)
How many sessions follow the GAD loop? (snapshot — work — update docs — commit)
- Check: does each session start with `gad snapshot`?
- Check: are planning docs updated before or with each commit?
- Score = compliant sessions / total sessions

### 3. Planning doc freshness (0.0 – 1.0)
Are STATE.xml and TASK-REGISTRY.xml current?
- Check: last-updated timestamp vs last commit date
- Check: next-action describes actual current state
- Check: task statuses match git history (done tasks have commits)

### 4. Decision capture rate (0.0 – 1.0)
Are decisions being captured as they happen?
- Count decisions created per session vs decisions implied by changes
- Check: do decisions reference the context that created them?

### 5. Cross-project coherence (0.0 – 1.0)
Do the 7 workspaces maintain consistent state?
- Check: are all workspace STATE.xml files current?
- Check: does the global workspace reflect all sub-project states?
- Check: are decisions in the right project (not leaked to global)?

### 6. Delivery velocity (qualitative)
What shipped per round? Not a numeric score — a narrative:
- Features shipped
- Bugs fixed
- Decisions made
- Generations spawned
- Site pages published

## How to compute

1. Run trace-analysis skill first to get raw metrics
2. Parse git log for the round's date range
3. Read all workspace STATE.xml files
4. Compute each dimension score
5. Produce a structured report with evidence

## Output

SELF-EVAL-ROUND-N.md in .planning/ with:
- Per-dimension scores with evidence
- Aggregate score (weighted)
- Comparison to previous rounds
- Actionable findings (what to improve)

## Integration with the site

Self-eval reports should appear alongside species/generation evaluation reports on the
landing page. The "Results" section should show both controlled (species generations) and
real-world (self-eval) data. This is what makes the Freedom hypothesis credible — we're
not just testing on toys.

## Vocabulary note (post decision gad-212)

"Self-eval" retains the methodology sense of "evaluation" — the act of scoring GAD against
its own rubric. Where this skill refers to produced artifacts in the species/generation
system (e.g. the "game evals" on escape-the-dungeon), those now read as "species
generations" per gad-212 + gad-219.
