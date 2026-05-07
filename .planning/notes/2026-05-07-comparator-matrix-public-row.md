# Public-benchmark row — 2026-05-07

Aggregated from `experiments/runs/_eval_*_n164.log`. Per decision `slm-learning-103` this is the public-leaderboard row of the comparator matrix; pair with the frontier-comparator, owned-domain, and lineage rows before promoting any candidate.

## Scores (n=164 each)

| Model | HumanEval | MBPP | Notes |
|---|---|---|---|
| 7B coder LoRA | running | running | Qwen2.5-Coder-7B-Instruct + LoRA r=16 on OpenCodeReasoning n=5000, 1 epoch, A100 (training) |
| 7B base (no LoRA) | running | running | Qwen2.5-Coder-7B-Instruct base — control row to measure LoRA delta |
| 3B coder LoRA | running | running | Qwen2.5-Coder-3B-Instruct + LoRA r=16 same recipe as 7B |

## LoRA delta vs base (HumanEval + MBPP combined)


## Lineage (per slm-learning-100 Delta Graph schema)

| Model | base | parents | rank | dataset | training | adapter | manifest |
|---|---|---|---|---|---|---|---|
| 7B coder LoRA | Qwen2.5-Coder-7B-Instruct | base | 16 | OpenCodeReasoning n=5000 | 1 epoch, lr=2e-4, A100 34min ($1.58) | `/models/runs/ladder-7b-coder-2026-05-08/adapter` | `MANIFEST.json` |
| 3B coder LoRA | Qwen2.5-Coder-3B-Instruct | base | 16 | OpenCodeReasoning n=5000 | 1 epoch, lr=2e-4, A10G 53min ($0.97) | `/models/runs/ladder-3b-coder-2026-05-08/adapter` | `MANIFEST.json` |

## Frontier comparator (claude-cli on owned-domain)

Existing data from `experiments/runs/comparator_*_gad_tools_v2.json`:

| Model | gad_tools_v2 (owned domain) | Cost |
|---|---|---|
| ours-via-modal-v2 | 30/30 (100.0%) | $0.00 |
| claude-cli (frontier) | 24/30 (80.0%) | $0.0048 |

**Owned-domain win on `gad_tools_v2`: +20pp over claude-cli at $0/call.** The public-benchmark row above complements this with the standard coder benchmarks.

## Decision refs

- `slm-learning-094` — composition-of-specialists path
- `slm-learning-097` — two-shot $50 discipline (32B shot gate)
- `slm-learning-100` — Delta Graph schema
- `slm-learning-103` — compare-and-compete mandatory (4 rows per candidate)
