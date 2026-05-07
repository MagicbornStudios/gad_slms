# Wiring opencode → our model

Per `slm-learning-104` (ASAP launch timeline), the launch threshold is:
**Day 14: operator runs at least one real PR through
opencode-using-ours-via-modal-vllm.**

This doc is the recipe to make that work once `modal_app/serve_vllm.py`
is deployed.

## Prerequisites

1. `modal deploy modal_app/serve_vllm.py` — deploys the VLLMEngine class. Modal returns a stable URL like:
   ```
   https://b2gdevs--slm-learning-vllm-vllmengine-chat-completions.modal.run
   ```
2. Hit `/health` to confirm the engine loaded:
   ```bash
   curl https://b2gdevs--slm-learning-vllm-vllmengine-health.modal.run
   ```
   Should return JSON with `status: ok` + base_model + adapter info.

## Option 1: opencode via custom OpenAI provider

In `~/.config/opencode/opencode.json` (or per-project
`./.opencode/opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": "allow",
  "providers": {
    "gad-modal": {
      "type": "openai",
      "baseURL": "https://b2gdevs--slm-learning-vllm-vllmengine-chat-completions.modal.run/v1",
      "apiKey": "not-required",
      "models": {
        "dr-stein-cli-v2": {
          "name": "Dr Stein CLI v2 (1.5B + adapter)"
        }
      }
    }
  }
}
```

Then run opencode with our model:

```bash
opencode run --model gad-modal/dr-stein-cli-v2 "Take a note that the build is broken on Windows."
```

## Option 2: claude-cli via env override

Claude Code supports a custom base URL:

```bash
ANTHROPIC_BASE_URL=https://b2gdevs--slm-learning-vllm-...modal.run \
  claude -p "Take a note that the build is broken on Windows."
```

Note: claude-cli expects Anthropic-style endpoints; our vLLM speaks
OpenAI-shape. May need a tiny adapter shim. Use opencode (Option 1)
as the primary path.

## Option 3: direct HTTP (the matrix runner)

Add a row to `scripts/eval/models_to_compare.json`:

```json
{
  "model_id": "ours-via-modal-v2",
  "kind": "local",
  "endpoint": "https://b2gdevs--slm-learning-vllm-vllmengine-chat-completions.modal.run",
  "served_name": "dr-stein-cli-v2",
  "cost_usd_per_1k_tokens_out": 0.0,
  "tier": "ours-served",
  "notes": "Our v2 adapter served via Modal vLLM — the row that proves we exist on the leaderboard"
}
```

Then:

```bash
python scripts/eval/run_comparative_matrix.py \
  --benchmark gad_tools_v2 \
  --model ours-via-modal-v2 \
  --no-frontier \
  --out experiments/runs/comparator_v2_via_modal.json
```

## Cost expectations

vLLM container scale-to-zero is enabled. Idle = $0. Active L4 = $0.80/hr.
Realistic monthly at light dev usage: ~$3-15.

For heavier benchmark sweeps (HumanEval n=164 + MBPP n=974), the
container stays warm during the sweep — assume ~$1-2 per full sweep.

## Adapter swapping

To serve a different adapter, override the engine params at deploy:

```python
# modal_app/serve_vllm.py — adjust DEFAULT_ADAPTER, DEFAULT_BASE
# OR deploy multiple instances:

@app.cls(...)
class VLLMEngineMath(VLLMEngine):
    base_model = "Qwen/Qwen2.5-1.5B-Instruct"
    adapter_id = "scrubster/dr-stein-colab-qwen15-math-5k"
    served_name = "dr-stein-math"
```

Future: a single engine that hot-swaps LoRA per-request based on
the served_model_name (vLLM supports multi-LoRA serving). That's
the S-LoRA pattern in `slm-learning-094`.

## Decision refs

- `slm-learning-094` composition strategy (this is the system-orchestration L5 piece)
- `slm-learning-104` ASAP launch timeline (Day 14 threshold)
- `slm-learning-105` hardware policy (serving on Modal not local)
