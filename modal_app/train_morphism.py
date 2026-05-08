"""Modal training app for morphism Variant A — identity-init layer expansion.

Per slm-learning-165 (architecture review GREEN) and slm-learning-169
(dataset locked to base-failure rows). This is the morphism analog of
train_lora.py:

  - Loads base Qwen2 model
  - Inserts an IdentityProjectionLayer (zero-init linear projection +
    RMSNorm in a residual block) at a chosen position
  - Verifies init agreement vs base model on a small prompt set BEFORE
    training (assert >=99% token agreement; zero tolerance per charter)
  - Trains ONLY the projection layer's weight + bias (everything else
    frozen)
  - Saves the modified model + reports trainable param count

Companion to:
  - reports/research/morphism_qwen2_arch_review.md (the architecture rationale)
  - reports/research/morphism_prototype_plan.md (Phases 0-4)

Usage:
    modal run modal_app/train_morphism.py::main \\
        --spec-path experiments/configs/morphism/morphism_0p5b_variant_a.json \\
        --gpu A10G
"""
from __future__ import annotations

import json
from pathlib import Path

import modal


app = modal.App("slm-learning-train-morphism")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.9.1",
        "transformers>=4.50",
        "peft>=0.15",
        "trl>=0.20",
        "datasets>=3.0",
        "accelerate>=1.0",
        "huggingface_hub>=0.30",
        "pyarrow",
    )
)

data_volume = modal.Volume.from_name("slm-data", create_if_missing=True)
models_volume = modal.Volume.from_name("slm-models", create_if_missing=True)


# Copied verbatim from morphism_qwen2_arch_review.md.
# Loaded into the Modal image at runtime via inlining below; this constant
# documents the contract.
IDENTITY_PROJECTION_LAYER_SRC = '''
import torch
import torch.nn as nn
from transformers.models.qwen2.modeling_qwen2 import Qwen2RMSNorm


class IdentityProjectionLayer(nn.Module):
    """Identity-init residual block. At t=0, model(x) === base(x)."""

    def __init__(self, hidden_size: int, eps: float = 1e-6):
        super().__init__()
        self.hidden_size = hidden_size
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
        cache_position=None,
        position_embeddings=None,
        **kwargs,
    ):
        return hidden_states + self.proj(self.norm(hidden_states))
'''


@app.function(
    image=image,
    gpu="A10G",
    volumes={"/data": data_volume, "/models": models_volume},
    timeout=10800,
    cpu=4,
    memory=32_768,
)
def train_morphism_a10g(spec: dict) -> dict:
    return _train_morphism_inner(spec)


@app.function(
    image=image,
    gpu="A100",
    volumes={"/data": data_volume, "/models": models_volume},
    timeout=14400,
    cpu=8,
    memory=65_536,
)
def train_morphism_a100(spec: dict) -> dict:
    return _train_morphism_inner(spec)


def _train_morphism_inner(spec: dict) -> dict:
    import datetime as dt
    import time
    import traceback

    import torch
    import torch.nn as nn
    from datasets import Dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
    from transformers.models.qwen2.modeling_qwen2 import Qwen2RMSNorm
    from trl import SFTTrainer, SFTConfig

    t_start = time.time()
    run_id = spec["run_id"]
    base_model = spec["base_model"]
    dataset_path = spec["dataset_volume_path"]
    sys_prompt = spec.get("system_prompt", "You are a coding assistant.")
    instr_field = spec.get("instruction_field", "input")
    resp_field = spec.get("response_field", "target")
    max_length = spec.get("max_length", 1024)
    train_cfg = spec["training"]
    morphism_cfg = spec.get("morphism", {})
    insert_after = morphism_cfg.get("insert_after_layer", 7)
    init_check = morphism_cfg.get("init_check", {})
    init_prompts = init_check.get("prompts", [
        "def hello():",
        "import math\nfrom typing import List",
        "def fibonacci(n: int) -> int:",
        "class Stack:",
        "for i in range(10):",
    ])
    init_max_new = init_check.get("max_new_tokens", 16)
    init_min_agreement = init_check.get("min_agreement", 0.99)
    hub_repo = spec.get("hub_repo")

    out_dir = Path(f"/models/runs/{run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[morphism] run_id={run_id}")
    print(f"[morphism] base={base_model} dataset={dataset_path}")
    print(f"[morphism] insert_after_layer={insert_after}")
    if torch.cuda.is_available():
        print(f"[morphism] gpu_visible: {torch.cuda.get_device_name(0)}")
    else:
        print("[morphism] gpu_visible: NONE")

    # --- 1. Load tokenizer + base
    tok = AutoTokenizer.from_pretrained(base_model)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    dtype = torch.bfloat16 if train_cfg.get("bf16", True) else torch.float16

    print(f"[morphism] loading base in {dtype} ...")
    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        dtype=dtype,
        device_map="auto",
    )
    base.eval()

    # --- 2. Build a fresh expanded model (NOT the same instance as base)
    # We need TWO instances on the device for the init-agreement check.
    print("[morphism] loading second copy for expansion + init-check ...")
    expanded = AutoModelForCausalLM.from_pretrained(
        base_model,
        dtype=dtype,
        device_map="auto",
    )

    inner = expanded.model
    cfg = inner.config
    hidden_size = cfg.hidden_size
    num_hidden_before = cfg.num_hidden_layers
    print(f"[morphism] base hidden_size={hidden_size} num_hidden_layers={num_hidden_before}")

    # Variant A: identity-init projection layer (single high-leverage chokepoint)
    class IdentityProjectionLayer(nn.Module):
        def __init__(self, hidden_size: int, eps: float = 1e-6):
            super().__init__()
            self.hidden_size = hidden_size
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
            cache_position=None,
            position_embeddings=None,
            **kwargs,
        ):
            return hidden_states + self.proj(self.norm(hidden_states))

    # Variant C: late gated residual with SMALL-NONZERO init throughout.
    # Per slm-learning-181: Variant B's chicken-and-egg gate-stickiness
    # is fixed by giving up_proj small-random weights (not zero) and
    # gate small nonzero (not zero). Function preservation is approximate
    # (>=99% token agreement), not bit-exact, in exchange for trainability.
    # y = x + gate * up(silu(down(norm(x)))) with:
    #   gate init = small nonzero (default 0.01)
    #   up_proj init = kaiming * 0.01 (small-random, not zero)
    #   down_proj init = kaiming (full)
    class GatedResidualLayerC(nn.Module):
        def __init__(self, hidden_size: int, bottleneck_size: int,
                     eps: float = 1e-6, gate_init: float = 0.01,
                     up_scale: float = 0.01):
            super().__init__()
            self.hidden_size = hidden_size
            self.bottleneck_size = bottleneck_size
            self.norm = Qwen2RMSNorm(hidden_size, eps=eps)
            self.down = nn.Linear(hidden_size, bottleneck_size, bias=True)
            self.up = nn.Linear(bottleneck_size, hidden_size, bias=True)
            self.gate = nn.Parameter(torch.full((1,), float(gate_init)))
            self.act = nn.SiLU()
            nn.init.kaiming_uniform_(self.down.weight, a=5**0.5)
            nn.init.zeros_(self.down.bias)
            nn.init.kaiming_uniform_(self.up.weight, a=5**0.5)
            with torch.no_grad():
                self.up.weight.mul_(float(up_scale))
            nn.init.zeros_(self.up.bias)

        def forward(
            self, hidden_states, attention_mask=None, position_ids=None,
            past_key_values=None, use_cache=False, cache_position=None,
            position_embeddings=None, **kwargs,
        ):
            h = self.norm(hidden_states)
            h = self.up(self.act(self.down(h)))
            return hidden_states + self.gate * h

    # Variant B: gated zero-init bottleneck residual (safer growth structure).
    # y = x + gate * up(silu(down(norm(x)))), with gate=0 AND up.weight=0 at
    # init. Two layers of safety: gate scales the contribution from 0;
    # zero-init up_proj means Bottleneck(x)=0 even if gate departs from 0.
    # Per operator review 2026-05-08 (slm-learning-172): expected to be more
    # forgiving than Variant A under tiny-data fine-tuning at small bases.
    class GatedBottleneckLayer(nn.Module):
        def __init__(self, hidden_size: int, bottleneck_size: int,
                     eps: float = 1e-6):
            super().__init__()
            self.hidden_size = hidden_size
            self.bottleneck_size = bottleneck_size
            self.norm = Qwen2RMSNorm(hidden_size, eps=eps)
            self.down = nn.Linear(hidden_size, bottleneck_size, bias=True)
            self.up = nn.Linear(bottleneck_size, hidden_size, bias=True)
            self.gate = nn.Parameter(torch.zeros(1))
            self.act = nn.SiLU()
            # down init: small kaiming so it starts near uniform random
            nn.init.kaiming_uniform_(self.down.weight, a=5**0.5)
            nn.init.zeros_(self.down.bias)
            # up init: zero — guarantees Bottleneck(x) = 0 at init
            nn.init.zeros_(self.up.weight)
            nn.init.zeros_(self.up.bias)
            # gate init: zero — guarantees y = x at init even if up wasn't 0

        def forward(
            self,
            hidden_states,
            attention_mask=None,
            position_ids=None,
            past_key_values=None,
            use_cache=False,
            cache_position=None,
            position_embeddings=None,
            **kwargs,
        ):
            h = self.norm(hidden_states)
            h = self.up(self.act(self.down(h)))
            return hidden_states + self.gate * h

    # Match dtype/device of the model being expanded
    target_device = next(inner.parameters()).device
    variant = morphism_cfg.get("variant", "A_identity_projection")
    if variant == "A_identity_projection":
        new_layer = IdentityProjectionLayer(hidden_size, cfg.rms_norm_eps).to(
            device=target_device, dtype=dtype
        )
    elif variant == "B_gated_bottleneck":
        bottleneck_size = morphism_cfg.get(
            "bottleneck_size", max(64, hidden_size // 4)
        )
        new_layer = GatedBottleneckLayer(
            hidden_size, bottleneck_size, cfg.rms_norm_eps
        ).to(device=target_device, dtype=dtype)
        print(f"[morphism] Variant B: bottleneck_size={bottleneck_size}")
    elif variant == "C_gated_residual":
        bottleneck_size = morphism_cfg.get(
            "bottleneck_size", max(64, hidden_size // 4)
        )
        gate_init = morphism_cfg.get("gate_init", 0.01)
        up_scale = morphism_cfg.get("up_scale", 0.01)
        new_layer = GatedResidualLayerC(
            hidden_size, bottleneck_size, cfg.rms_norm_eps,
            gate_init=gate_init, up_scale=up_scale,
        ).to(device=target_device, dtype=dtype)
        print(f"[morphism] Variant C: bottleneck_size={bottleneck_size} "
              f"gate_init={gate_init} up_scale={up_scale}")
    else:
        return {"run_id": run_id, "status": "error",
                "error": f"unknown morphism.variant {variant!r}"}

    insert_pos = insert_after + 1
    layers = list(inner.layers)
    layers.insert(insert_pos, new_layer)
    inner.layers = nn.ModuleList(layers)
    cfg.num_hidden_layers = num_hidden_before + 1
    if hasattr(cfg, "layer_types") and cfg.layer_types is not None:
        new_layer_types = list(cfg.layer_types)
        new_layer_types.insert(insert_pos, "full_attention")
        cfg.layer_types = new_layer_types

    print(f"[morphism] expanded num_hidden_layers={cfg.num_hidden_layers} "
          f"(inserted at index {insert_pos})")

    # --- 3. Init-agreement check vs base
    print("[morphism] running init-agreement check ...")
    base.eval()
    expanded.eval()
    agreements = []
    per_prompt = []
    for p in init_prompts:
        ids = tok(p, return_tensors="pt").to(target_device)
        with torch.no_grad():
            out_b = base.generate(
                **ids,
                max_new_tokens=init_max_new,
                do_sample=False,
                pad_token_id=tok.pad_token_id,
            )
            out_e = expanded.generate(
                **ids,
                max_new_tokens=init_max_new,
                do_sample=False,
                pad_token_id=tok.pad_token_id,
            )
        new_b = out_b[0][ids["input_ids"].shape[1]:].tolist()
        new_e = out_e[0][ids["input_ids"].shape[1]:].tolist()
        n = min(len(new_b), len(new_e))
        if n == 0:
            agreement = 1.0
        else:
            matches = sum(1 for a, b in zip(new_b[:n], new_e[:n]) if a == b)
            agreement = matches / n
        agreements.append(agreement)
        per_prompt.append({
            "prompt": p,
            "agreement": agreement,
            "base_tokens": new_b[:n],
            "expanded_tokens": new_e[:n],
        })
        print(f"[morphism] init-check prompt={p[:30]!r} agreement={agreement:.3f}")

    mean_agreement = sum(agreements) / max(1, len(agreements))
    print(f"[morphism] mean init agreement = {mean_agreement:.4f} "
          f"(threshold {init_min_agreement})")

    # Free base immediately to reclaim VRAM
    del base
    torch.cuda.empty_cache()

    if mean_agreement < init_min_agreement:
        return {
            "run_id": run_id,
            "status": "init_check_failed",
            "mean_agreement": mean_agreement,
            "per_prompt": per_prompt,
            "error": f"Init agreement {mean_agreement:.4f} < threshold "
                     f"{init_min_agreement}. Patch is broken; do not train.",
        }

    # --- 4. Freeze everything EXCEPT the inserted projection layer
    trainable_module = inner.layers[insert_pos]
    for name, p in expanded.named_parameters():
        p.requires_grad_(False)
    for p in trainable_module.parameters():
        p.requires_grad_(True)
    trainable = sum(p.numel() for p in expanded.parameters() if p.requires_grad)
    total = sum(p.numel() for p in expanded.parameters())
    print(f"[morphism] trainable params: {trainable/1e6:.3f}M / "
          f"{total/1e6:.2f}M ({100*trainable/total:.4f}%)")

    # --- 5. Load + format dataset
    if dataset_path.endswith(".jsonl"):
        ds = Dataset.from_json(dataset_path)
    elif dataset_path.endswith(".parquet"):
        ds = Dataset.from_parquet(dataset_path)
    else:
        return {"run_id": run_id, "status": "error",
                "error": f"unknown dataset format: {dataset_path}"}
    print(f"[morphism] loaded {len(ds)} rows from {dataset_path}")

    def to_text(row: dict) -> dict:
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": str(row.get(instr_field, ""))},
            {"role": "assistant", "content": str(row.get(resp_field, ""))},
        ]
        try:
            text = tok.apply_chat_template(messages, tokenize=False)
        except Exception:
            text = (f"<|system|>{sys_prompt}\n"
                    f"<|user|>{row.get(instr_field, '')}\n"
                    f"<|assistant|>{row.get(resp_field, '')}\n")
        return {"text": text}

    ds_fmt = ds.map(to_text, remove_columns=ds.column_names)

    # --- 6. SFT training, only the inserted layer is trainable
    sft_cfg = SFTConfig(
        output_dir=str(out_dir / "checkpoints"),
        num_train_epochs=train_cfg.get("epochs", 3),
        learning_rate=train_cfg.get("lr", 2e-4),
        per_device_train_batch_size=train_cfg.get("batch_size", 4),
        gradient_accumulation_steps=train_cfg.get("grad_accum", 4),
        warmup_ratio=train_cfg.get("warmup_ratio", 0.05),
        weight_decay=train_cfg.get("weight_decay", 0.0),
        bf16=train_cfg.get("bf16", True),
        fp16=train_cfg.get("fp16", False),
        gradient_checkpointing=False,  # disabled for tiny trainable surface
        seed=train_cfg.get("seed", 42),
        save_strategy="no",
        logging_steps=train_cfg.get("logging_steps", 5),
        max_length=max_length,
        max_grad_norm=train_cfg.get("max_grad_norm", 1.0),
        report_to="none",
    )

    trainer = SFTTrainer(
        model=expanded,
        args=sft_cfg,
        train_dataset=ds_fmt,
        processing_class=tok,
    )
    print(f"[morphism] starting SFT — "
          f"{sft_cfg.num_train_epochs} epochs, "
          f"bs={sft_cfg.per_device_train_batch_size}, "
          f"grad_accum={sft_cfg.gradient_accumulation_steps}, "
          f"lr={sft_cfg.learning_rate}")
    try:
        train_result = trainer.train()
        train_status = "ok"
        train_loss = float(train_result.training_loss)
        train_metrics = dict(train_result.metrics)
    except Exception as e:
        traceback.print_exc()
        return {"run_id": run_id, "status": "trainer_failed",
                "error": str(e)[:400]}

    # --- 7. Save the FULL modified model (not just the layer) so it can
    # be loaded back as a CausalLM. Adapter-style save isn't right here —
    # the whole architecture is now different.
    model_dir = out_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    expanded.save_pretrained(str(model_dir))
    tok.save_pretrained(str(model_dir))

    # Also save just the inserted layer's state-dict separately for
    # provenance + cheap reload paths.
    layer_state = trainable_module.state_dict()
    torch.save(layer_state, str(out_dir / "identity_projection_layer.pt"))

    # --- 8. Optional HF push
    hub_url = None
    if hub_repo:
        try:
            from huggingface_hub import HfApi
            api = HfApi()
            api.create_repo(hub_repo, repo_type="model", exist_ok=True,
                            private=spec.get("hub_private", False))
            api.upload_folder(folder_path=str(model_dir),
                              repo_id=hub_repo, repo_type="model")
            hub_url = f"https://huggingface.co/{hub_repo}"
            print(f"[morphism] pushed -> {hub_url}")
        except Exception as e:
            print(f"[morphism] hub push failed: {e!r}")

    wall_seconds = round(time.time() - t_start, 1)

    manifest = {
        "schema_v": 1,
        "run_id": run_id,
        "ts_completed": dt.datetime.now(dt.timezone.utc).isoformat(),
        "compute_target": f"modal-{spec.get('gpu', 'A10G').lower()}",
        "wall_seconds": wall_seconds,
        "wall_hours": round(wall_seconds / 3600, 2),
        "base_model": base_model,
        "dataset_volume_path": dataset_path,
        "n_train_rows": len(ds_fmt),
        "morphism": {
            "variant": variant,
            "insert_after_layer": insert_after,
            "insert_position_index": insert_pos,
            "num_hidden_before": num_hidden_before,
            "num_hidden_after": cfg.num_hidden_layers,
            "init_agreement_mean": mean_agreement,
            "init_agreement_per_prompt": per_prompt,
            "bottleneck_size": morphism_cfg.get("bottleneck_size") if variant in ("B_gated_bottleneck", "C_gated_residual") else None,
            "gate_init": morphism_cfg.get("gate_init") if variant == "C_gated_residual" else None,
            "up_scale": morphism_cfg.get("up_scale") if variant == "C_gated_residual" else None,
        },
        "training": train_cfg,
        "training_loss": train_loss,
        "training_metrics": train_metrics,
        "trainable_params_M": round(trainable / 1e6, 4),
        "total_params_M": round(total / 1e6, 2),
        "trainable_fraction_pct": round(100 * trainable / total, 4),
        "hub_url": hub_url,
        "model_volume_path": str(model_dir),
        "decision_refs": ["slm-learning-130", "slm-learning-158",
                          "slm-learning-163", "slm-learning-165",
                          "slm-learning-169"],
        "status": train_status,
    }
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    models_volume.commit()

    print(f"[morphism] DONE run_id={run_id} wall={wall_seconds}s "
          f"loss={train_loss:.4f} hub={hub_url}")
    return manifest


@app.local_entrypoint()
def main(spec_path: str = "", gpu: str = "A10G") -> None:
    if not spec_path:
        print("usage: modal run modal_app/train_morphism.py "
              "--spec-path <path> [--gpu A10G|A100]")
        return
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    spec.setdefault("gpu", gpu)
    print(f"[main] firing morphism {spec['run_id']} on Modal {gpu}...")
    fn = {"A10G": train_morphism_a10g, "A100": train_morphism_a100}.get(
        gpu, train_morphism_a10g)
    result = fn.remote(spec)
    print()
    print(json.dumps(result, indent=2)[:3000])
