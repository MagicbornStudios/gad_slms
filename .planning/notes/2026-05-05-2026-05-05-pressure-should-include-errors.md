# Errors + unknown-task signal should weight into evolution pressure (framework-level)

User insight 2026-05-05 21:00 after watching this session burn 4 OOMs + 2 segfaults + 3 silent-fail bugs + a falsified hypothesis: every unsolved error or unknown-task IS a debt the project owes itself, and the pressure system should surface that.

Currently pressure aggregates:
- Operational signals (active phases, in-progress tasks)
- Evolution signals (skill candidates, shed flags)

Missing:
- ERROR pressure: open .planning/errors/* + recently-failed runs (rc != 0) + verify-phase failures
- UNKNOWN-TASK pressure: tasks marked blocked, todos with 'how do we' phrasing, debug skill invocations that didn't terminate cleanly

Concrete proposal:
- gad-statusline.js reads .planning/errors/ count + recent failed-task count (last 24h) and adds an error-pressure contribution to the unified pressure number
- New CLI: gad pressure breakdown shows the four contributions (ops / evolution / errors / unknowns)
- Decision threshold: when error-pressure dominates, dispatcher should route to debug-skill or pause new-feature work

Why this matters for slm-learning specifically: in this session alone we had 4 VRAM OOMs + 2 driver segfaults + 1 catastrophic forgetting empirical reversal + 1 upload_folder silent stall — every one of those is a 'how do we make this not happen again' that's currently invisible to the pressure scale. We solved them in the moment, but the operator can't see how MUCH unsolved-stuff debt is accumulating across sessions.

This is a framework-level GAD improvement, not slm-learning-internal. Captured here because that's where the evidence is. Should be promoted to a framework backlog item and a phase plan for the gad CLI.
