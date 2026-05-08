# GAD Scaling Ledger

Authoritative record of system growth: base models, adapters, and assemblies.
Each entry records honest parameter counts, evaluation results, and promotion status.

**Last updated:** 2026-05-08T17:32:47.868859Z

## Active Assemblies

Currently routable systems:

### gad-coder-7b-canonical-assembly-2026-05-08
- **Model:** gad-coder-7b-canonical
- **Status:** staging
- **Total params:** 7,628,460,000
- **Evals:** humaneval: 0.848, mbpp: 0.823
- **Notes:** Current GAD coder system: 7B base + hard_fn_norm adapter. Gap-targeted training on 7B-base HE failures. Best $/pp-lift metric to date. Staging pending 32B base eval for 32B shot decision.


## Base Model Inventory

| Model | Params | Status |
|---|---|---|
| Qwen/Qwen2.5-Coder-0.5B-Instruct | 494,032,768 | canonical |
| Qwen/Qwen2.5-Coder-1.5B-Instruct | 1,543,714,304 | canonical |
| Qwen/Qwen2.5-Coder-1.5B-Instruct | 1,777,088,000 | canonical |
| Qwen/Qwen2.5-Coder-3B-Instruct | 3,099,175,936 | canonical |
| Qwen/Qwen2.5-Coder-7B-Instruct | 7,610,000,000 | canonical |

## Canonical Adapters

Promoted to production:

#### ladder-1p5b-hard-retain-canonical
- **Base:** Qwen/Qwen2.5-Coder-1.5B-Instruct
- **Adapter params:** 18,460,000
- **Status:** canonical
- **Evals:** humaneval: 0.64, mbpp: 0.64

#### ladder-1p5b-ocr-fn-norm-canonical
- **Base:** Qwen/Qwen2.5-Coder-1.5B-Instruct
- **Adapter params:** 18,464,768
- **Status:** canonical
- **Evals:** humaneval: 0.616, mbpp: 0.64
- **Decisions:** slm-learning-110, slm-learning-118


## Staging Adapters

Awaiting promotion decision:

#### ladder-1p5b-morphism-b-staging
- **Base:** Qwen/Qwen2.5-Coder-1.5B-Instruct
- **Adapter params:** 1,183,100
- **Status:** staging
- **Evals:** humaneval: 0.549, mbpp: 0.61

#### ladder-7b-hard-fn-norm-canonical
- **Base:** Qwen/Qwen2.5-Coder-7B-Instruct
- **Adapter params:** 18,460,000
- **Status:** staging
- **Evals:** humaneval: 0.848, mbpp: 0.823
- **Decisions:** slm-learning-119, slm-learning-130


## Rejected Adapters

#### ladder-0p5b-hard-fn-norm-lora-rejected
- **Base:** Qwen/Qwen2.5-Coder-0.5B-Instruct
- **Adapter params:** 8,800,000
- **Status:** rejected
- **Evals:** humaneval: 0.226, mbpp: 0.427

#### ladder-0p5b-hard-fn-norm-morphism-lr5e5-rejected
- **Base:** Qwen/Qwen2.5-Coder-0.5B-Instruct
- **Adapter params:** 804,608
- **Status:** rejected
- **Evals:** humaneval: 0.116, mbpp: 0.415

#### ladder-0p5b-hard-fn-norm-morphism-rejected
- **Base:** Qwen/Qwen2.5-Coder-0.5B-Instruct
- **Adapter params:** 804,608
- **Status:** rejected
- **Evals:** humaneval: 0.274, mbpp: 0.378

#### ladder-1p5b-hard-only-rejected
- **Base:** Qwen/Qwen2.5-Coder-1.5B-Instruct
- **Adapter params:** 18,460,000
- **Status:** rejected
- **Evals:** humaneval: 0.482, mbpp: 0.573

#### ladder-1p5b-morphism-a-rejected
- **Base:** Qwen/Qwen2.5-Coder-1.5B-Instruct
- **Adapter params:** 2,362,400
- **Status:** rejected
- **Evals:** humaneval: 0.329, mbpp: 0.402

#### ladder-3b-ocr-fn-norm-rejected
- **Base:** Qwen/Qwen2.5-Coder-3B-Instruct
- **Adapter params:** 18,464,768
- **Status:** rejected
- **Reason:** Regression at 3B: -3.6 pp HE / -0.6 pp MBPP. fn_norm is a 1.5B-only specialist.
- **Evals:** humaneval: 0.799, mbpp: 0.738
- **Decisions:** slm-learning-110, slm-learning-118

#### ladder-7b-ocr-fn-norm-rejected
- **Base:** Qwen/Qwen2.5-Coder-7B-Instruct
- **Adapter params:** 18,464,768
- **Status:** rejected
- **Reason:** Neutral on HE (-0.6 pp) and regression on MBPP (-3.7 pp). Generic OCR data saturates strong bases.
- **Evals:** humaneval: 0.811, mbpp: 0.768, gad_tools: 0.367
- **Decisions:** slm-learning-107, slm-learning-110


## Evaluation Scores

### GAD_TOOLS

| Entry | Score |
|---|---|
| ladder-7b-ocr-fn-norm-rejected | 36.7% |
| qwen25-coder-7b-base-v3 | 36.7% |

### HUMANEVAL

| Entry | Score |
|---|---|
| gad-coder-7b-canonical-assembly-2026-05-08 | 84.8% |
| ladder-7b-hard-fn-norm-canonical | 84.8% |
| qwen25-coder-3b-base-v1 | 83.5% |
| qwen25-coder-7b-base-v3 | 81.7% |
| ladder-7b-ocr-fn-norm-rejected | 81.1% |
| ladder-3b-ocr-fn-norm-rejected | 79.9% |
| ladder-1p5b-hard-retain-canonical | 64.0% |
| ladder-1p5b-ocr-fn-norm-canonical | 61.6% |
| qwen25-coder-0p5b-base-2026-05-08 | 55.5% |
| ladder-1p5b-morphism-b-staging | 54.9% |
| qwen25-coder-1p5b-base-2026-05-08 | 54.9% |
| qwen25-coder-1p5b-base-v1 | 54.9% |
| ladder-1p5b-hard-only-rejected | 48.2% |
| ladder-1p5b-ocr-no-think-skeleton | 45.7% |
| ladder-1p5b-morphism-a-rejected | 32.9% |
| ladder-0p5b-hard-fn-norm-morphism-rejected | 27.4% |
| ladder-0p5b-hard-fn-norm-lora-rejected | 22.6% |
| ladder-0p5b-hard-fn-norm-morphism-lr5e5-rejected | 11.6% |

### MBPP

| Entry | Score |
|---|---|
| gad-coder-7b-canonical-assembly-2026-05-08 | 82.3% |
| ladder-7b-hard-fn-norm-canonical | 82.3% |
| qwen25-coder-7b-base-v3 | 80.5% |
| ladder-7b-ocr-fn-norm-rejected | 76.8% |
| qwen25-coder-3b-base-v1 | 74.4% |
| ladder-3b-ocr-fn-norm-rejected | 73.8% |
| ladder-1p5b-hard-retain-canonical | 64.0% |
| ladder-1p5b-ocr-fn-norm-canonical | 64.0% |
| ladder-1p5b-morphism-b-staging | 61.0% |
| qwen25-coder-1p5b-base-2026-05-08 | 61.0% |
| qwen25-coder-1p5b-base-v1 | 61.0% |
| ladder-1p5b-ocr-no-think-skeleton | 58.5% |
| ladder-1p5b-hard-only-rejected | 57.3% |
| qwen25-coder-0p5b-base-2026-05-08 | 51.8% |
| ladder-0p5b-hard-fn-norm-lora-rejected | 42.7% |
| ladder-0p5b-hard-fn-norm-morphism-lr5e5-rejected | 41.5% |
| ladder-1p5b-morphism-a-rejected | 40.2% |
| ladder-0p5b-hard-fn-norm-morphism-rejected | 37.8% |

## Total Deployed Parameters Over Time

| Entry | Added | Total Params | Active Params |
|---|---|---|---|
| qwen25-coder-1p5b-base-v1 | 2026-05-01 | 1,777,088,000 | 1777088000 |
| qwen25-coder-3b-base-v1 | 2026-05-01 | 3,099,175,936 | 3099175936 |
| qwen25-coder-7b-base-v3 | 2026-05-05 | 7,610,000,000 | 7610000000 |
| tooluse-sanity-v2-modal-l4 | 2026-05-07 | 7,628,460,000 | 7628460000 |
| gad-coder-7b-canonical-assembly-2026-05-08 | 2026-05-08 | 7,628,460,000 | 7.628B routed |
| ladder-1p5b-ocr-fn-norm-canonical | 2026-05-08 | 1,795,552,768 | 1795552768 |
| ladder-1p5b-ocr-no-think-skeleton | 2026-05-08 | 1,795,552,768 | 1795552768 |
| ladder-3b-ocr-fn-norm-rejected | 2026-05-08 | 3,117,640,704 | 3117640704 |
| ladder-7b-hard-fn-norm-canonical | 2026-05-08 | 7,628,460,000 | 7628460000 |
| ladder-7b-ocr-fn-norm-rejected | 2026-05-08 | 7,628,464,768 | 7628464768 |
