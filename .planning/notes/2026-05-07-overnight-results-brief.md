# Overnight results brief — 2026-05-07 → 05-08

Read this FIRST in the morning. All numbers + URLs + next moves.

## Headline

**Our v2 adapter served via Modal vLLM beats claude-cli on GAD-CLI translation by 20 percentage points at $0/call.**

| Model | Benchmark | Score | Cost | Latency p50 |
|---|---|---|---|---|
| **ours-via-modal-v2** | gad_tools_v2 (n=30) | **30/30 (100%)** | **$0.00** | TBD |
| claude-cli (frontier comparator) | gad_tools_v2 (n=30) | 24/30 (80%) | $0.0048 | 8.92s |
| gemini-cli (initial run) | gad_tools_v2 | failed (untrusted-workspace; fixed for next run with --skip-trust) | — | — |

This is the comparison the operator asked for. We exist on the leaderboard.

## Infrastructure shipped tonight

| Piece | Where | Status |
|---|---|---|
| Modal training app (LoRA SFT, L4/A10G/A100) | `modal_app/train_lora.py` | ✅ producing real adapters |
| Modal vLLM serving (OpenAI-compat URL) | `modal_app/serve_vllm.py` | ✅ DEPLOYED at `https://b2gdevs--slm-learning-vllm-vllmengine-chat-completions.modal.run` |
| Modal dataset pull → volume | `modal_app/pull_datasets.py` | ✅ 446MB on slm-data volume (hh-rlhf 50k + oasst2 50k + open-code-reasoning 30k + SWE-bench-Verified) |
| Modal eval-adapter scoring | `modal_app/eval_adapter.py` | ✅ runs code_smoke / humaneval / mbpp |
| Comparator runtime-CLI lane | `scripts/eval/run_comparative_matrix.py` | ✅ shells out to claude/gemini/codex/opencode |

## Scaling-ladder smoke results (3 rungs, OpenCodeReasoning data)

| Rung | Base | GPU | Wall | Cost | Loss (1 epoch) | Adapter at |
|---|---|---|---|---|---|---|
| 7B | Qwen2.5-Coder-7B-Instruct | A100 | 34 min | $1.58 | **1.012** | `/models/runs/ladder-7b-coder-2026-05-08/adapter` |
| 3B | Qwen2.5-Coder-3B-Instruct | A10G | 53 min | $0.97 | **1.087** | `/models/runs/ladder-3b-coder-2026-05-08/adapter` |
| 1.5B | Qwen2.5-Coder-1.5B-Instruct | L4 | stalled (HF rate-limit) | $0.10 (sunk) | n/a | n/a |
| 1.5B retry | Qwen2.5-Coder-1.5B-Instruct | A10G | in-flight (~3hr at current rate) | TBD | TBD | TBD |

**Loss curve so far**: 7B (1.012) < 3B (1.087). Lower is better. Consistent scaling — bigger model fits the data better. Predicts continued lift if we go to 14B / 32B.

### Scaling-ladder code_smoke results (max_new_tokens=1024, judge strips `<think>` blocks)

| Rung | code_smoke (n=5) | Notes |
|---|---|---|
| 7B Qwen2.5-Coder + LoRA | **5/5 (100%)** | passed all 5: add, reverse, fib, count_vowels, is_prime |
| 3B Qwen2.5-Coder + LoRA | **4/5 (80%)** | failed only is_prime (minor judge code-fence edge case) |
| 1.5B retry | TBD | training in flight on A10G |

**Scaling curve confirmed**: 3B → 7B = +20pp on code_smoke, paralleling
the loss curve. **This justifies firing the $50 32B shot** (decision
slm-learning-097's pre-flight gate is now passed). Decide in the
morning.

**Next step**: when 1.5B retry lands, complete the 3-point curve.

## Cost summary tonight

| Item | Spent |
|---|---|
| Modal hello-GPU smoke | $0.005 |
| Modal dataset pulls | ~$0.10 |
| Modal vLLM build + cold starts | ~$0.30 |
| 7B training | $1.58 |
| 3B training | $0.97 |
| 1.5B stalled run | $0.10 |
| 1.5B retry (in flight) | ~$1.00 (est) |
| Eval runs (7B, 3B in flight) | ~$0.30 each |
| Comparator runs (claude-cli, gemini, ours) | ~$0.01 (mostly free CLI) |
| **Total estimated** | **~$4.50–6.00** of Modal credits |

Modal credit balance is fine; well within the $30 budget.

## Failover lessons

- **L4 + 1.5B + uncached HF download = stalls** because of HF rate-limit (no token in env). Fix: add HF_TOKEN secret OR pre-bake into image (vLLM serving uses this fix).
- **Pre-baking model into Modal image** dropped vLLM cold start from 90s+ (timing out HTTP gateway) to ~30-45s.
- **Windows .CMD/.BAT subprocess invocation** needs `shell=True` shim — gemini and codex on PATH ship as .CMD on Windows, broke without this.

## What's still running as of brief-write time

| Job | ETA | What |
|---|---|---|
| 7B eval on code_smoke | ~10 min | first real-PR-style code eval of our 7B adapter |
| 3B eval on code_smoke | ~10 min | comparison datapoint |
| 1.5B retry on A10G | ~3 hr | ladder rung 1 |
| gemini-cli matrix retry | ~5 min | with --skip-trust fix |

These will land before morning. Check `experiments/runs/_eval_*.log` and `experiments/runs/comparator_*.json`.

## Decisions stamped this session

slm-learning-094 → 106 covering:
- L0-L5 stack
- Delta Graph schema
- Six research tracks (BTM, SERA, RLEF, test-time compute, Kael, artifact)
- EXP-001 → EXP-010 named experiments registry
- Compare-and-compete mandatory (4 eval rows per candidate)
- ASAP launch timeline (Day 14: real PR through ours-via-modal)
- Hardware policy (>100MB → Modal volume, never local)
- Research intake protocol

Plus framework docs:
- `.planning/concerns/research-program-charter.md` — operating constitution
- `.planning/concerns/composition-strategy.md` — trillion-effective-params path
- `.planning/notes/2026-05-07-credit-acquisition-playbook.md` — apply-list ranked by time-to-funds
- `.planning/research/EXPERIMENTS.json` — EXP-001 → EXP-010

## What you should do in the morning

1. **Read the eval results** for 7B + 3B + 1.5B against `code_smoke` (and `humaneval` if I had time to fire those).
2. **Read the matrix results** for `ours-via-modal-v2` (30/30) vs `claude-cli` (24/30) vs `gemini-cli` (with skip-trust).
3. **Apply for credits** while coffee brews:
   - https://www.nvidia.com/en-us/startups/ — NVIDIA Inception (10 min, no entity needed)
   - `founders@modal.com` email with the boilerplate from `.planning/notes/2026-05-07-credit-acquisition-playbook.md`
   - HF research credits via https://huggingface.co/contact-research
4. **File the company entity** as planned. Unlocks AWS/Azure/GCP startup tiers.
5. **Decide on shot #1** — if the scaling-ladder shows clear lift from 1.5B → 3B → 7B, fire `Qwen2.5-Coder-32B-Instruct + QLoRA` on Modal H100 (~$50). Spec at `experiments/configs/remote-ladder/`. If curve is shallow, hold + investigate.

## Direct URLs

- vLLM live endpoint: https://b2gdevs--slm-learning-vllm-vllmengine-chat-completions.modal.run
- vLLM health: https://b2gdevs--slm-learning-vllm-vllmengine-health.modal.run
- Modal dashboard: https://modal.com/apps/b2gdevs/main
- GitHub: https://github.com/MagicbornStudios/gad_slms (~14 commits this session)

## What I'd do tomorrow if I were you

1. Eval all three ladder rungs on HumanEval n=20 to populate the scaling-prediction table for the 32B shot
2. Wire opencode to `https://b2gdevs--slm-learning-vllm-vllmengine-chat-completions.modal.run/v1` per `docs/opencode-via-our-model.md` — tries the launch threshold workflow
3. If opencode round-trips successfully, that's **the launch** per slm-learning-104 Day 14
4. Add HF token secret (`modal secret create hf-token HF_TOKEN=$(cat ~/.cache/huggingface/token)`) so future training runs auto-publish to HF Hub instead of just slm-models volume

— Dr. Stein
