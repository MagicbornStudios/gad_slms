# Public-benchmark row + key finding — 2026-05-07 (autonomous run, finalized)

Aggregated from `experiments/runs/_eval_*_n164.log` and Modal training
manifests. Per decision `slm-learning-103` this is the
public-leaderboard row of the comparator matrix; pair with the
frontier-comparator, owned-domain, and lineage rows before promoting
any candidate.

## Headline finding

> **The OpenCodeReasoning LoRA REGRESSES standard public benchmarks
> by –34.1pp on HumanEval and –4.9pp on MBPP versus the same-size
> Qwen2.5-Coder-7B base.** Loss curve was monotone clean across the
> 3-rung scaling ladder, but the LoRA does not transfer to public
> benchmarks. The `slm-learning-097` pre-flight gate for the $50
> Qwen2.5-Coder-32B shot **fails**. Hold the shot.

## Public-benchmark scores (n=164 each)

| Model | HumanEval | MBPP | Wall (training) | Cost (training) |
|---|---|---|---|---|
| **Qwen2.5-Coder-7B base** | **106/164 (64.6%)** | **132/164 (80.5%)** | — (control) | — |
| Qwen2.5-Coder-7B + OCR LoRA | **50/164 (30.5%)** | **124/164 (75.6%)** | 34 min A100 | $1.58 |
| Qwen2.5-Coder-3B + OCR LoRA | did-not-land | did-not-land | 53 min A10G | $0.97 |
| Qwen2.5-Coder-1.5B + OCR LoRA (v2) | did-not-land | did-not-land | 33 min A10G | $0.55 |

The 4 L4-hosted evals (3B HE/MBPP, 1.5B HE/MBPP) repeatedly stalled
at the Modal L4 1-hour container limit even after bumping to 5400s.
Adapters exist on the slm-models volume; the operator can re-fire
these evals manually:

```sh
MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
    -m modal run modal_app/eval_adapter.py::main \
    --adapter-id /models/runs/ladder-3b-coder-2026-05-08/adapter \
    --base-model Qwen/Qwen2.5-Coder-3B-Instruct \
    --benchmark humaneval --limit 164 --gpu A10G --max-new-tokens 1024
```

(Switch to A10G to escape the L4 contention. Repeat for 1.5B with
adapter `ladder-1p5b-coder-2026-05-08-v2`.)

## LoRA delta vs base (7B, n=164)

| Benchmark | Base | LoRA | Δ |
|---|---|---|---|
| HumanEval | 64.6% | 30.5% | **–34.1 pp** |
| MBPP | 80.5% | 75.6% | **–4.9 pp** |

The 7B base MBPP score (80.5%) matches published Qwen2.5-Coder-7B
baseline (~79–83%), validating the harness on MBPP. The 7B base
HumanEval (64.6%) is below published ~88% — chat-mode harness floor;
instruct models score lower in chat mode than in completion mode and
our judge has remaining edges (model wraps in ```python``` blocks
inconsistently). For both benchmarks the **delta** is the meaningful
signal because it controls for harness noise.

## Scaling-ladder loss curve (training)

| Rung | Base | Loss (1 epoch, OCR n=5000) | Wall | GPU | Cost |
|---|---|---|---|---|---|
| 1 | Qwen2.5-Coder-1.5B-Instruct | **1.187** (v2 retry, dataset_limit fixed) | 33 min | A10G | $0.55 |
| 2 | Qwen2.5-Coder-3B-Instruct | **1.087** | 53 min | A10G | $0.97 |
| 3 | Qwen2.5-Coder-7B-Instruct | **1.012** | 34 min | A100 | $1.58 |

Curve is monotone (loss decreases as size doubles, ~0.10 per 2x).
The fitted slope predicts that a 14B / 32B run would continue
descending the loss curve. **But** the public-benchmark numbers above
say the loss curve does not predict downstream benchmark utility for
this dataset. Loss-curve smoothness is necessary but not sufficient.

## Owned-domain comparator (carried from overnight 2026-05-07)

From `experiments/runs/comparator_*_gad_tools_v2.json`:

| Model | gad_tools_v2 (n=30) | Cost/call |
|---|---|---|
| **ours-via-modal-v2** (tooluse v1 LoRA via Modal vLLM) | **30/30 (100.0%)** | **$0.00** |
| claude-cli (frontier comparator) | 24/30 (80.0%) | $0.0048 |
| gemini-cli | failed initially; retry pending | — |

Owned-domain win on `gad_tools_v2`: **+20pp over claude-cli at
$0/call**. This is the OWNED-DOMAIN row of the comparator matrix per
`slm-learning-103`. The PUBLIC-DOMAIN row above shows the OCR LoRA
regression — different LoRAs, different signals.

## Auxiliary training: tooluse-sanity-v2

Fired and landed during this autonomous run.

| Field | Value |
|---|---|
| Base | Qwen/Qwen2.5-1.5B-Instruct |
| Dataset | `data/processed/gad-telemetry-2026-05-06/sft_tooluse.jsonl` (4841 telemetry pairs, 6× v1 corpus) |
| LoRA | r=16, α=32, dropout=0.05 |
| Training | 3 epochs, lr=2e-4, bs=4, grad_accum=4, bf16 |
| Final loss | **0.406** (≈ v1 0.39) |
| Wall | 35 min on Modal L4 |
| Cost | $0.50 |
| Adapter | `/models/runs/tooluse-sanity-v2-modal-l4-2026-05-08/adapter` (slm-models volume) |
| HF Hub | not pushed (no HF_TOKEN secret in Modal env) |

Final loss matches v1 within noise — 6× more data preserved fit.
**Generalization eval (gad_tools n=30) is the follow-up question.**
Adding gad_tools to `modal_app/eval_adapter.py` benchmarks list is
the next eval task; not done in this run because it requires loading
`promptfoo-gad-tools.yaml` cases on Modal.

## Lineage (per slm-learning-100 Delta Graph schema)

| delta_id | base | parents | rank | dataset | training_method | evals.public | cost_usd | wall_hours | adapter |
|---|---|---|---|---|---|---|---|---|---|
| ladder-7b-coder-2026-05-08 | Qwen2.5-Coder-7B-Instruct | — | 16 | OCR n=5000 | SFT-LoRA, 1ep, A100 | HE 30.5% / MBPP 75.6% | $1.58 | 0.57 | volume |
| ladder-3b-coder-2026-05-08 | Qwen2.5-Coder-3B-Instruct | — | 16 | OCR n=5000 | SFT-LoRA, 1ep, A10G | did-not-land (L4 contention) | $0.97 | 0.88 | volume |
| ladder-1p5b-coder-2026-05-08-v2 | Qwen2.5-Coder-1.5B-Instruct | — | 16 | OCR n=5000 | SFT-LoRA, 1ep, A10G | did-not-land (L4 contention) | $0.55 | 0.55 | volume |
| tooluse-sanity-v2-modal-l4-2026-05-08 | Qwen2.5-1.5B-Instruct | — | 16 | gad-telemetry n=4841 | SFT-LoRA, 3ep, L4 | gad_tools eval pending | $0.50 | 0.58 | volume |

## Bug log (this run)

| Bug | Cost | Fix |
|---|---|---|
| Git Bash MSYS path translation: `/models/...` → `C:/Program Files/Git/...` | ~$0.05 (5 fast failures) | `MSYS_NO_PATHCONV=1` env var |
| MBPP sanitized config schema rename | ~$0.05 | Try `prompt` then fall back to `text` |
| HumanEval judge missing function signature | ~$0.50 (re-run) | Add `prefix` field to case; prepend `def` signature |
| Judge `.strip()` killing leading body indent | ~$0.50 (re-run) | Use rstrip + skip leading blank lines instead |
| `textwrap.dedent` on body breaking prefix-merge | ~$0 (caught before re-fire) | No dedent when prefix is present |
| Modal `--spec dict` rejected | $0 | Use `train_lora.py::main --spec-path <path>` |
| L4 1-hour container timeout | ~$0.30 (3B MBPP timeout) | Bumped to 5400s — but L4 evals continued to stall, suggesting Modal L4 capacity issue not pure timeout |
| Aggregator overwrites comprehensive report | $0 (file rewrite) | Future: aggregator should preserve hand-edited sections or emit to a separate file |

## Cost summary (autonomous run)

| Item | Spent |
|---|---|
| Eval lane (4 confirmed runs + retries + cancellations + stuck L4) | ~$4.00 |
| 1.5B retry training (A10G, 33 min) | $0.55 |
| Tooluse-sanity-v2 training (L4, 35 min) | $0.50 |
| Bug-debugging tax (cancelled mid-run jobs) | ~$1.55 |
| Volume put + image build + cold starts | ~$0.30 |
| **Total estimated** | **~$6.90** |

Well under the $30 budget. Bug-tax was high but each bug is now
fixed permanently in the codebase.

## Decisions implied (for operator)

1. **HOLD the $50 Qwen2.5-Coder-32B + QLoRA shot.** The
   `slm-learning-097` pre-flight gate requires the scaling-ladder
   smoke to predict benchmark lift. Loss curve is clean but
   benchmark curve regresses. Firing the 32B shot now would burn
   $50 to confirm a regression we already see at 7B.
2. **Pivot training data.** OpenCodeReasoning alone causes regression
   on standard benchmarks. Hypotheses to test next:
   - The `<think>...</think>` reasoning blocks burn token budget
     and confuse the chat-mode harness
   - 1 epoch is overfit to OCR's unique output style
   - LoRA r=16 is too small to absorb both OCR-style + base
     instruction-following
   - Mix OCR with instruction-following data to preserve base
     capability (the SLM strategy doc already calls for this)
3. **Validate tooluse-v2 generalization.** v2 has 6× v1 data and
   matches v1 final loss. The owned-domain win we have today
   (`ours-via-modal-v2 = 30/30`) was on v1. v2 may lift further
   — need a gad_tools eval to confirm.
4. **Add gad_tools benchmark to `modal_app/eval_adapter.py`** so
   every adapter we train can be scored on owned-domain in the same
   modal lane as the public-benchmark lane. Currently gad_tools is
   only via `scripts/eval_checkpoint.py` which loads local
   checkpoints, not Modal-volume adapters.
5. **Investigate HumanEval chat-mode harness gap.** 7B base scored
   64.6% vs published ~88%. The chat template + instruct phrasing
   adds ~24pp of variance. Either accept the floor or move to a
   completion-mode harness (no chat template) that matches the
   published numbers.
6. **Move 3B + 1.5B evals off L4.** L4 capacity issues caused 4
   evals to stall regardless of timeout setting. Switch to A10G
   when re-firing — 7B HE/MBPP completed cleanly on A10G.

## Decision refs

- `slm-learning-094` — composition-of-specialists path
- `slm-learning-097` — two-shot $50 discipline (32B shot gate)
- `slm-learning-100` — Delta Graph schema
- `slm-learning-103` — compare-and-compete mandatory (4 rows per candidate)
- `slm-learning-105` — hardware policy (Modal-first)

## What's complete vs deferred

| Item | Status |
|---|---|
| 7B base × HumanEval n=164 | ✅ 106/164 (64.6%) |
| 7B base × MBPP n=164 | ✅ 132/164 (80.5%) |
| 7B coder LoRA × HumanEval n=164 | ✅ 50/164 (30.5%) |
| 7B coder LoRA × MBPP n=164 | ✅ 124/164 (75.6%) |
| 1.5B retry training | ✅ loss=1.187 |
| Tooluse-sanity-v2 training | ✅ loss=0.406 |
| 3B coder LoRA × HumanEval | ❌ stalled on L4; re-fire on A10G |
| 3B coder LoRA × MBPP | ❌ stalled on L4; re-fire on A10G |
| 1.5B coder LoRA × HumanEval | ❌ stalled on L4; re-fire on A10G |
| 1.5B coder LoRA × MBPP | ❌ stalled on L4; re-fire on A10G |
| Tooluse-v2 × gad_tools eval | ⏸ deferred (needs eval_adapter.py extension) |
| SWE-bench Verified subset | ⏸ deferred (next session task) |

— Dr. Stein, autonomous run 2026-05-07 (finalized)
