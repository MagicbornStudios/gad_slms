# Training Queue

Per decision `slm-learning-081`: slm-learning is a training factory,
not a folder of experiments. Every training job lives as a JSON spec
that walks through five buckets:

```
queue/
  pending/        ← created, not yet picked
  running/        ← claimed by a worker, training in progress
  evaluated/      ← training done, eval done, verdict.json present
  promoted/       ← council stamped, candidate is now staging or canonical
  rejected/       ← failed gate or interred as skeleton
```

## Job spec schema

```json
{
  "job_id": "<unique slug, e.g. doc-verifier-r8-2026-05-06>",
  "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
  "adapter_type": "lora",
  "rank": 8,
  "alpha": 16,
  "dataset": "data/eval/doc_verifier_train.reshaped.jsonl",
  "holdout": "data/eval/doc_verifier_holdout.reshaped.jsonl",
  "evals": ["doc_verifier_f1", "json_validity", "gad_tools"],
  "compute_target": "local-1660ti",
  "config_path": "experiments/configs/stage25_qwen15_doc_verifier_r8.yaml",
  "promotion_policy": "manual",
  "evidence_tier_target": "T2",
  "decision_refs": ["slm-learning-051", "slm-learning-081"],
  "created_at": "2026-05-06T00:00:00Z",
  "claimed_by": null,
  "claimed_at": null,
  "completed_at": null,
  "verdict_path": null
}
```

## compute_target enum

| Target | What it is | Cost |
|---|---|---|
| `local-1660ti` | Tier 0: 6GB GTX 1660 Ti, on this machine | $0 (sunk hardware) |
| `remote-l4` | Tier 1: HF Jobs L4 24GB | ~$0.80/hr |
| `remote-a10g` | Tier 1: HF Jobs A10G | ~$1.00/hr |
| `remote-l40s` | Tier 2: HF Jobs L40S 48GB | ~$1.80/hr |
| `remote-a100` | Tier 2: HF Jobs A100 80GB | ~$2.50/hr |
| `remote-h200` | Tier 2: HF Jobs H200 | ~$5.00/hr |

Per `slm-learning-080`: 1660 Ti is for tiny continuous deltas only.
Larger ranks / bigger bases / multi-task runs go remote.

## promotion_policy enum

| Policy | Behavior |
|---|---|
| `manual` | every transition requires operator stamp via `scripts/delta/promote_atomic.py` |
| `auto-staging` | low-blast-radius specialists may auto-move from candidate → staging on numeric gate pass; never to canonical |
| `refused` | candidate is research-only, never promoted |

Per `slm-learning-082`: main coder NEVER auto-promotes. `auto-staging`
is reserved for routers / rerankers / judges / doc-verifier per
`slm-learning-051` first-targets list.

## Lifecycle

```
operator OR daemon writes <job_id>.json -> pending/
runner picks oldest pending, atomic rename -> running/<job_id>.json
runner shells out to scripts/delta/train_lora_delta.py with --manifest
runner completes, writes verdict, atomic rename -> evaluated/<job_id>.json
operator OR daemon (per promotion_policy) reviews verdict
operator stamps -> promoted/<job_id>.json + checkpoint registry update
OR
verdict refuses -> rejected/<job_id>.json + skeleton interment if ladder-end

state machine is enforced via fs.rename atomicity (same as handoffs)
```

## What's NOT in the queue (deliberate scope cap)

- Inference jobs (the queue is for training only)
- Eval-only re-runs (those go via `scripts/post_multitask_eval_queue.sh`)
- Dataset ingest (telemetry ingest runs separately per
  `scripts/ingest_gad_telemetry.py`)
- Skeleton sweeps (per `.planning/concerns/skeleton-system.md`)
