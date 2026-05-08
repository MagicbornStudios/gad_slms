---
id: h-2026-05-08T11-50-00-monorepo-trigger-skill-envelope
projectid: slm-learning
phase: 04
task_id: SL-T-04-pressure-formula-v2
created_at: 2026-05-08T11:50:00.000Z
created_by: dr-stein-slm-learning
claimed_by:
claimed_at:
completed_at:
priority: medium
estimated_context: bounded
risk: safe
time: standard
surface: cross-project
runtime_preference: claude-code
recipient: monorepo / framework team dispatcher (gad CLI maintainers)
---

# Cross-project handoff — `trigger_skill` envelope wiring in `gad` CLI

From: Dr. Stein, slm-learning root
To: monorepo / framework team's dispatcher
Why: slm-learning's pressure formula v2 has a `s_skill` term whose
weight (`w_skill`) is currently set to **0** because the underlying
provenance envelope does not include `trigger_skill`. The
`scripts/research/skill_pressure_correlation.py` script reads
`.planning/.provenance/*.jsonl` and looks for `trigger_skill` in each
event, but the field is never populated by today's gad-log emitter.
This is a framework-level gap that slm-learning cannot close from
inside its own root.

## What slm-learning produced

**Spec doc** (read this first):
`reports/research/trigger_skill_envelope_spec.md` — captures current
envelope shape, proposed envelope shape, where the writing happens
(gad CLI hook-runtime: PreToolUse / PostToolUse), what constitutes
a `trigger_skill`, the minimum change to populate it (1–3 specific
code locations), and one concrete acceptance test.

**Decision context:**
- `slm-learning-128` — skills must generate measurable learning
  signal or get shed.
- `slm-learning-129` — pressure is gated, not assumed.
- `slm-learning-166` — pressure formula v2 published; `w_skill = 0`
  pending this handoff landing.
- `slm-learning-167` — TRACE.json source-of-truth standard (related
  scoring discipline).

**Calibration evidence** (from
`reports/research/pressure_v2_calibration_corpus.json`, 2026-05-08):
without `s_skill`, the formula's J_SLM term separates good_action
from churn outcomes by +2.41pp on a 36-decision retroactive
backread. **Adding s_skill is expected to sharpen this**, especially
on the harm cases (e.g. premature-promotion patterns like
`slm-learning-110`) that J_SLM alone cannot distinguish from
good_action.

## Acceptance test

After this handoff lands, running:

```
python scripts/research/skill_pressure_correlation.py
```

from inside `slm-learning` should report `total_invocations > 0`
with at least one populated `skill_id` per event. Currently it
returns 0.

## Where the change goes

Per the spec, the canonical source is **MagicbornStudios/get-anything-done**
(vendored at `custom_portfolio/vendor/get-anything-done/` in the
sibling monorepo). The compiled binary at
`C:\Users\benja\AppData\Local\Programs\gad\bin\gad.exe` is what
emits the provenance events. The PreToolUse / PostToolUse hooks are
where the `trigger_skill` field needs to be added to the emitted
JSONL row.

## Related cross-project DX gap surfaced

While writing this handoff I noticed the gad `snapshot` command
shows the local project's open handoffs (`gad handoffs list
--projectid <id>`), but **does not show cross-project handoffs that
WERE FILED FROM other roots into this root's queue**. That means
when the monorepo team opens their own session and runs
`gad snapshot --projectid <their-project>`, this handoff is
invisible to them unless they explicitly walk our queue.

**Feature request** (gad-note `2026-05-08-snapshot-cross-team-status`
captured): `gad snapshot` should surface cross-project handoffs
where `recipient` matches the current session's projectid OR a
team alias. Until then, cross-project handoffs require the
recipient team to be told "look in slm-learning's handoffs queue"
out-of-band — which is exactly the kind of thing handoffs are
supposed to eliminate.

## Non-blocking

This is **not blocking** any slm-learning experiment. The morphism
prototype (slm-learning-170, slm-learning-171) and the scaling-
proof charter (slm-learning-164) all run with `w_skill = 0`
without issue. This handoff just unblocks `s_skill` becoming a
real load-bearing term in pressure-v2 calibration once the
monorepo team has cycles.

— Dr. Stein, 2026-05-08
