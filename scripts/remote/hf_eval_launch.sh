#!/usr/bin/env bash
# Eval-only HF Jobs launcher. Pulls a list of adapter repos from HF Hub
# and runs the full benchmark matrix on each.
#
# Usage:
#   bash scripts/remote/hf_eval_launch.sh "repo1 repo2 repo3" [flavor] [timeout]
#
# Defaults:
#   flavor=l4x1   ($0.80/hr; sufficient for 1.5B-3B inference)
#   timeout=1h

set -euo pipefail

ADAPTERS="${1:?Usage: $0 \"repo1 repo2 ...\" [flavor] [timeout]}"
FLAVOR="${2:-l4x1}"
TIMEOUT="${3:-1h}"

REPO="https://github.com/MagicbornStudios/gad_slms.git"
IMAGE="pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel"

echo "Eval-only HF Job:"
echo "  flavor:   $FLAVOR"
echo "  timeout:  $TIMEOUT"
echo "  adapters: $ADAPTERS"
echo

CMD="apt-get update -qq && apt-get install -y -qq git curl && cd /tmp && git clone -b master $REPO repo && cd repo && bash scripts/remote/hf_eval_bootstrap.sh $ADAPTERS"

hf jobs run \
  --flavor "$FLAVOR" \
  --secrets HF_TOKEN \
  --env PYTHONUTF8=1 \
  --env PYTHONPATH=src \
  --timeout "$TIMEOUT" \
  -d \
  "$IMAGE" \
  bash -c "$CMD"
