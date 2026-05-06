#!/usr/bin/env bash
# Fire a training sweep on HF Jobs. Run from operator's local machine.
#
# Usage:
#   bash scripts/remote/hf_job_launch.sh [flavor] [configs-dir] [timeout]
#
# Defaults:
#   flavor=a10g-small  ($1.00/hr; 24GB A10G; fits 1.5B + 3B at bf16 LoRA)
#   configs-dir=experiments/configs/colab/
#   timeout=2h
#
# What it does:
#   - Submits a detached HF Jobs run with our pytorch image
#   - Job clones the repo (current master), installs deps, runs sweep
#   - Adapters auto-publish to scrubster/dr-stein-<config>
#   - Returns job_id; watch with: hf jobs logs <job_id>

set -euo pipefail

FLAVOR="${1:-a10g-small}"
CONFIGS_DIR="${2:-experiments/configs/colab/}"
TIMEOUT="${3:-2h}"

REPO="https://github.com/MagicbornStudios/gad_slms.git"
IMAGE="pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel"

echo "Launching HF Job:"
echo "  flavor:      $FLAVOR"
echo "  configs-dir: $CONFIGS_DIR"
echo "  timeout:     $TIMEOUT"
echo "  image:       $IMAGE"
echo "  repo:        $REPO"
echo

CMD="apt-get update -qq && apt-get install -y -qq git curl && cd /tmp && git clone $REPO repo && cd repo && bash scripts/remote/hf_job_bootstrap.sh $CONFIGS_DIR"

hf jobs run \
  --flavor "$FLAVOR" \
  --secrets HF_TOKEN \
  --env PYTHONUTF8=1 \
  --env PYTHONPATH=src \
  --timeout "$TIMEOUT" \
  -d \
  "$IMAGE" \
  bash -c "$CMD"
