---
name: objective-eval-design
description: >-
  Design evaluations that produce structured, objective, comparable data instead of single
  opaque scores. Trigger this skill when designing a new species, adding a new scoring
  dimension, deciding whether to measure something with human review vs automation, or when
  a reviewer or stakeholder asks "why did this generation score X?" and the answer isn't
  immediately visible in the data. The core discipline is that every measurement you add
  should answer a specific research question, expose its inputs clearly, and be comparable
  across generations. If a score can't be decomposed into dimensions or traced back to the
  events that produced it, it isn't objective — it's just a vibe with a number attached.
lane: meta
type: meta-framework
---

# objective-eval-design

The GAD evaluation framework exists to find out whether structured planning helps agents
build better things. The answer to that question is only trustworthy if the measurements
that produce it are themselves trustworthy. This skill is the methodology for designing
measurements that hold up.

## The test for any new measurement

Before you add a new scoring dimension, a new metric, a new gate criterion, or a new chart,
ask four questions. If you can't answer all four, the measurement isn't ready.

1. **What specific research question does this answer?** "Is bare better than GAD" is not
   a research question — it's a hypothesis. A research question is "does the bare workflow
   produce more novel skill documents per generation than GAD?" or "do agents that hit the
   forge gate within the first 10 minutes score higher on human review?" A measurement that
   doesn't answer a specific question is a dashboard-filler.

2. **What are its inputs and can a reader see them?** A composite score of 0.177 is
   derived from six dimension scores times six weights, plus a low-score cap. If a reader
   hits the per-generation page and sees the number but can't see the six inputs, the
   number is opaque. Every measurement this skill touches has to be accompanied by a way
   to drill into what went into it. `/generations/[species]/[version]` formula breakdown is
   the template.

3. **Is it comparable across generations?** A measurement that uses a different formula,
   rubric, or input schema on different generations is a local artifact, not a comparable
   metric. Rubric versions, requirements versions, and trace schema versions all exist
   precisely so we can detect and label incompatible cross-generation comparisons. Add a
   `*_version` field to any new measurement that might evolve.

4. **Can it be decomposed?** Single numbers lie. A dimension rarely needs a sub-dimension
   but when it does, make room for that split in the schema from day one. `human_review`
   started as a single number and had to be expanded to a rubric because reviewers could
   disagree about playability without disagreeing about polish. If a measurement could
   plausibly be split in the future, design the schema so a split doesn't break old data.

## Avoid these traps

### Trap 1 — The "vibe with a number attached"

Human review was originally a single 0.0-1.0 score set by a reviewer who "felt like it
was mid." That number is unfalsifiable: two reviewers can give different numbers for the
same generation and there's no way to know whose is right, because there's no structure to
disagree inside. The fix: structured rubric with per-dimension scores and per-dimension
notes. Reviewers can still disagree but now their disagreements are localized and traceable.

### Trap 2 — The "process metric that rescues a broken generation"

v5 escape-the-dungeon scored requirement_coverage 1.0 and planning_quality 1.0 while the
game itself rendered a blank screen (human_review = 0.0). The mechanical dimensions were
legitimate — the agent did plan 12 phases and complete 12 tasks and commit per task — but
none of that mattered because the output was broken. This is gad-29's whole reason for
existing: **process metrics do not guarantee output quality**. The fix was to weight human
review at 30% and cap composite scores when human review is catastrophically low. When
you're designing a new measurement, check whether it could produce the same failure: a
high score that coexists with a broken artifact. If yes, it needs a cap or a gate.

### Trap 3 — The "what I expected the agent to do" bias

Skill accuracy is defined as "did the agent trigger the expected skills at the right
moments." The word "expected" carries the whole bias. If the agent solved the task without
using the expected skills, is that failure or emergence? The measurement as defined treats
it as failure. Depending on what the species is testing, that might be wrong. The fix
isn't to throw out the measurement — it's to be explicit about what it's measuring
("conformance to the framework's expected usage pattern") and add a sibling measurement
when you want to capture something else ("novel workflow emergence" for bare/emergent).
Never let one measurement silently redefine what success looks like.

### Trap 4 — The "we'll add the breakdown later"

Aggregate-only fields like `skill_accuracy: 0.17` (v8 TRACE.json) are the trap every
"we'll add the detail later" promise falls into. Once the number is stored without the
breakdown, you can't derive the breakdown. The original generation is gone, the session is
closed, the agent is rate-limited. The only information you preserved is the bare number.
Always capture the decomposition at measurement time, even if your UI hasn't caught up yet.
Phase 25's trace schema v4 exists to fix this for tool-level data; apply the same
discipline to every new measurement.

## Design patterns that work

### Pattern 1 — Dimensions + aggregate

Every scored measurement has:
- A `dimensions` object with per-field scores and notes
- An `aggregate_score` computed from the dimensions with documented weights
- A `*_version` field for schema evolution

The aggregate is a convenience, not the truth. The truth is the dimensions. Consumers that
just want a number read the aggregate; consumers that want to understand why read the
dimensions.

### Pattern 2 — Formula transparency

Every derived number has a rendering that shows the formula with the actual values. The
per-run page's composite formula table (dimension × weight = contribution, sorted by
contribution) is the template. Anywhere a number appears and isn't obviously its own input,
there's a "how was this computed" expansion.

### Pattern 3 — Automated where possible, subjective where required

The test for whether a gate criterion can be automated is whether a playwright test can
check it deterministically. "Does the game loop complete at least 3 room transitions
without softlock" — automatable. "Does the game feel fun" — not automatable, belongs in
human rubric. Don't burn human review budget on things a test can check; save it for the
things that genuinely require judgment.

### Pattern 4 — Questions before charts

When someone proposes a new chart, ask "what question does it answer?" If the answer is
"it shows the data" the chart isn't ready. If the answer is "does X correlate with Y" the
chart has to be shaped around that correlation, not around the data shape. The scatter
plot on /#graphs answers "do process metrics agree with human review" and that's why the
diagonal reference line is there — it's the thing you're looking for disagreement against.
Without the reference line the chart is just dots.

### Pattern 5 — Query first, visualize second

Before you build a chart, write the query that produces the data for it. If the query is
obvious and the data falls out cleanly, the chart is probably worth building. If you can't
even write the query without preprocessing, the visualization will also be awkward. `gad
query` (phase 27 track 4) is the tool that makes this pattern possible — you draft
queries against the trace dataset, see what falls out, then promote the useful ones to
/insights cards.

## When this skill interacts with others

- **create-skill** — when you invent a new methodology while running a generation, this
  skill tells you how to design the measurement that proves the methodology worked.
  Capture the methodology with `create-skill`, design the measurement with
  `objective-eval-design`.
- **framework-upgrade** — changing a scoring formula or rubric is a framework change and
  has to go through the `framework-upgrade` procedure so cross-version comparisons stay
  honest.
- **portfolio-sync** — when new rubrics or derived metrics land, the site picks them up
  through the prebuild. Don't hand-edit generated files.
- **plan-phase / execute-phase** — phase 27 is the first phase organized entirely around
  this methodology. Future data-production phases follow the same shape: discuss-phase
  captures the research question, plan-phase breaks down the measurement pipeline,
  execute-phase ships the infrastructure.

## Expected cadence

Not every session should touch the data pipeline. But whenever you add a new species,
a new rubric dimension, a new chart, or a new scoring criterion, check this skill first.
The five tests at the top (question, inputs, comparability, decomposability, trap check)
take 30 seconds each and catch most of the drift before it ships.

The invariant: **every number on the site is explainable, decomposable, and comparable.**
If you can't explain a number to a reader with a page of drill-down, the number isn't
ready to publish.

## Vocabulary note (post decision gad-212)

- Species = the character-build / configuration being measured (skills, tech stack,
  context framework, constraints).
- Generation = a single produced artifact (one run of a species in its project ecosystem).
- "Evaluation" in this skill refers to the academic methodology — the discipline of
  producing structured, comparable measurements. That is preserved intentionally.
- CLI: `gad species <op>` for species management, `gad generation <op>` for
  generation-level operations, `gad spawn <project>/<species>` to produce a new
  generation (decision gad-219).
