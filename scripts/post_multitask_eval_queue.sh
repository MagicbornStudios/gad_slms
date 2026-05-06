#!/usr/bin/env bash
# Post-multitask eval queue — runs the moment multitask training
# finishes the GPU. Per ChatGPT priority directive 2026-05-06:
#
#   1. Finish multi-task LoRA run, immediately evaluate:
#      - GAD-tools
#      - GSM8K
#      - HumanEval
#      - tool-use sanity eval if available
#
# This script is operator-triggered. Run it after the multitask run's
# eval_hook fires (which already does gad_tools + gsm8k + humaneval).
# This script adds:
#   - tool-use sanity eval (custom)
#   - constitution-impact arm C eval (slm-learning-060)
#   - regression check vs v2 baseline (slm-learning-070, no >5pp drop)
#   - SWE-bench scaffold run (so the result envelope exists)
#
# Usage:
#   bash scripts/post_multitask_eval_queue.sh
#
# Decision refs: slm-learning-051, slm-learning-060, slm-learning-071.

set -euo pipefail

CANDIDATE_DIR="${CANDIDATE_DIR:-experiments/runs/stage25_qwen15_multitask}"
BASELINE_DIR="${BASELINE_DIR:-experiments/runs/stage25_qwen15_instruct_v2}"

echo "[queue] candidate = $CANDIDATE_DIR"
echo "[queue] baseline  = $BASELINE_DIR"

# 1. Eval candidate against baseline using slm-learning's verifier rubric.
echo ""
echo "[queue 1/4] eval_candidate.py vs v2 baseline ..."
.venv/Scripts/python.exe scripts/delta/eval_candidate.py \
  --candidate-dir "$CANDIDATE_DIR" \
  --baseline-eval-dir "$BASELINE_DIR/eval" \
  --benchmarks gad_tools,gsm8k,humaneval \
  > "$CANDIDATE_DIR/eval/verdict.json" 2>&1 || \
  echo "[queue] eval_candidate.py exit non-zero (continuing)"

# 2. SWE-bench scaffold (status=scaffold; real scoring is phase 06).
echo ""
echo "[queue 2/4] eval_swebench.py scaffold ..."
.venv/Scripts/python.exe scripts/eval_swebench.py \
  --model-path "$CANDIDATE_DIR" \
  --out "$CANDIDATE_DIR/eval/swebench.json" 2>&1 || \
  echo "[queue] eval_swebench.py exit non-zero (continuing)"

# 3. Constitution-impact arm C eval — only if scripts/eval/constitution_arm_c.py exists.
echo ""
echo "[queue 3/4] constitution-impact arm C ..."
if [ -f scripts/eval/constitution_arm_c.py ]; then
  .venv/Scripts/python.exe scripts/eval/constitution_arm_c.py \
    --candidate-dir "$CANDIDATE_DIR" \
    --baseline-dir "$BASELINE_DIR" 2>&1 || \
    echo "[queue] arm C exit non-zero (continuing)"
else
  echo "[queue] constitution_arm_c.py not yet implemented — skipping"
fi

# 4. Tool-use sanity eval — only if a held-out tool-use eval set exists.
echo ""
echo "[queue 4/4] tool-use sanity eval ..."
if [ -f data/eval/tool_use_holdout.jsonl ] && [ -f scripts/eval/eval_tool_use.py ]; then
  .venv/Scripts/python.exe scripts/eval/eval_tool_use.py \
    --candidate-dir "$CANDIDATE_DIR" \
    --holdout data/eval/tool_use_holdout.jsonl 2>&1 || \
    echo "[queue] tool-use eval exit non-zero (continuing)"
else
  echo "[queue] tool-use holdout / eval script not yet built — skipping"
fi

echo ""
echo "[queue] done. Verdict at $CANDIDATE_DIR/eval/verdict.json"
echo "[queue] Next: review verdict, then either:"
echo "[queue]   - log promotion decision + run scripts/delta/promote_atomic.py"
echo "[queue]   - inter as skeleton via tmp/zoo/ (slm-learning-066)"
echo "[queue]   - schedule rank=16 retrain if underfit (per ChatGPT directive)"
