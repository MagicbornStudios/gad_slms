# Mid-session status — 2026-05-07 evening

Companion to `.planning/notes/2026-05-07-next-session-handoff.md`. Captures
the deltas of THIS session so the next cold pickup can read this first
and skip the prior handoff.

## What landed this session

| Commit | What |
|---|---|
| 94ca7de | Doc-verifier r=16 augmented training fired + delta-train daemon contract files (prepare_dataset.py, train_delta.py, bench_candidate.py) |
| (D-4 commit) | scripts/benchmark/run_per_cohort.py per-cohort benchmark dispatcher |
| (paraphrase commit) | Stage-2 haiku paraphrase scaffold (paraphrase_doc_verifier_reasons.py) |
| 5bab01e | Doc-verifier r=16 augmented REGRESSED (F1 0.720→0.599); slm-learning-093 logged |
| (augmenter v2 commit) | 20-template haiku paraphrase pool + augmenter v2 + spec |

5 commits this session. All on master.

## Empirical findings

| Run | Result | Verdict |
|---|---|---|
| doc-verifier r=16 augmented v1 (442→592, uniform reason template ×150) | F1 0.599, unknown F1 0.167 | **REGRESSED** vs r=16 baseline |
| tool-use sanity v2 (4841 pairs, batch=2) | OOM on 6GB 1660Ti | trainer_failed; retry queued |
| tool-use sanity v2 retry (batch=1, grad_accum=16) | training as of mid-session | **in flight** |
| doc-verifier r=16 augmented v2 (442→592, 20 distinct reason templates) | spec written, queued | **PENDING** — will fire after tool-use v2 |

## Key decision: slm-learning-093 (locked)

Synthetic minority-class augmentation REQUIRES surface-form variance.
Uniform templates cause overfit to the template, not the underlying
concept. The framework table in `.planning/concerns/scaling-decisions.md`
is updated with this lesson.

## Queue state right now

```
pending/
  multitask-r32-remote-l40s-2026-05-06.json    (Tier 2 remote, $$$)
  planning-specialist-r16-2026-05-07.json      (blocked-on-deps: needs fresh telemetry export)
  doc-verifier-r16-augmented-v2-2026-05-07.json  (NEW — diverse reasons)
running/
  tooluse-sanity-v2-2026-05-07.json            (training as of mid-session)
evaluated/
  doc-verifier-r16-2026-05-06 (F1=0.720, candidate not promoted)
rejected/
  doc-verifier-r8-2026-05-06 (F1=0.533)
  doc-verifier-r16-augmented-2026-05-07 (F1=0.599 — uniform-template regression)
```

## Next session pickup order

1. Check tool-use v2 retry status — should be evaluated by morning. If
   passed: promote to canonical, retire v1. If failed: investigate
   (recipe issue or data shape mismatch).
2. Fire doc-verifier v2 retrain by running:
   `.venv-gpu/Scripts/python.exe scripts/queue/run_next.py --target local-cuda-0`
3. After it finishes, eval against the holdout:
   `.venv-gpu/Scripts/python.exe scripts/eval/eval_doc_verifier.py --candidate scrubster/dr-stein-stage25-qwen15-doc-verifier-r16-augmented-v2 --base Qwen/Qwen2.5-1.5B-Instruct --holdout data/eval/doc_verifier_holdout.reshaped.jsonl --out experiments/runs/stage25_qwen15_doc_verifier_r16_augmented_v2/eval_doc_verifier.json`
4. If v2 passes the gate (F1 >= 0.85): promote, retire candidate, log
   slm-learning-094.
5. If v2 still regresses: data-imbalance lane is exhausted; pivot to
   r=32 on original 442 corpus OR consider that doc-verifier may need
   a non-LoRA approach.

## Cross-Claude bridge ack outbound

Dropped at `custom_portfolio/.planning/handoffs/open/h-2026-05-07T19-45-00-global-bridge-ack-from-slm-learning.md`.
Ask: gad-monorepo Claude needs to run `gad telemetry export` with the
new handoffs adapter so the planning specialist's pair count grows
beyond 98.

## What still couldn't run this session

- Constitution arm C eval (GPU bound; deferred)
- Comparative matrix with frontier rows (requires API keys + cost
  approval; per closeout 18-50-34 the operator has them set in env
  but we'd want their explicit go before burning ~$3 in API tokens)
- Planning specialist remote L4 fire (gated on richer training pairs)
