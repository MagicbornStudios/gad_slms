#!/usr/bin/env bash
# Bootstrap script that runs INSIDE an HF Jobs container.
#
# Job command should be:
#   bash -c "git clone https://github.com/MagicbornStudios/gad_slms.git /repo \
#            && cd /repo && bash scripts/remote/hf_job_bootstrap.sh [configs-dir]"
#
# Args:
#   $1 = configs-dir (default: experiments/configs/colab/)
#
# Env (from job --secrets / --env):
#   HF_TOKEN — write token, used to push adapters
#
# What it does:
#   1. Install Python deps (transformers/peft/trl/datasets/accelerate/etc)
#   2. Re-pull gitignored data files from HF (math 5k)
#   3. Run sweep_finetune.py against every config in --configs-dir
#   4. Print a results table

set -euo pipefail

CONFIGS_DIR="${1:-experiments/configs/colab/}"

echo "==[ hf_job_bootstrap ]=================================================="
echo "configs-dir: $CONFIGS_DIR"
echo "cwd:         $(pwd)"
echo "python:      $(python --version)"
echo "gpu:"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv || echo "  (no GPU detected)"
echo

echo "==[ install deps ]======================================================"
pip install -q --no-cache-dir \
  "trl==1.3.0" transformers peft datasets accelerate \
  huggingface_hub bitsandbytes pyyaml
echo "  ok"
echo

echo "==[ refresh data ]======================================================"
# Wrapped in `set +e` because the `datasets` library + torch can crash on
# interpreter shutdown (PyGILState_Release fatal) AFTER successfully writing
# the file. We verify file existence + size after; that's the real success
# signal, not Python's exit code.
set +e
python <<'PY'
import json
import os
from pathlib import Path
from datasets import load_dataset

out = Path('data/openmathinstruct_5k.jsonl')
need_refresh = (not out.exists()) or out.stat().st_size < 1_000_000
if not need_refresh:
    print(f'  {out} already present')
else:
    print(f'  streaming OpenMathInstruct-2 -> {out}')
    ds = load_dataset('nvidia/OpenMathInstruct-2', split='train', streaming=True)
    n = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', encoding='utf-8') as f:
        for ex in ds:
            instr = ex.get('problem') or ex.get('question')
            resp = ex.get('generated_solution')
            if not instr or not resp or len(resp) > 2500:
                continue
            f.write(json.dumps({'instruction': instr, 'command': resp}, ensure_ascii=False) + '\n')
            n += 1
            if n >= 5000:
                break
    print(f'  wrote {n} pairs')
# os._exit(0) bypasses Python's atexit handlers (where the GIL crash happens)
os._exit(0)
PY
set -e
# Verify the file is actually present + non-trivial
if [ ! -s data/openmathinstruct_5k.jsonl ] || [ "$(wc -l < data/openmathinstruct_5k.jsonl)" -lt 100 ]; then
  echo "FATAL: math data file missing or too small after refresh step"
  ls -la data/openmathinstruct_5k.jsonl 2>&1 || true
  exit 1
fi
echo "  verified: $(wc -l < data/openmathinstruct_5k.jsonl) lines in math data file"
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
    if not cfg.get('compute_target', '').startswith(('colab', 'a10g', 'h200', 'l4', 't4')):
        continue
    e = m.get('eval_results', {})
    g, h, s = e.get('gad_tools', {}), e.get('humaneval', {}), e.get('gsm8k', {})
    rows.append({
        'name': cfg['name'],
        'base': cfg['base_model'].split('/')[-1],
        'train_s': m.get('elapsed_train_sec', 0),
        'gad': f"{g.get('passed','-')}/{g.get('total','-')}" if 'passed' in g else 'n/a',
        'h':   f"{h.get('passed','-')}/{h.get('total','-')}" if 'passed' in h else 'n/a',
        'g8k': f"{s.get('passed','-')}/{s.get('total','-')}" if 'passed' in s else 'n/a',
        'hub': m.get('hub_url', 'not pushed'),
    })

if not rows:
    print('  no Colab/HF-Jobs runs found in experiments/runs/')
else:
    print(f"{'name':40} {'base':24} {'train':>8}  {'gad':>7}  {'humaneval':>10}  {'gsm8k':>7}")
    print('-' * 110)
    for r in rows:
        print(f"{r['name']:40} {r['base']:24} {r['train_s']:>7.0f}s  {r['gad']:>7}  {r['h']:>10}  {r['g8k']:>7}")
    print()
    for r in rows:
        print(f"  {r['name']:40} -> {r['hub']}")
PY
echo
echo "==[ done ]=============================================================="
