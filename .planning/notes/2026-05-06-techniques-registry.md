# Techniques registry — slm-learning model evolution

Living document. Each technique has status, where it fits in the ladder, and the
empirical evidence we have so far. Reference for decision `slm-learning-033`.

## Adapter / fine-tuning techniques

| Technique | Status | Use in GAD | Evidence so far |
|---|---|---|---|
| **LoRA** | canonical | per-skill specialists (CLI, math, tooluse) | v1 22/30 → v2 30/30 GAD-tools; works |
| **QLoRA** | not-yet-tried | 7B-32B fine-tunes on $1-3/hr GPUs | bitsandbytes path wired in `base_loader.py`; needs container test |
| **DoRA** | not-yet-tried | when LoRA plateaus | magnitude+direction decomposition; reported better stability |
| **LoRA+** | not-yet-tried | training speed | separate LR for A vs B matrices; ~2x speedup published |
| **Multi-task LoRA** | queued (SL-T-04-03) | one adapter, multiple domains | hypothesis: beats stacking for our scale |
| **Stacked LoRAs** | queued (SL-T-04-02) | combine specialists at inference | risk: untrained interaction |
| **TIES / DARE merging** | not-yet-tried | safer "many LoRAs become one" | PEFT supports it; preserves direction in weight space |
| **Bake / merge_and_unload** | gated | promote multi-task adapter to new base | only after 7-criterion gate (decision 032) |

## Preference / RL techniques

| Technique | Status | Use in GAD | Evidence so far |
|---|---|---|---|
| **DPO** | not-yet-tried | preference training after SFT | needs (chosen, rejected) pairs |
| **ORPO** | not-yet-tried | combined SFT + preference, no reference model | simpler than DPO+SFT pipeline |
| **Execution-driven RL** | long-term | unit tests / game tests as reward signal | requires reward model + env wrapper |

## Inference techniques

| Technique | Status | Use in GAD | Evidence so far |
|---|---|---|---|
| **Speculative decoding** | not-yet-tried | 1.5B drafter + 7B verifier | approaches 7B speed at 7B quality |
| **KV / prefix caching** | not-yet-tried | reuse GAD context blocks (repo summary, system prompt) | vLLM supports natively |
| **4-bit / int8 quantization** | not-yet-tried locally | 3B+ on the 1660 Ti | bitsandbytes available |

## Classical ML for routing & triage

| Technique | Status | Use in GAD | Evidence so far |
|---|---|---|---|
| **Logistic regression** | queued (SL-T-04-01) | router: input → which specialist | will train on hand-labeled 200 examples |
| **SVM** | not-yet-tried | router alternative; calibrated decision boundary | tradeoff w/ logistic |
| **XGBoost** | not-yet-tried | tabular features (code metrics, lint, file size) | trees beat NNs on tabular |
| **Isolation forest** | not-yet-tried | anomaly flagging on model outputs | "did the LoRA produce nonsense?" detector |
| **Isotonic regression** | not-yet-tried | calibrate LLM confidence to real probabilities | fixes overconfidence |

## Failure modes (so we don't repeat them)

| Failure | Cause | Mitigation |
|---|---|---|
| Distill model on terse data → catastrophic forgetting of `<think>` | Fine-tuning a reasoning model on non-reasoning outputs | Don't mix model archetype with anti-archetype data (decision 027) |
| 30/30 saturation on small eval | 30 cases is too narrow | Need harder eval (game tasks, unit-test repair) |
| Bake without promotion gate | Permanent loss of prior skills | Decision 032 — gate criteria mandatory |
| LoRAs trained independently then stacked | Interference at inference | Train coexistence via AdapterFusion or move to multi-task LoRA |

## Status legend

- **canonical**: in our default recipe, validated
- **experimental**: actively running an experiment
- **queued**: planned, has task ID
- **not-yet-tried**: in the registry, not yet on the queue
- **abandoned**: tried and didn't work; record the reason
