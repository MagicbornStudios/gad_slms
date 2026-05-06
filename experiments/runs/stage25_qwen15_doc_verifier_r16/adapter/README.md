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

# scrubster/dr-stein-stage25-qwen15-doc-verifier-r16

PEFT/LoRA adapter for `Qwen/Qwen2.5-1.5B-Instruct`, fine-tuned on the
slm-learning GAD-tool translation track.

- Trained on: 153 hand-curated `(instruction, gad CLI command)` pairs
- Adapter kind: lora (r=16, alpha=32)
- Target modules: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj
- Run name: `stage25_qwen15_doc_verifier_r16`
- Compute: `local-cuda-0`

## Loading

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
model = PeftModel.from_pretrained(base, "scrubster/dr-stein-stage25-qwen15-doc-verifier-r16")
```

## Notes

Doc-verifier rank=16 retrain after r=8 underfit (F1 0.533 << 0.85 threshold per ChatGPT directive 2026-05-06). The r=8 model perfected json_validity (1.000) and learned verified/refuted (F1 0.77/0.83) but COMPLETELY MISSED the unknown class (F1 0.000) — 8/8 unknown cases mispredicted as verified or refuted. More capacity may let the model learn the unknown decision boundary.
Same recipe as r=8 (442 reshaped train pairs, 50 holdout) — only LoRA rank/alpha doubled. Per slm-learning-051: candidate-only.

