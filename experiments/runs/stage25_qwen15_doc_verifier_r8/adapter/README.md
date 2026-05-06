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

# scrubster/dr-stein-stage25-qwen15-doc-verifier-r8

PEFT/LoRA adapter for `Qwen/Qwen2.5-1.5B-Instruct`, fine-tuned on the
slm-learning GAD-tool translation track.

- Trained on: 153 hand-curated `(instruction, gad CLI command)` pairs
- Adapter kind: lora (r=8, alpha=16)
- Target modules: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj
- Run name: `stage25_qwen15_doc_verifier_r8`
- Compute: `local-cuda-0`

## Loading

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
model = PeftModel.from_pretrained(base, "scrubster/dr-stein-stage25-qwen15-doc-verifier-r8")
```

## Notes

Doc-verifier specialist (SL-T-04-09) — first agent-as-SLM end-to-end. Per ChatGPT priority directive 2026-05-06: rank=8 first, rank=16 only if underfit. 442 training pairs (after dedup from 738 raw across two bootstrap runs), 50 stratified hold-out. Label balance: refuted 226 (51%) / verified 146 (33%) / unknown 70 (16%).
Output schema is JSON: {status, evidence, reason}. Trainer treats the JSON as a single response string.
Per slm-learning-051: this run produces a CANDIDATE, not an auto-merged adapter. Promotion requires Verifier+Critic verdict + scripts/delta/promote_atomic.py operator stamp.

