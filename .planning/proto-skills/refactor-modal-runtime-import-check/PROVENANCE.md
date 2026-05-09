---
candidate_slug: refactor-modal-runtime-import-check
source_phase: 04
pressure_score: 0.80
created_on: 2026-05-09
created_by: create-proto-skill
status: complete
---

Source candidate at `.planning/candidates/refactor-modal-runtime-import-check/CANDIDATE.md`.
Evolution turn 1 of slm-learning post-decision-202 batch (2026-05-09 UTC).
Pressure source: refactor wave 1 (commit f8bd6bb) extracted shared morphism
modules into `modal_app/morphism_layers.py` + `morphism_insertion.py`.
Local smoke test passed bit-identical for all 3 variants. Modal runtime
crashed with `ModuleNotFoundError: No module named 'modal_app'` because
`train_morphism.py`'s image config did not have
`.add_local_python_source('modal_app')`. eval_morphism.py already had it,
so eval would have worked — but train was the bottleneck. Cost: ~$0.10
in failed-container-init time, plus operator chase time. HIGH priority
because every Modal-app-package refactor is at risk.
