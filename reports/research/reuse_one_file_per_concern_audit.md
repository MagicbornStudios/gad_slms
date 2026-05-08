# Reuse + One-File-Per-Concern Audit

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Decision refs:** slm-learning-196 (proposed below)

Per operator directive 2026-05-08: "make sure we have put all the
context, phases, areas of interest for research, findings, notes,
in all the appropriate places also that we are reusing code and
doing the one file per component and one file per concern"

A read-only Explore subagent scanned 15 files across morphism +
data + Modal + eval surfaces.

## Findings (6 duplications, 1 multi-concern violation)

| # | What | Locations | Canonical home | LOC saved |
|---|---|---|---|---|
| 1 | IdentityProjectionLayer / GatedBottleneckLayer / GatedResidualLayerC | `train_morphism.py`, `eval_morphism.py`, `local_init_smoke_test.py` (3 copies) | `modal_app/morphism_layers.py` | ~190 |
| 2 | HumanEval/MBPP loaders | `eval_adapter.py`, `build_0p5b_hard*.py`, `build_7b_hard*.py`, `build_retain_bank.py`, `build_delta_packets.py`, `frontier_comparator.py` (6 copies) | `scripts/data/_eval_dataset_loaders.py` | ~200 |
| 3 | `_judge` + `_strip_post_answer_pollution` | `eval_adapter.py`, `frontier_comparator.py` (2 copies, drift risk high) | `scripts/eval/_judge.py` | ~130 |
| 4 | `expand_with_identity` insertion logic | `train_morphism.py`, `eval_morphism.py` (inline), `local_init_smoke_test.py` (extracted) — 3 ways | `modal_app/morphism_insertion.py` | ~40 |
| 5 | Dataset extraction (`extract_canonical_target` / `extract_he_target` / `he_correction`) | `build_0p5b_hard*.py`, `build_7b_hard*.py`, `build_retain_bank.py`, `build_delta_packets.py`, `build_consolidation_mix.py` (5 copies) | `scripts/data/_extraction.py` | ~25 |
| 6 | `eval_adapter.py` multi-concern (~520 LOC: dataset I/O + judge + inference + persist + dispatch) | one file | split into `modal_app/eval_common.py` + slim `eval_adapter.py` | n/a |
| 7 (sup.) | `build_0p5b_hard_fn_norm_dataset.py` superseded by `build_delta_packets.py` | per-base hard scripts | deprecate; document migration | — |
| 8 (sup.) | `build_retain_mix_dataset.py` near-duplicate of `build_consolidation_mix.py` | both | reimplement retain_mix as thin wrapper around consolidation_mix | — |

**Total LOC eliminated by 1+2+3+4+5: ~585.**

## Prioritized refactor order

1. **#1 + #4 together** (morphism layers + insertion helper) — cohesive unit, ~230 LOC, low risk.
2. **#2** (HE/MBPP loaders) — biggest reach, ~200 LOC, low-med risk.
3. **#3** (judge/strip) — drift risk mitigation, ~130 LOC, medium risk (subtle prefix-handling logic).
4. **#5** (extraction helpers) — small but tidy, ~25 LOC, low risk.
5. **#6** (eval_adapter split) — last; depends on #2 + #3 landing first.

## Out of scope this session

The refactor is **deferred** until the 1.5B+retain canonical is
fully wired into the houses framework + Lane D serving. Refactor
during Lane B/D work, not before. Tracked here so it doesn't get
lost.

— Dr. Stein, reuse + one-file-per-concern audit, 2026-05-08
