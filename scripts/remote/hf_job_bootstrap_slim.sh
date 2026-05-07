#!/usr/bin/env bash
# Slim bootstrap — installs deps + runs sweep, skips the data-refresh step.
#
# Use this when the configs-dir's specs reference data files that are
# ALREADY in the repo clone (i.e. committed to git, not pulled from HF
# datasets at runtime).
#
# The wider hf_job_bootstrap.sh streams openmath/gsm8k/humaneval at
# every job start, which is wasteful and prone to dataset-streaming
# hangs. This slim version skips that phase entirely.
#
# Usage (called inside hf jobs container):
#   bash scripts/remote/hf_job_bootstrap_slim.sh [configs-dir]

set -euo pipefail

CONFIGS_DIR="${1:-experiments/configs/colab/}"

echo "==[ hf_job_bootstrap_slim ]============================================="
echo "configs-dir: $CONFIGS_DIR"
echo "cwd:         $(pwd)"
echo "python:      $(python --version)"
echo "gpu:"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv || \
  echo "  (no GPU detected)"
echo

echo "==[ install deps ]======================================================"
pip install -q --no-cache-dir \
  "trl==1.3.0" transformers peft datasets accelerate \
  huggingface_hub bitsandbytes pyyaml 2>&1 | tail -5
echo "  ok"
echo

echo "==[ verify configs reference repo-tracked data ]======================="
python <<'PY'
import sys
import yaml
from pathlib import Path

cfg_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "experiments/configs/colab/")
missing = []
for cfg_path in sorted(cfg_dir.glob("*.yaml")):
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)
    data_path = cfg.get("data", {}).get("path")
    if not data_path:
        continue
    p = Path(data_path)
    if not p.exists():
        missing.append((cfg_path.name, data_path))
if missing:
    print("FATAL: configs reference data files not present in the repo clone:")
    for name, dp in missing:
        print(f"  {name} -> {dp}")
    print("Either commit the data files OR use the full hf_job_bootstrap.sh "
          "that pulls from HF datasets.")
    sys.exit(1)
print(f"  all data paths in {cfg_dir} verified present")
PY
echo

echo "==[ run sweep ]========================================================="
PYTHONPATH=src PYTHONUTF8=1 python scripts/sweep_finetune.py --configs-dir "$CONFIGS_DIR"
echo

echo "==[ summary ]==========================================================="
python <<'PY'
import json
from pathlib import Path

rows = []
for d in sorted(Path('experiments/runs').iterdir()):
    if not d.is_dir():
        continue
    mp = d / 'MANIFEST.json'
    if not mp.exists():
        continue
    m = json.loads(mp.read_text())
    cfg = m.get('config', {})
    e = m.get('eval_results', {})
    g = e.get('gad_tools', {})
    rows.append({
        'name': cfg.get('name', d.name),
        'base': cfg.get('base_model', '?').split('/')[-1],
        'train_s': m.get('elapsed_train_sec', 0),
        'gad': f"{g.get('passed','-')}/{g.get('total','-')}" if 'passed' in g else 'n/a',
        'hub': m.get('hub_url', 'not pushed'),
    })

if not rows:
    print('  no runs found in experiments/runs/')
else:
    print(f"{'name':40} {'base':24} {'train':>8}  {'gad':>7}")
    print('-' * 90)
    for r in rows:
        print(f"{r['name']:40} {r['base']:24} {r['train_s']:>7.0f}s  {r['gad']:>7}")
    print()
    for r in rows:
        print(f"  {r['name']:40} -> {r['hub']}")
PY
echo
echo "==[ done ]=============================================================="
