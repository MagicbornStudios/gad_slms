#!/usr/bin/env bash
# Eval-only bootstrap. Runs INSIDE an HF Jobs container.
# Pulls one or more PEFT adapter repos from HF Hub and runs the full
# benchmark matrix (gad_tools + humaneval + gsm8k) against each.
#
# Usage (from launcher):
#   bash scripts/remote/hf_eval_bootstrap.sh <hub_repo_id_1> [<hub_repo_id_2> ...]
#
# Each repo must be a PEFT adapter (adapter_config.json + safetensors)
# whose adapter_config.json points at a base model HF Hub can resolve.

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "FATAL: expected at least one HF Hub adapter repo id" >&2
  echo "Usage: $0 <repo_id> [...]" >&2
  exit 2
fi

ADAPTERS=("$@")

echo "==[ hf_eval_bootstrap ]================================================="
echo "adapters: ${ADAPTERS[*]}"
echo "cwd:      $(pwd)"
echo "python:   $(python --version)"
nvidia-smi --query-gpu=name,memory.total --format=csv || true
echo

echo "==[ install deps ]======================================================"
pip install -q --no-cache-dir \
  "trl==1.3.0" transformers peft datasets accelerate \
  huggingface_hub bitsandbytes pyyaml
echo "  ok"
echo

echo "==[ refresh eval data ]================================================="
set +e
python <<'PY'
import os
from pathlib import Path
from datasets import load_dataset

gsm = Path('data/external/gsm8k/test.parquet')
if not (gsm.exists() and gsm.stat().st_size > 100_000):
    print(f'  pulling GSM8K test -> {gsm}')
    ds = load_dataset('openai/gsm8k', 'main', split='test')
    gsm.parent.mkdir(parents=True, exist_ok=True)
    ds.to_parquet(str(gsm))
    print(f'  wrote {len(ds)} rows')

he = Path('data/external/humaneval/test.parquet')
if not (he.exists() and he.stat().st_size > 50_000):
    print(f'  pulling HumanEval test -> {he}')
    ds = load_dataset('openai/openai_humaneval', split='test')
    he.parent.mkdir(parents=True, exist_ok=True)
    ds.to_parquet(str(he))
    print(f'  wrote {len(ds)} rows')

os._exit(0)
PY
set -e

for path in data/external/gsm8k/test.parquet data/external/humaneval/test.parquet; do
  if [ ! -s "$path" ]; then
    echo "FATAL: eval data file missing: $path"
    exit 1
  fi
done
echo "  verified eval data"
echo

# Per-adapter loop
for repo_id in "${ADAPTERS[@]}"; do
  slug=$(echo "$repo_id" | tr '/' '_')
  local_dir="/tmp/adapters/${slug}"

  echo "==[ ${repo_id} ]=========================================================="
  python - "$repo_id" "$local_dir" <<'PY'
import sys
from huggingface_hub import snapshot_download
repo_id, local_dir = sys.argv[1], sys.argv[2]
print(f'  downloading {repo_id} -> {local_dir}')
snapshot_download(repo_id=repo_id, local_dir=local_dir)
print('  done')
PY

  out_dir="experiments/runs/eval_${slug}"
  mkdir -p "$out_dir"

  echo "  [gad_tools] running ..."
  PYTHONPATH=src PYTHONUTF8=1 python scripts/eval_checkpoint.py \
    --checkpoint "$local_dir" \
    --out "${out_dir}/eval_gad_tools.json" \
    --name "$slug" \
    --max-new-tokens 50 --temperature 0.0 --device auto || true

  echo "  [humaneval] running n=10 ..."
  PYTHONPATH=src PYTHONUTF8=1 python scripts/eval_humaneval.py \
    --checkpoint "$local_dir" \
    --out "${out_dir}/eval_humaneval.json" \
    --name "$slug" \
    --n 10 --max-new-tokens 256 --temperature 0.0 --device auto || true

  echo "  [gsm8k] running n=50 ..."
  PYTHONPATH=src PYTHONUTF8=1 python scripts/eval_gsm8k.py \
    --checkpoint "$local_dir" \
    --out "${out_dir}/eval_gsm8k.json" \
    --name "$slug" \
    --n 50 --max-new-tokens 400 --temperature 0.0 --device auto || true
  echo
done

echo "==[ summary ]==========================================================="
python <<'PY'
import json
from pathlib import Path
print(f"{'adapter':50} {'gad_tools':>12}  {'humaneval':>10}  {'gsm8k':>10}")
print('-' * 92)
for d in sorted(Path('experiments/runs').glob('eval_*')):
    name = d.name[len('eval_'):]
    g = h = s = 'n/a'
    for fname, key, fmt in [
        ('eval_gad_tools.json', 'pct', lambda j: f"{j.get('passed','?')}/{j.get('total','?')}"),
        ('eval_humaneval.json', 'pass_at_1', lambda j: f"{j.get('passed','?')}/{j.get('total','?')}"),
        ('eval_gsm8k.json', 'accuracy', lambda j: f"{j.get('passed','?')}/{j.get('total','?')}"),
    ]:
        path = d / fname
        if path.exists():
            try:
                j = json.loads(path.read_text())
                if fname == 'eval_gad_tools.json': g = fmt(j)
                elif fname == 'eval_humaneval.json': h = fmt(j)
                elif fname == 'eval_gsm8k.json': s = fmt(j)
            except Exception:
                pass
    print(f"{name:50} {g:>12}  {h:>10}  {s:>10}")
PY
echo
echo "==[ done ]=============================================================="
