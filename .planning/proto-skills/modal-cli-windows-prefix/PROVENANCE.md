---
candidate_slug: modal-cli-windows-prefix
source_phase: 04
pressure_score: 0.85
created_on: 2026-05-09
created_by: create-proto-skill
status: complete
---

Source candidate at `.planning/candidates/modal-cli-windows-prefix/CANDIDATE.md`.
Evolution turn 1 of slm-learning post-decision-202 batch (2026-05-09 UTC).
Pressure source: bit slm-learning twice in session 2026-05-08 — first as
encoding-only failure (5 ephemeral apps with 0 tasks queued), then as
MSYS path-translation failure (6 evals trained but evaluation step
crashed with HFValidationError on mangled `--adapter-id` argument).
HIGH priority because every Modal-using project on Windows hits this.
