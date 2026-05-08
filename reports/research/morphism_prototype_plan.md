# Model Morphism Prototype Plan

**Owner**: Dr. Stein
**Status**: ready to execute. Architecture review GREEN (`reports/research/morphism_qwen2_arch_review.md`). Pending operator authorization for ~$3 fire.
**References**: slm-learning-158, 163, 165, 167 (proposed below)
**Status gate**: blocks EXP-009 in EXPERIMENTS.json

> **Operator lock 2026-05-08:** the morphism prototype must train
> on **0.5B-base-failure rows**, not on the existing 7B-hard rows
> or generic fn_norm. Training a 0.5B-architecture experiment on
> 7B's failure distribution would teach the wrong gaps. This adds
> a $0.40 prerequisite step (eval Qwen2.5-Coder-0.5B-Instruct on
> HumanEval n=164 to identify 0.5B's failure cases) before the
> dataset build can run.

## Hypothesis

Function-preserving model morphism (identity-initialized architecture expansion) costs significantly less than training a target-size model from scratch, while preserving learned features from the parent checkpoint. Testing at tiny scale (0.5B → ~0.7B) validates the technique before laddering to larger sizes.

## Target Base

**Primary**: `Qwen2.5-Coder-0.5B-Instruct` (HF Hub, ~500M active params)

**Fallback**: `Qwen2.5-Coder-1.5B-Instruct` if 0.5B unavailable or insufficient for meaningful expansion

Rationale: smallest viable coder; identity initialization cost is proportional to target_size, so tiny-first proves technique at lowest absolute cost.

---

## Morphism Method: Identity-Initialized Expansion

### Variant A: Linear Projection Between Blocks

**Architecture change**:
1. Load Qwen2.5-Coder-0.5B checkpoint
2. Identify a layer pair: layer_N → layer_N+1 (both transformer blocks)
3. Insert an identity-initialized linear projection layer:
   ```
   hidden_dim = 1920 (Qwen 0.5B hidden size)
   projection = nn.Linear(hidden_dim, hidden_dim)
   nn.init.eye_(projection.weight)  # identity initialization
   nn.init.zeros_(projection.bias)
   ```
4. Wire as: `output_N → projection → layer_N+1`

**Invariant**: At initialization, `model(x) ≈ baseline(x)` because projection is identity.

**Active params**: +1.92M (projection weight matrix)

**Training**: Only projection trained initially; option to unfreeze adjacent blocks in later epoch.

---

### Variant B: Block Duplication with Zero-Residual

**Architecture change**:
1. Load Qwen2.5-Coder-0.5B checkpoint
2. Duplicate one transformer block (layer_N → layer_N, copy):
3. Initialize duplicate's residual contribution to zero:
   ```
   # Duplicate block B' from B
   # Residual path: x → B(x) → B'(α·x) → output
   # Set α = 0 at init so B' output is zeroed
   ```
4. Gradually unfreeze α during training so new block contributes.

**Invariant**: At initialization, new block is dormant (α=0), so `model(x) ≈ baseline(x)`.

**Active params**: +~500M (full duplicate block)

**Training**: Train only the duplicated block weights + α scaling parameter; freeze original block and other layers.

---

## Verification at Initialization

**Before training any weights**, run the identity preservation test:

```python
def verify_morphism_init(base_model, morphed_model, test_prompts=20):
    """Assert morphed model ≈ base at initialization."""
    for prompt in test_prompts:
        tokens_base = base_model.generate(prompt, max_new_tokens=20)
        tokens_morphed = morphed_model.generate(prompt, max_new_tokens=20)
        
        # Token-level agreement (greedy decode, temp=0)
        agreement = sum(1 for a, b in zip(tokens_base, tokens_morphed) if a == b)
        agreement_pct = agreement / min(len(tokens_base), len(tokens_morphed))
        
        assert agreement_pct > 0.95, f"Init agreement {agreement_pct} < 95% on '{prompt[:30]}...'"
    
    print(f"✓ Function preservation verified: {100*agreement_pct:.1f}% token agreement on {len(test_prompts)} prompts")
```

**Test set**: 20 diverse code completion prompts (Python, JavaScript, multi-line).

**Pass criterion**: ≥95% token-level agreement on greedy decode (temp=0.0).

---

## Training

### Dataset (operator-locked 2026-05-08)

Use **0.5B-base-failure rows**: rows synthesized from
HumanEval cases where `Qwen2.5-Coder-0.5B-Instruct` fails, with
canonical solutions as the target. Rationale per
`scaling_proof_charter.md`: training a 0.5B-architecture
experiment on 7B's failure distribution would teach gaps that
don't apply to 0.5B. The 7B-hard dataset is the wrong shape for
this base.

**Build sequence (free + $0.40):**

1. Eval Qwen2.5-Coder-0.5B-Instruct on HumanEval n=164 (greedy,
   temp=0.0, EOS early-stop, 10s subprocess timeout per
   `AGENTS.md` Eval Pipeline Conventions). Cost: ~$0.40 on
   Modal A10G. Output:
   `tmp/diag-2026-05-08/base_he_0p5b_full.json`.
2. Run the existing dataset builder against the 0.5B results:

   ```
   python scripts/data/build_7b_hard_fn_norm_dataset.py \
       --results tmp/diag-2026-05-08/base_he_0p5b_full.json \
       --out data/processed/0p5b-hard-fn-norm-2026-05-08
   ```

   Output: `data/processed/0p5b-hard-fn-norm-2026-05-08/rows.jsonl`
   (~80–100 rows expected, since 0.5B base will fail more cases
   than 7B).

3. Update `tags` in the rows from `"7b-hard"` to `"0p5b-hard"`
   (one-line sed) and re-write `profile.json` source field. This
   is a small chore in the existing script that should be
   parameterized in a follow-up.

**Why not "broader instruction-following data":** generic
data-shape mixing is what made fn_norm regress at 3B and 7B
(`slm-learning-130`). The whole point of the morphism arm is to
test whether function-preserving capacity, trained on the
specific gaps the base has, beats a same-cost LoRA on the same
data. Adding a confounding generic corpus would dilute the
signal. Generic-corpus morphism is a follow-up cycle, not the
prototype.

(Historical alternatives, retained for context:)

- ~~Option A~~: `hard_fn_norm.jsonl` (58 rows from 7B failures) —
  rejected, wrong base distribution
- ~~Option B~~: Tiny instruction-following subset — deferred,
  generic-corpus confound

### Hyperparameters

| Param | Value | Rationale |
|-------|-------|-----------|
| `model` | Qwen2.5-Coder-0.5B + morphism (A or B) | baseline |
| `dataset` | hard_fn_norm.jsonl (58 rows) | fast iteration |
| `batch_size` | 4 (fits 6GB VRAM) | local GPU constraint |
| `lr` | 2e-4 (Variant A), 1e-4 (Variant B) | projection is sensitive; block duplication more stable |
| `epochs` | 3 | minimal overfitting on tiny corpus |
| `gradient_accumulation_steps` | 2 | effective batch 8 |
| `warmup_steps` | 10 (of ~45 total) | brief warmup for tiny run |
| `weight_decay` | 0.01 | light regularization |
| `max_grad_norm` | 1.0 | prevent projection explosion |
| `compute` | local-1660ti | 6GB baseline |
| `est_wall_time` | 2-3 minutes | 58 examples × 3 epochs ÷ eff. batch 8 |

**TRL SFTTrainer** config stub:
```yaml
model_id: "Qwen/Qwen2.5-Coder-0.5B-Instruct"
dataset_name: "hard_fn_norm"
output_dir: "experiments/runs/morphism_0p5b_variant_a_trial1"
num_train_epochs: 3
per_device_train_batch_size: 4
gradient_accumulation_steps: 2
learning_rate: 0.0002
lr_scheduler_type: "linear"
warmup_steps: 10
max_grad_norm: 1.0
weight_decay: 0.01
save_strategy: "epoch"
logging_steps: 5
report_to: ["tensorboard"]
```

---

## Comparison Arms (Four-Arm Study)

| Arm | Base | Method | Training | Active Params | Trainable Params |
|-----|------|--------|----------|---|---|
| **A** (baseline) | 0.5B | None | None | 500M | 0 |
| **B** (LoRA) | 0.5B | LoRA r=16 | hard_fn_norm.jsonl | 500M | 1.6M |
| **C** (morphism-A) | 0.5B + projection | Identity linear projection | hard_fn_norm.jsonl | 501.92M | 1.92M |
| **D** (morphism-B) | 0.5B + dup block | Block duplication + zero-residual | hard_fn_norm.jsonl | 1.0B | 500M |

**Execution order**: A (baseline eval only), B, C, D in parallel after A.

---

## Metrics

### 1. Function Preservation at Initialization (Pre-Training)

Arm C and D only:
```
Token agreement vs base: ___ %
Target: ≥95%
```

### 2. Post-Training Evaluation

All arms (A, B, C, D):

| Benchmark | Arm A (baseline) | Arm B (LoRA) | Arm C (morphism-A) | Arm D (morphism-B) | Delta C vs B | Delta D vs B |
|-----------|---|---|---|---|---|---|
| HumanEval n=20 (pass@1, greedy) | | | | | | |
| MBPP n=20 (pass@1, greedy) | | | | | | |
| hard_fn_norm holdout (5 cases) | | | | | | |

### 3. Efficiency Metrics

| Metric | Arm B | Arm C | Arm D |
|--------|-------|-------|-------|
| Training wall time (minutes) | | | |
| Training VRAM peak (GB) | | | |
| Checkpoint size (MB) | | | |
| Cost per param trained (USD / 1M trainable) | | | |
| Eval lift per million trained params | | | |

**Cost calculation**:
```
cost = (wall_time_hours * gpu_hourly_rate) / num_trainable_params_millions
Example: 3 min LoRA on Modal A10G @ $1/hr ÷ 1.6M params ≈ $0.0031 per 1M params trained
```

### 4. Scaling Projection

If Arm C or D shows promise:
- **Cost ratio**: training_cost_morphism ÷ training_cost_lora (target: ≤1.0 for competitive viability)
- **Param efficiency**: (eval_lift_C ÷ trainable_params_C) vs (eval_lift_B ÷ trainable_params_B)

---

## Pass Criteria

**Prototype succeeds if ALL of the following hold**:

1. **Function preservation** (Arm C, D): ≥95% token agreement at initialization
2. **Competitive training cost**: wall_time(C) ≤ 1.3 × wall_time(B) *or* wall_time(D) ≤ 1.3 × wall_time(B)
3. **Non-negative eval lift**: score(C_post) ≥ score(A_baseline) on at least one benchmark *or* score(D_post) ≥ score(A_baseline)
4. **Stability**: No NaNs, divergence, or GPU OOM during training of C or D

**If all pass**: Morphism technique is ready to ladder (0.5B → 1.5B → 3B → 7B).

---

## Risk Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|-----------|
| Qwen 0.5B coder not on HF Hub | Low | Fallback to 1.5B; adjust hyperparams (higher lr, fewer epochs) |
| Identity projection collapses during training | Medium | Use gradient clipping (max_grad_norm=1.0); monitor weight norms live; lower lr if diverging |
| HF transformers doesn't support arbitrary block insertion | Medium | Fork `modeling_qwen2.py` locally; insert projection in `forward()` method; test on CPU first |
| Training diverges on tiny dataset (58 examples) | Low | Add dropout to projection; increase weight decay; train fewer epochs |
| Block duplication OOM on 6GB GPU | Low | Use block duplication only on A10G arm; skip locally if needed |
| HumanEval n=20 insufficient signal | Low | Eval on full n=164 if any arm shows lift; costs ~2 min per arm |

---

## Implementation Plan (Do Not Execute Yet)

### Config Files

**File 1**: `experiments/configs/morphism/identity_projection_0p5b.json`
```json
{
  "exp_id": "EXP-009-morphism-projection",
  "model_id": "Qwen/Qwen2.5-Coder-0.5B-Instruct",
  "morphism_variant": "A_projection",
  "morphism_layer_pair": [7, 8],
  "dataset": "hard_fn_norm",
  "learning_rate": 0.0002,
  "num_epochs": 3,
  "batch_size": 4
}
```

**File 2**: `experiments/configs/morphism/identity_projection_block_dup_0p5b.json`
```json
{
  "exp_id": "EXP-009-morphism-blockdup",
  "model_id": "Qwen/Qwen2.5-Coder-0.5B-Instruct",
  "morphism_variant": "B_block_duplication",
  "dup_layer": 8,
  "dataset": "hard_fn_norm",
  "learning_rate": 0.0001,
  "num_epochs": 3,
  "batch_size": 4
}
```

### Scripts

**File 3**: `scripts/morphism/verify_function_preservation.py` (~100 LOC)
```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

def verify_init_identity(base_model_id, morphed_model_path, test_prompts=20):
    """Load base and morphed; assert token-level identity at init."""
    # Implementation: load both, generate, compare tokens
    pass
```

**File 4**: `scripts/morphism/train_with_identity_expansion.py` (~200 LOC)
```python
from trl import SFTTrainer
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer
import json

def train_morphism_variant(variant: str, config_path: str):
    """
    variant: 'A_projection' or 'B_block_dup'
    config_path: path to JSON config
    """
    # Load config, prepare dataset, wire morphism, train
    # Output: checkpoint + eval JSONs
    pass
```

**File 5**: `scripts/morphism/eval_morphism_arms.py` (~150 LOC)
```python
def evaluate_all_arms(base_eval_dir, lora_eval_dir, morphism_c_dir, morphism_d_dir):
    """Tabulate HumanEval + MBPP + hard_fn_norm results."""
    # Output: morphism_results.json (structured for report)
    pass
```

### Execution Checklist (operator-locked sequence 2026-05-08)

**Phase 0: prerequisites (~$0.40, ~5 min)**
- [ ] Verify Qwen2.5-Coder-0.5B-Instruct on HF Hub accessible (free)
- [ ] Eval 0.5B base on HumanEval n=164 → `tmp/diag-2026-05-08/base_he_0p5b_full.json` (Arm A baseline)
- [ ] Eval 0.5B base on MBPP n=164 → matching artifact (Arm A baseline)
- [ ] Build 0.5B-hard-fn-norm dataset via existing builder (free, local)

**Phase 1: implement morphism subclass (~$0, ~30 min)**
- [ ] Implement `IdentityProjectionLayer` from `morphism_qwen2_arch_review.md` (~50 LOC)
- [ ] Implement `expand_with_identity()` helper (~30 LOC)
- [ ] Run `verify_function_preservation.py` on (base, expanded) pair → assert 100% token agreement on 20 prompts (zero tolerance)

**Phase 2: train arms B + C in parallel (~$0.50, ~5 min)**
- [ ] Arm B: train LoRA r=16 on 0.5B base × 0.5B-hard-fn-norm
- [ ] Arm C: train morphism Variant A on 0.5B-expanded × 0.5B-hard-fn-norm

**Phase 3: eval all arms (~$1.60, ~30 min)**
- [ ] Arm A: 0.5B base × HE/MBPP n=164 (already done in Phase 0)
- [ ] Arm B: 0.5B + LoRA × HE/MBPP n=164
- [ ] Arm C: 0.5B-expanded + morphism × HE/MBPP n=164
- [ ] (Defer Arm D block-duplication unless A/B/C trio is positive)

**Phase 4: report + decision (~$0, ~30 min)**
- [ ] Aggregate to `reports/evals/morphism_0p5b_variant_a_2026-05-XX.md`
- [ ] Update `reports/scaling/gad_scaling_ledger.md` with new entries
- [ ] Assess against pass criteria
- [ ] Log decision (slm-learning-167 if pass, slm-learning-167-falsify if fail)
- [ ] If pass: queue morphism-1p5b variant for next iteration
- [ ] If fail: document falsification, do not bury — per `slm-learning-122` durable transfer artifacts, falsifications are publishable

**Total cost ~$2.50, total wall ~70 min, gated by operator authorization.**

---

## Implementability Assessment

**Status**: Implementable as-described, with **one research gate**: HF transformers integration for arbitrary layer insertion.

**Gate detail**: Qwen2's modeling code must allow mid-network layer injection without breaking positional encodings or attention masks. This requires either:
1. Modifying `transformers/models/qwen2/modeling_qwen2.py` locally (safe, tested approach)
2. Subclassing `Qwen2ForCausalLM` and overriding `forward()` (cleaner, less risky)

**Pre-flight research**: Spend ~30 minutes confirming Qwen2 block structure is amenable to identity-initialized insertion. If architecture uses absolute positional embeddings that must stay tied to layer indices, the insertion strategy changes (post-block instead of mid-block).

**Recommendation**: Execute 30-minute architecture review of `Qwen2ForCausalLM.forward()` before firing training. If structure is flexible, proceed immediately. If not, variant A (projection between existing blocks) becomes the primary path, and variant B defers to a custom MoE upcycling script.

---

## Decision References

- **slm-learning-158**: Morphism as function-preserving expansion (principle)
- **slm-learning-163**: Tiny-first experimental validation (policy)
- **slm-learning-165**: Qwen2 morphism Variant A architecture review GREEN
- **slm-learning-130**: Gap-targeted training is canonical scale recipe (basis for "use base-failure rows, not generic")
- **scaling_proof_charter.md Arm 2**: this prototype IS Arm 2; pre-registered pass/fail criteria live there

## Next Milestone

- **If pass**: Author `scripts/morphism/apply_expansion_ladder.py` to semi-automate 0.5B → 1.5B → 3B morphism chain
- **If fail**: Revert to pure LoRA on upscaling path; morphism becomes optional research lane
