# Phase 05 — Continuous Local Delta Lab

## Status

`planned` (depends on phase 04 substrate)

## Goal

Stand up the **gated, candidate-only** continuous training loop on
the 1660 Ti per decision `slm-learning-051`. The lab produces
candidate adapters and prompt deltas continuously; **promotion is
manual and gated by the council**. No automatic merge, no automatic
hot-swap.

## Why this phase exists

Per decision `slm-learning-051`: continuous training creates
candidates; evals decide; humans/promoters merge; rollback is
mandatory. The earlier framing of "nightly tiny LoRA → TIES-merge
into running adapter → hot-swap" was too close to automatic weight
mutation and was explicitly softened by the council (ChatGPT 5.5
critique + user accept, 2026-05-06).

## Architecture

```
[ data sources ] ──→ [ scheduler ] ──→ [ trainer ] ──→ [ candidate dir ] ──→ [ evaluator ] ──→ [ promotion verdict ]
                            │                                                          │
                            └─────────── wakes at intervals ─────────────────┐         │
                                                                              ↓         ↓
                                                          [ corpus delta watcher ]   [ Verifier + Critic ]
```

### Components (1 file per concern)

- `scripts/lab/scheduler.py` — wakes at intervals, picks the next
  candidate experiment from the queue.
- `scripts/lab/trainer.py` — wraps `18_stage25_finetune.py` for
  candidate runs. Always `save_strategy: no` for the base; saves
  adapter + manifest to the candidate dir.
- `scripts/lab/evaluator.py` — runs the eval matrix
  (`eval_benchmark_matrix.py`) on the new candidate.
- `scripts/lab/verifier.py` — applies the Verifier soul rubric:
  evidence tier, baseline match, sample size, regression check.
- `scripts/lab/critic.py` — applies the Critic soul rubric:
  failure-mode pre-mortem, untested invariants, skeleton traps.
- `scripts/lab/queue.py` — the experiment queue (YAML or JSONL).
- `experiments/candidates/<run-id>/` — candidate directory with
  `adapter/`, `eval/`, `manifest.json`, `verdict.json`.

### Promotion gate

A candidate moves from `experiments/candidates/` to a published
adapter only when ALL of:

1. eval scores meet or beat the relevant baseline on the relevant
   shape (no regression on other shapes by more than 5 percentage
   points)
2. Verifier verdict = `verified` at evidence tier T2 or higher
3. Critic verdict = `recommend: ship` (no `blocking: true` failure
   modes)
4. Human stamp via `gad decisions add slm-learning-NNN --title
   "Promote candidate <run-id>"`

Counter-rotation per `slm-learning-058`: if the same candidate fails
promotion three times across iterations, it is interred (skeleton)
or explicitly retired with a council decision.

## First targets (per slm-learning-051)

Priority order:

1. **Routers** — small classifier deltas trained on routing-decision
   traces from `scripts/router/runtime_select.py`. Cheap, fast, high
   leverage. Updates per slm-learning-039 (rule router → ML router).
2. **Rerankers** — small adapter that scores candidate outputs from a
   larger model. Useful for two-tier routing per slm-learning-036.
3. **Judges** — soul-aligned eval scorers (Dr. Stein output schema
   conformance, common-dream alignment). Connects to
   `slm-learning-060` constitution-impact arm C.
4. **Prompt deltas** — small soft-prompt adapters (prompt-tuning,
   ~0.001% trainable). Lowest VRAM, fastest iteration.
5. **IA³ / BitFit** — tiny parameter-efficient adapters for narrow
   behavior shifts.
6. **Small candidate adapters** — full LoRA on narrow corpora (e.g.
   doc-verifier specialist when corpus is bootstrapped per
   `synth_doc_verifier_pairs.py`).

LoRA/TIES merge experiments are explicitly an experimental branch
that requires its own PLAN.md before any merge or hot-swap. They
are NOT in scope for the first wave.

## Task breakdown

| ID | Goal | Status |
|---|---|---|
| SL-T-05-01 | Author the experiment queue schema (YAML format, slot for hypothesis, baseline, evidence tier target) | planned |
| SL-T-05-02 | Implement `scripts/lab/scheduler.py` — picks next, marks running, writes lock file | planned |
| SL-T-05-03 | Implement `scripts/lab/evaluator.py` — runs benchmark matrix, writes verdict.json | planned |
| SL-T-05-04 | Implement `scripts/lab/verifier.py` — Verifier soul rubric applied to candidate | planned |
| SL-T-05-05 | Implement `scripts/lab/critic.py` — Critic soul rubric applied to candidate | planned |
| SL-T-05-06 | First end-to-end candidate run: a router delta on real routing traces | planned |
| SL-T-05-07 | Integration with promotion-gate.md (slm-learning-032) — candidate enters gate, exits with stamp or interment | planned |
| SL-T-05-08 | Overnight queue — automated wake-and-pick on a schedule (cron / Windows scheduled task) | planned |

## Acceptance criteria

- A candidate can be queued, trained, evaluated, and verdicted without
  human intervention.
- A verdict either records `promote: true` (with all evidence) or
  `promote: false` (with the failure path), never `unknown`.
- Three candidates have run end-to-end with all four verdict stages
  populated.
- `gad snapshot` lists pending candidates, last verdict, and queue
  depth.
- Zero auto-merges. The phase passes only if the gate is unbroken.

## Risk register (from Critic)

- **Confounding through env drift**: candidate trained yesterday vs
  today is on the same base model but the eval set / harness may have
  shifted. Mitigation: pin eval harness commit per candidate.
- **VRAM thrash**: scheduler + trainer + evaluator running concurrently
  on a 6GB GPU OOMs. Mitigation: one GPU job at a time, hard lock.
- **Skeleton-revival in the queue**: queue picks a candidate variant
  that was already retired. Mitigation: queue checks the museum/zoo
  before scheduling.
- **Eval set staleness**: a candidate scores well on eval but fails in
  real artifact use. Mitigation: artifact-eval slice (a small set of
  real GAD tasks evaluated by `gad-verify-phase`).

## References

- decisions `slm-learning-032` (promotion gate), `slm-learning-051`
  (Continuous Local Delta Lab)
- soul: `narrative/souls/dr-stein.md` (proposes), `verifier.md`
  (verifies), `critic.md` (stress-tests), `archivist.md` (records)
- concern: `.planning/concerns/constitution-impact.md` — the
  experiment that drives the early candidates
