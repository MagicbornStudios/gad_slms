---
library_name: peft
base_model: Qwen/Qwen2.5-1.5B-Instruct
tags:
  - lora
  - peft
  - dr-stein
  - slm-learning
  - gad-cli
---

# scrubster/dr-stein-stage25-qwen15-instruct-v2

PEFT/LoRA adapter for `Qwen/Qwen2.5-1.5B-Instruct`, fine-tuned on the
slm-learning GAD-tool translation track.

- Trained on: 153 hand-curated `(instruction, gad CLI command)` pairs
- Adapter kind: lora (r=16, alpha=32)
- Target modules: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj
- Run name: `stage25_qwen15_instruct_v2`
- Compute: `local-cuda-0`

## Loading

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
model = PeftModel.from_pretrained(base, "scrubster/dr-stein-stage25-qwen15-instruct-v2")
```

## Notes

Stage 2.5 v2: same Qwen2.5-1.5B-Instruct base + bf16 (empirical winner per slm-learning-025) + LoRA r=16/alpha=32, but trained on the EXPANDED data set (gad_tool_pairs_v2.jsonl = 153 hand-curated seeds + 630 vocab-anchored pairs from a haiku-4-5 subagent grounded in the actual gad CLI surface). The v1 control hit 22/30 (73.3%) on GAD-tools but its 8 failures were systematic vocabulary errors — model invented commands that don't exist (`tasks mark`, `plan hydrate`, `goals status`). This run targets those gaps explicitly via vocab-anchored distillation per decision slm-learning-022 + 2026-05-05 takeaway. Predicted lift: 22/30 -> 26-28/30.

