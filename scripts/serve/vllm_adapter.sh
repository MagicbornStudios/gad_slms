#!/usr/bin/env bash
# vLLM serving harness — OpenAI-compatible local endpoint for any
# scrubster/dr-stein-* Hub adapter. Pattern A integration per the
# two-tier routing architecture (decision slm-learning-040).
#
# Usage:
#   ADAPTER_REPO=scrubster/dr-stein-colab-cli \
#   BASE_MODEL=Qwen/Qwen2.5-1.5B-Instruct \
#   PORT=8000 \
#   bash scripts/serve/vllm_adapter.sh
#
# After boot, smoke-test with:
#   curl -X POST http://localhost:8000/v1/chat/completions \
#     -H "Content-Type: application/json" \
#     -d '{"model":"adapter","messages":[{"role":"user","content":"hi"}]}'
#
# Notes:
# - vLLM has no native Windows support; run from WSL2, Linux, or HF Jobs.
# - For Windows-host fallback, use scripts/serve/serve_adapter.py
#   (FastAPI + transformers — slower but no CUDA-Linux dependency).
# - bf16 default per slm-learning-025 (Turing+); fp16 only on Ampere remote.

set -euo pipefail

ADAPTER_REPO="${ADAPTER_REPO:?set ADAPTER_REPO, e.g. scrubster/dr-stein-colab-cli}"
BASE_MODEL="${BASE_MODEL:-Qwen/Qwen2.5-1.5B-Instruct}"
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
DTYPE="${DTYPE:-bfloat16}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"
GPU_MEMORY_UTIL="${GPU_MEMORY_UTIL:-0.85}"

echo "[vllm] base=${BASE_MODEL} adapter=${ADAPTER_REPO} dtype=${DTYPE}"
echo "[vllm] listening on ${HOST}:${PORT}"

# Pre-pull the adapter so vLLM does not hang on first request.
hf download "${ADAPTER_REPO}" --quiet || true

exec python -m vllm.entrypoints.openai.api_server \
  --model "${BASE_MODEL}" \
  --enable-lora \
  --lora-modules "adapter=${ADAPTER_REPO}" \
  --dtype "${DTYPE}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTIL}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --served-model-name adapter
