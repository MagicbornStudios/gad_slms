#!/usr/bin/env bash
# Start the v2 CLI specialist adapter on a local OpenAI-compatible endpoint.
#
# Adapter: scrubster/dr-stein-stage25-qwen15-instruct-v2 (30/30 GAD-tools).
# Base: Qwen/Qwen2.5-1.5B-Instruct.
#
# Usage:
#   bash scripts/serve/start_v2.sh                # vLLM on Linux/WSL2
#   bash scripts/serve/start_v2.sh --windows      # Python fallback on Windows host
#
# After boot, smoke-test:
#   curl -X POST http://localhost:8000/v1/chat/completions \
#     -H "Content-Type: application/json" \
#     -d '{"model":"adapter","messages":[{"role":"user","content":"add a note: build is broken"}]}'
#
# scripts/gad_nl.py is the natural-language wrapper around this endpoint.

set -euo pipefail

ADAPTER="${ADAPTER:-scrubster/dr-stein-stage25-qwen15-instruct-v2}"
BASE="${BASE:-Qwen/Qwen2.5-1.5B-Instruct}"
PORT="${PORT:-8000}"

if [[ "${1:-}" == "--windows" ]]; then
  echo "[start_v2] Windows fallback path: serve_adapter.py via .venv-gpu"
  exec .venv-gpu/Scripts/python.exe scripts/serve/serve_adapter.py \
    --adapter "${ADAPTER}" \
    --base "${BASE}" \
    --port "${PORT}"
fi

echo "[start_v2] vLLM path: scripts/serve/vllm_adapter.sh"
ADAPTER_REPO="${ADAPTER}" BASE_MODEL="${BASE}" PORT="${PORT}" \
  exec bash scripts/serve/vllm_adapter.sh
