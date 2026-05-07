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

# scrubster/dr-stein-stage25-qwen15-doc-verifier-r16-augmented

PEFT/LoRA adapter for `Qwen/Qwen2.5-1.5B-Instruct`, fine-tuned on the
slm-learning GAD-tool translation track.

- Trained on: 153 hand-curated `(instruction, gad CLI command)` pairs
- Adapter kind: lora (r=16, alpha=32)
- Target modules: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj
- Run name: `stage25_qwen15_doc_verifier_r16_augmented`
- Compute: `local-cuda-0`

## Loading

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
model = PeftModel.from_pretrained(base, "scrubster/dr-stein-stage25-qwen15-doc-verifier-r16-augmented")
```

## Notes

Doc-verifier rank=16 retrain on the augmented corpus (442 -> 592 pairs; unknown class 70 -> 220 via fake-parent-prefix synthesis, see scripts/distill/augment_doc_verifier_unknown.py).
Hypothesis (from .planning/concerns/scaling-decisions.md): r=16 model stalled at F1=0.720 because unknown-class had only 16% of pairs — a DATA imbalance bottleneck, not a parameter bottleneck. Re-balancing the corpus to ~37% unknown should lift unknown-class F1 from 0.462 toward the 0.85 promotion gate without changing rank.
Same recipe as r=16 (LoRA r=16, alpha=32, 3 epochs, lr=2e-4) — only the dataset path changed. Per slm-learning-051: candidate-only.

