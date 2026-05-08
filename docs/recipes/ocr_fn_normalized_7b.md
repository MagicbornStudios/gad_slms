# Recipe: OCR fn_normalized × 7B

## Verdict
NOT USEFUL

## Numbers
| Metric | Base | + LoRA | Δ |
|---|---|---|---|
| HumanEval n=164 | 134/164 (81.7%) | 133/164 (81.1%) | -0.6pp |
| MBPP n=164 | 132/164 (80.5%) | 126/164 (76.8%) | -3.7pp |

## Recipe spec
- base_model: Qwen/Qwen2.5-Coder-7B-Instruct
- dataset: ocr_function_normalized (1991 rows, ~40% kept from 5000)
- LoRA: r=16, α=32, dropout=0.05
- training: 1 epoch, lr=2e-4, bs=4, grad_accum=4, bf16, gradient_checkpointing
- GPU: A100, wall: 14 min, cost: ~$0.66
- adapter_path: /models/runs/ladder-7b-ocr-fn-norm-2026-05-08/adapter
- training_loss: 0.9697

## When to use
- Do not use; regression confirmed at 7B scale
- Archive as negative result for research program record

## When NOT to use
- 7B coder specialist in any capacity
- Scaling-ladder validation (7B regression invalidates upstream 1.5B/3B gains for this recipe)
- Any production or evaluation workflow

## Why it doesn't work at this scale
At 7B, the base model already internalized the **specific** HumanEval/MBPP function-output shapes during pretraining and initial instruction-tuning. The OCR fn_normalized dataset does not teach the model *new* structures; it instead introduces perturbative fine-tuning that drifts the base distribution away from what the eval target distribution rewards. The -0.6pp on HumanEval and -3.7pp on MBPP (plus -2.8pp on gad_tools at 36.7%) confirm this redundancy-or-harm pattern.

The problem is not the recipe *design* (LoRA rank=16, learning rate, batch size all reasonable). Rather, at 7B capacity, the model has already compressed function-output semantics into its weights in a way that generalizes to the eval set. Fine-tuning on a narrower dataset (1991 rows, ~40% retention) with the same task-specific template actually increases the likelihood of overfitting to noise or task-specific artifacts that do not transfer back to the original eval distribution.

This result suggests that future 7B+ recipes should target **different domains** (hard examples, out-of-distribution reasoning, specialized tool-use) rather than reinforcing patterns the base model already mastered. The recipe may still help smaller scales; it provides no value at 7B and larger.

## Lineage / decision_refs
slm-learning-094, slm-learning-097, slm-learning-103, slm-learning-107, slm-learning-110, slm-learning-113, slm-learning-118, slm-learning-119

## Pointers
- adapter on slm-models volume: /models/runs/ladder-7b-ocr-fn-norm-2026-05-08/adapter
- gate-fail report: reports/evals/fn_normalized_7b_confirmation.md
- data contract: docs/data-contracts/coding_sft.md
