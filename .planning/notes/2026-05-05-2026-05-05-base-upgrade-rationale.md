# Base upgrade rationale: 135M to 1.5B Qwen-family pair

Stage 2.5 on SmolLM2-135M scored 9/30 (default LR) and 12/30 (higher LR) on GAD-tools — first non-zero scores ever. HumanEval 0/10, GSM8K 5/50 (mostly collisions). The 135M base is below the SLM paper's 1B-effective-floor (arxiv 2506.02153). Upgrading to 1.5B per decision slm-learning-022.

Two candidates running in parallel sweep, same Qwen tokenizer:
- DeepSeek-R1-Distill-Qwen-1.5B: reasoning-distilled from R1, strongest 1.5B by published benchmarks. Caveat: emits <think>...</think> traces which may hurt single-line GAD-CLI output but should help HumanEval/GSM8K.
- Qwen2.5-1.5B-Instruct: standard instruction-following baseline. Better at terse output, slightly weaker raw reasoning.

Both fit fp16 inference on 1660 Ti (~3GB weights, comfortable headroom). Both fit local QLoRA training. Sweep gives empirical answer instead of guessing.

If we later step up to 3B+, we cross into int8-inference territory locally and need a separate inference path. SmolLM3-3B and Phi-4-mini are candidates for that future phase.

Inference fits local; training planned for both local and remote (Colab T4 / Kaggle dual-T4) per slm-learning-020.
