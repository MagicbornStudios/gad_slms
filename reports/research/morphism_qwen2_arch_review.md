# Qwen2 architecture review for morphism (lane 10)

**Date:** 2026-05-08
**Reviewer:** Dr. Stein
**Source:** `.venv-gpu/Lib/site-packages/transformers/models/qwen2/modeling_qwen2.py`
**Decision refs:** `slm-learning-158`, `slm-learning-163`
**Gate status:** **GREEN for Variant A (identity projection). YELLOW (workable) for Variant B (block duplication).**

---

## Verdict

Identity-init layer insertion is feasible in Qwen2 with a tiny subclass (~50 LOC). Function preservation at initialization is **guaranteed by construction**, not empirically hoped for. The morphism prototype can fire immediately on Variant A.

---

## What I read

| Component | Lines | Relevance |
|---|---|---|
| `Qwen2RotaryEmbedding.forward` | 51–113 | Where RoPE cos/sin come from |
| `apply_rotary_pos_emb` | 124–146 | Per-attention RoPE application |
| `Qwen2Attention.__init__` + `.forward` | 187–245 | The KV cache constraint |
| `Qwen2DecoderLayer.forward` | 269–309 | Block boundary and signature |
| `Qwen2Model.__init__` + `.forward` | 332–413 | Layer iteration and mask wiring |

---

## The four feasibility checks

### 1. Positional encoding (RoPE) — ✅ no constraint

RoPE is computed **once** at `Qwen2Model.forward` line 396:

```python
position_embeddings = self.rotary_emb(hidden_states, position_ids)
```

The same `(cos, sin)` tuple is then **passed to every layer** (line 402). RoPE is a function of `position_ids`, not of layer index. **Adding a layer does not change positional embeddings for any other layer.** This kills the biggest hypothetical concern from the morphism plan.

### 2. Attention mask — ✅ index-by-position works

Mask is selected per-layer at line 401:

```python
attention_mask=causal_mask_mapping[self.config.layer_types[i]]
```

`layer_types` is a list keyed by position (the `i` in `enumerate`). To insert a layer at position N, we must extend `layer_types` to length `num_hidden_layers + 1`. For an identity-projection layer that has no attention, the value at the new index is irrelevant — the new layer ignores `attention_mask` entirely. We pass `"full_attention"` as a safe placeholder.

### 3. KV cache and `layer_idx` — ✅ for Variant A, ⚠️ for Variant B

This is the only real constraint. `Qwen2Attention.__init__` stores `self.layer_idx = layer_idx` (line 194), and `forward` calls `past_key_values.update(key_states, value_states, self.layer_idx)` (line 225).

- **Variant A (identity projection)**: the new layer has **no attention**, so no KV slot. Cache untouched. No conflict.
- **Variant B (block duplication)**: the duplicated block has its own attention and needs a fresh `layer_idx`. `DynamicCache` (the default at line 370) grows on demand keyed by `layer_idx`, so allocating one more slot is fine — but every cache allocator must handle it. Static caches with fixed shape fail. Verdict: workable, but every inference path that uses Variant B must run on `DynamicCache` until proven on others.

### 4. Layer iteration count — ✅ explicit slice

Forward loop at line 398:

```python
for i, decoder_layer in enumerate(self.layers[: self.config.num_hidden_layers]):
```

Inserting into `self.layers` is **not enough** — we must also bump `config.num_hidden_layers`, otherwise the new layer is silently dropped. This is a footgun worth a comment in the patch.

---

## Simplest insertion strategy (Variant A)

```python
import torch.nn as nn
from transformers.models.qwen2.modeling_qwen2 import Qwen2RMSNorm, Qwen2ForCausalLM


class IdentityProjectionLayer(nn.Module):
    """Identity-init residual block. At t=0, model(x) ≡ base(x)."""

    def __init__(self, hidden_size: int, eps: float = 1e-6):
        super().__init__()
        self.norm = Qwen2RMSNorm(hidden_size, eps=eps)
        self.proj = nn.Linear(hidden_size, hidden_size, bias=True)
        nn.init.zeros_(self.proj.weight)
        nn.init.zeros_(self.proj.bias)

    def forward(
        self,
        hidden_states,
        attention_mask=None,
        position_ids=None,
        past_key_values=None,
        use_cache=False,
        position_embeddings=None,
        **kwargs,
    ):
        return hidden_states + self.proj(self.norm(hidden_states))


def expand_with_identity(model: Qwen2ForCausalLM, insert_after: int) -> Qwen2ForCausalLM:
    inner = model.model
    cfg = inner.config
    new_layer = IdentityProjectionLayer(cfg.hidden_size, cfg.rms_norm_eps)
    new_layer = new_layer.to(device=next(inner.parameters()).device,
                             dtype=next(inner.parameters()).dtype)
    inner.layers.insert(insert_after + 1, new_layer)
    cfg.num_hidden_layers += 1
    if hasattr(cfg, "layer_types"):
        cfg.layer_types = list(cfg.layer_types)
        cfg.layer_types.insert(insert_after + 1, "full_attention")
    return model
```

**Function preservation at t=0 is guaranteed**: `proj.weight = 0` and `proj.bias = 0` ⇒ `proj(norm(x)) = 0` ⇒ output is bit-exact with the base model. The ≥95% token-agreement check from the morphism plan should produce 100% — if it doesn't, the patch has a bug.

**Trainable params introduced**:

| Base | hidden_size | Identity params (h² + h) | Frac of base |
|---|---|---|---|
| Qwen2.5-Coder-0.5B | 896 | 803 712 | 0.16% |
| Qwen2.5-Coder-1.5B | 1536 | 2 360 832 | 0.13% |
| Qwen2.5-Coder-3B | 2048 | 4 196 352 | 0.14% |
| Qwen2.5-Coder-7B | 3584 | 12 851 712 | 0.17% |

For the 0.5B base in the morphism prototype plan, this is **less trainable surface than a LoRA r=16 adapter** (~1.6M). So Variant A is even cheaper than the prototype plan estimated.

---

## What still needs verification before training

The verdict is GREEN on the architecture. Two things to confirm in the actual training run:

1. **Loading and saving round-trip.** `model.save_pretrained()` followed by `Qwen2ForCausalLM.from_pretrained(path)` must reconstruct the modified model exactly. Risk: the saved config has `num_hidden_layers + 1`, but `from_pretrained` instantiates `num_hidden_layers + 1` standard `Qwen2DecoderLayer`s and then can't load the `IdentityProjectionLayer` weights. Mitigation: save the identity layer's weights with a non-conflicting prefix and load them via a hook. Or skip reload and train end-to-end in one process.
2. **Generation path.** `model.generate()` calls `forward()` repeatedly with `use_cache=True`. The identity layer accepts the kwargs but doesn't touch the cache, which is what we want. Risk: a kernel-fused path (FlashAttention, SDPA) might assume layer-index contiguity. Mitigation: run a single greedy generate in eager mode first to confirm.

Neither is a blocker. Both are 5-minute checks before the real training run.

---

## Open question for Variant B (block duplication)

The "real" morphism — duplicate a transformer block, zero-init the residual contribution — needs:

1. `deepcopy` the existing layer at index N
2. Wrap it so the residual is `x + α · block_out(x)` with `α = 0` at init
3. Allocate a new `layer_idx` for its attention's KV slot

The plan in `morphism_prototype_plan.md` calls this Variant B and it's also workable, but Variant A is sufficient to test the **methodology** at lowest absolute cost. If Variant A produces a positive lift on `hard_fn_norm`, Variant B becomes the next experiment, not the first.

---

## Cost projection (revised vs. morphism_prototype_plan.md)

| Arm | Trainable params | Wall (predicted) | Cost (predicted) |
|---|---|---|---|
| A (baseline 0.5B) | 0 | n/a (eval only) | $0.40 (eval) |
| B (LoRA r=16 on 0.5B) | ~1.6M | 2 min | $0.05 train + $0.40 eval |
| **C (identity projection 0.5B → 0.5B + 0.8M)** | **~0.8M** | **2 min** | **$0.05 train + $0.40 eval** |
| D (block duplication 0.5B → 1.0B) | ~500M | 10 min | $0.20 train + $0.40 eval |

Total prototype: ~$2 to fire all four arms. Within budget; can run today.

---

## Recommendation

1. **Fire Variant A immediately** when you authorize compute — it's the cleanest test of the morphism principle and costs ~$0.50 end-to-end.
2. **Defer Variant B** until A produces a positive (or clearly negative) result. Cheaper experiments first per `slm-learning-126`.
3. **Pre-register** the function-preservation invariant: `assert torch.allclose(base_logits, expanded_logits, atol=1e-5)` on 20 prompts at init. If this fails, the patch has a bug — do not train, debug first.
4. **Save Variant A's checkpoint** as `morphism-0p5b-projection-2026-05-XX/` per the 3-artifact rule (`slm-learning-096`).

---

## Cross-references

- `reports/research/morphism_prototype_plan.md` — original prototype plan, this review unblocks its execution checklist
- `slm-learning-158` — morphism principle (function-preserving expansion)
- `slm-learning-163` — tiny-first experimental validation policy
- `slm-learning-126` — smallest salvageable piece first

— Dr. Stein, Qwen2 morphism architecture review 2026-05-08
