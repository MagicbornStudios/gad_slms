# Morphism Phases 1-4 firing sequence (PowerShell on Windows).
#
# Run this AFTER Phase 0 completes (0.5B HE + MBPP base evals on Modal A10G).
# This script:
#   1. Pulls 0.5B HE results from Modal volume to local
#   2. Builds 0.5B-hard-fn-norm dataset locally
#   3. Uploads dataset to Modal volume
#   4. Fires LoRA control + morphism Variant A trainings in parallel on A10G
#   5. (Manual) After both finish, fires 4 evals (LoRA HE, LoRA MBPP,
#      morphism HE, morphism MBPP) in parallel
#   6. (Manual) Pulls all 4 eval JSONs locally
#   7. Runs scripts/morphism/aggregate_morphism_arms.py
#
# Per AGENTS.md: MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 not strictly needed
# in PowerShell (no MSYS), but PYTHONIOENCODING=utf-8 helps keep emoji-safe
# stdout on Windows consoles.
#
# Decision refs: slm-learning-130, slm-learning-165, slm-learning-169.

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$repoRoot = 'C:\Users\benja\Documents\slm_learning'
Set-Location $repoRoot

$modal = '.\.venv\Scripts\modal.exe'

# --- Phase 1a: pull 0.5B HE results
Write-Host '[phase-1a] Pulling 0.5B HE results from Modal volume...'
& $modal volume get slm-models `
    'eval-runs/morphism-0p5b-base-2026-05-08/humaneval_chat_base_n164.json' `
    'tmp/diag-2026-05-08/base_he_0p5b_full.json' --force

if (-not (Test-Path 'tmp/diag-2026-05-08/base_he_0p5b_full.json')) {
    Write-Error '0.5B HE results not yet in Modal volume — Phase 0 may not be done.'
    exit 1
}

# --- Phase 1b: pull 0.5B MBPP results
Write-Host '[phase-1b] Pulling 0.5B MBPP results from Modal volume...'
& $modal volume get slm-models `
    'eval-runs/morphism-0p5b-base-2026-05-08/mbpp_chat_base_n164.json' `
    'tmp/diag-2026-05-08/base_mbpp_0p5b_full.json' --force

# --- Phase 1c: build dataset locally
Write-Host '[phase-1c] Building 0.5B-hard-fn-norm dataset...'
& '.\.venv\Scripts\python.exe' 'scripts/data/build_0p5b_hard_fn_norm_dataset.py'

if (-not (Test-Path 'data/processed/0p5b-hard-fn-norm-2026-05-08/rows.jsonl')) {
    Write-Error 'Dataset build failed.'
    exit 1
}

# --- Phase 1d: upload dataset to Modal volume
Write-Host '[phase-1d] Uploading dataset to Modal volume...'
& $modal run modal_app/train_lora.py::upload `
    'data/processed/0p5b-hard-fn-norm-2026-05-08/rows.jsonl' `
    'processed/0p5b-hard-fn-norm-2026-05-08/rows.jsonl'

# --- Phase 2a: fire LoRA control training (A10G, in foreground here; can be backgrounded)
Write-Host '[phase-2a] Firing LoRA control training on A10G...'
& $modal run modal_app/train_lora.py::main `
    --spec-path 'experiments/configs/morphism/lora_0p5b_control.json' `
    --gpu A10G 2>&1 | Tee-Object -FilePath 'experiments/runs/_morphism_lora_control.log'

# --- Phase 2b: fire morphism Variant A training (A10G)
Write-Host '[phase-2b] Firing morphism Variant A training on A10G...'
& $modal run modal_app/train_morphism.py::main `
    --spec-path 'experiments/configs/morphism/morphism_0p5b_variant_a.json' `
    --gpu A10G 2>&1 | Tee-Object -FilePath 'experiments/runs/_morphism_variant_a.log'

# --- Phase 3: 4 evals in parallel (sequential here, ~30 min total)
Write-Host '[phase-3a] Eval LoRA × HE...'
& $modal run modal_app/eval_adapter.py::main `
    --adapter-id 'scrubster/dr-stein-morphism-0p5b-lora-control' `
    --base-model 'Qwen/Qwen2.5-Coder-0.5B-Instruct' `
    --benchmark humaneval --limit 164 --gpu A10G --mode chat `
    --max-new-tokens 512 `
    --persist-run-id 'morphism-0p5b-arms-2026-05-08' 2>&1 | Tee-Object -FilePath 'experiments/runs/_morphism_lora_he.log'

Write-Host '[phase-3b] Eval LoRA × MBPP...'
& $modal run modal_app/eval_adapter.py::main `
    --adapter-id 'scrubster/dr-stein-morphism-0p5b-lora-control' `
    --base-model 'Qwen/Qwen2.5-Coder-0.5B-Instruct' `
    --benchmark mbpp --limit 164 --gpu A10G --mode chat `
    --max-new-tokens 512 `
    --persist-run-id 'morphism-0p5b-arms-2026-05-08' 2>&1 | Tee-Object -FilePath 'experiments/runs/_morphism_lora_mbpp.log'

Write-Host '[phase-3c] Eval morphism × HE...'
& $modal run modal_app/eval_morphism.py::main `
    --run-id 'morphism-0p5b-variant-a-2026-05-08' `
    --base-model 'Qwen/Qwen2.5-Coder-0.5B-Instruct' `
    --insert-after-layer 11 `
    --benchmark humaneval --limit 164 --gpu A10G --mode chat `
    --max-new-tokens 512 `
    --persist-run-id 'morphism-0p5b-arms-2026-05-08' 2>&1 | Tee-Object -FilePath 'experiments/runs/_morphism_he.log'

Write-Host '[phase-3d] Eval morphism × MBPP...'
& $modal run modal_app/eval_morphism.py::main `
    --run-id 'morphism-0p5b-variant-a-2026-05-08' `
    --base-model 'Qwen/Qwen2.5-Coder-0.5B-Instruct' `
    --insert-after-layer 11 `
    --benchmark mbpp --limit 164 --gpu A10G --mode chat `
    --max-new-tokens 512 `
    --persist-run-id 'morphism-0p5b-arms-2026-05-08' 2>&1 | Tee-Object -FilePath 'experiments/runs/_morphism_mbpp.log'

# --- Phase 4: pull eval results + manifests, run aggregator
Write-Host '[phase-4a] Pulling eval result JSONs from Modal...'
& $modal volume get slm-models `
    'eval-runs/morphism-0p5b-arms-2026-05-08/humaneval_chat_morphism-0p5b-lora-control_n164.json' `
    'tmp/diag-2026-05-08/lora_0p5b_he_full.json' --force
& $modal volume get slm-models `
    'eval-runs/morphism-0p5b-arms-2026-05-08/mbpp_chat_morphism-0p5b-lora-control_n164.json' `
    'tmp/diag-2026-05-08/lora_0p5b_mbpp_full.json' --force
& $modal volume get slm-models `
    'eval-runs/morphism-0p5b-arms-2026-05-08/humaneval_chat_morphism_morphism-0p5b-variant-a-2026-05-08_n164.json' `
    'tmp/diag-2026-05-08/morphism_0p5b_he_full.json' --force
& $modal volume get slm-models `
    'eval-runs/morphism-0p5b-arms-2026-05-08/mbpp_chat_morphism_morphism-0p5b-variant-a-2026-05-08_n164.json' `
    'tmp/diag-2026-05-08/morphism_0p5b_mbpp_full.json' --force

# Pull both training manifests
& $modal volume get slm-models `
    'runs/morphism-0p5b-lora-control-2026-05-08/MANIFEST.json' `
    'tmp/morphism-0p5b-lora-control-MANIFEST.json' --force
& $modal volume get slm-models `
    'runs/morphism-0p5b-variant-a-2026-05-08/MANIFEST.json' `
    'tmp/morphism-0p5b-variant-a-MANIFEST.json' --force

# --- Phase 4b: aggregate
Write-Host '[phase-4b] Running aggregator...'
& '.\.venv\Scripts\python.exe' 'scripts/morphism/aggregate_morphism_arms.py'

Write-Host '[done] See reports/evals/morphism_0p5b_variant_a_2026-05-08.md'
