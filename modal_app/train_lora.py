"""Modal LoRA/QLoRA training app — runs SFT on a chosen GPU class.

Per slm-learning-105: training moves to Modal so the local 1660 Ti
stops being the bottleneck. Per slm-learning-097: $50-shot discipline
applies; this is the small-runs-on-Modal path that builds toward shots
without burning shot budget.

Design

- Mounts two Modal volumes:
    /data    — slm-data (datasets, telemetry, eval gold)
    /models  — slm-models (adapter outputs, lineage tracking)
- Reads a JSON spec describing base model + dataset path on volume +
  LoRA params + training params + HF Hub push target.
- Uses TRL SFTTrainer + PEFT.
- Saves adapter + MANIFEST.json to /models/<run-id>/.
- Pushes adapter to HF Hub if HF_TOKEN secret is mounted.
- Per slm-learning-096, captures (weights + outputs corpus + regression
  journal placeholder) for downstream curriculum distillation.

Usage

    # Tool-use v2 retry on Modal L4
    modal run modal_app/train_lora.py::train --spec '@experiments/configs/remote/tooluse_v2.json'

    # Scaling-ladder rungs in parallel
    modal run modal_app/train_lora.py::train_many --specs-dir experiments/configs/remote-ladder/

Each spec is a JSON file:

    {
      "run_id": "tooluse-v2-modal-l4-2026-05-08",
      "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
      "dataset_volume_path": "/data/processed/gad-telemetry/sft_tooluse.jsonl",
      "system_prompt": "...",
      "instruction_field": "instruction",
      "response_field": "command",
      "max_length": 512,
      "lora": {"r": 16, "alpha": 32, "dropout": 0.05,
               "target_modules": ["q_proj","k_proj","v_proj","o_proj",
                                  "gate_proj","up_proj","down_proj"]},
      "training": {"epochs": 3, "lr": 2e-4, "batch_size": 4,
                   "grad_accum": 4, "warmup_ratio": 0.05, "bf16": true,
                   "gradient_checkpointing": true, "seed": 42},
      "gpu": "L4",
      "timeout_seconds": 5400,
      "hub_repo": "scrubster/dr-stein-tooluse-v2-modal"
    }

Decision refs: slm-learning-094 (composition), 096 (3-artifact rule),
097 (shot discipline), 105 (hardware policy).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import modal


app = modal.App("slm-learning-train-lora")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.9.1",
        "transformers>=4.50",
        "peft>=0.15",
        "trl>=0.20",
        "datasets>=3.0",
        "accelerate>=1.0",
        "bitsandbytes>=0.43",
        "huggingface_hub>=0.30",
        "pyarrow",
        "pyyaml",
    )
)

data_volume = modal.Volume.from_name("slm-data", create_if_missing=True)
models_volume = modal.Volume.from_name("slm-models", create_if_missing=True)

# HF token is optional. Operator creates it once with:
#   modal secret create hf-token HF_TOKEN=hf_...
# If absent, the trainer skips the Hub push and saves only to the
# slm-models volume. The adapter is still recoverable via volume.
try:
    hf_secret = modal.Secret.from_name("hf-token", required_keys=["HF_TOKEN"])
    HF_SECRETS = [hf_secret]
except Exception:
    HF_SECRETS = []


GPU_FLAVORS = {
    "T4": "T4",
    "L4": "L4",
    "A10G": "A10G",
    "A100": "A100-40GB",
    "A100-80GB": "A100-80GB",
    "H100": "H100",
}


@app.function(
    image=image,
    gpu="L4",
    volumes={"/data": data_volume, "/models": models_volume},
    secrets=HF_SECRETS,
    timeout=10800,
    cpu=4,
    memory=32_768,
)
def train(spec: dict) -> dict:
    """Run one training spec end-to-end on the configured GPU."""
    return _train_inner(spec)


@app.function(
    image=image,
    gpu="A10G",
    volumes={"/data": data_volume, "/models": models_volume},
    secrets=HF_SECRETS,
    timeout=10800,
    cpu=4,
    memory=32_768,
)
def train_a10g(spec: dict) -> dict:
    return _train_inner(spec)


@app.function(
    image=image,
    gpu="A100",
    volumes={"/data": data_volume, "/models": models_volume},
    secrets=HF_SECRETS,
    timeout=14400,
    cpu=8,
    memory=65_536,
)
def train_a100(spec: dict) -> dict:
    return _train_inner(spec)


def _train_inner(spec: dict) -> dict:
    """The actual training body — shared by all GPU-flavor functions."""
    import datetime as dt
    import os
    import time
    import traceback

    import torch
    from datasets import Dataset, load_dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer, TrainingArguments,
    )
    from trl import SFTTrainer, SFTConfig

    t_start = time.time()
    run_id = spec["run_id"]
    base_model = spec["base_model"]
    dataset_path = spec["dataset_volume_path"]
    sys_prompt = spec.get("system_prompt", "You are a helpful assistant.")
    instr_field = spec.get("instruction_field", "instruction")
    resp_field = spec.get("response_field", "command")
    max_length = spec.get("max_length", 512)
    lora_cfg_dict = spec["lora"]
    train_cfg = spec["training"]
    hub_repo = spec.get("hub_repo")

    out_dir = Path(f"/models/runs/{run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[train] run_id={run_id}")
    print(f"[train] base={base_model} dataset={dataset_path}")
    print(f"[train] gpu_visible: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE'}")

    # 1. Load dataset
    if dataset_path.endswith(".jsonl"):
        ds = Dataset.from_json(dataset_path)
    elif dataset_path.endswith(".parquet"):
        ds = Dataset.from_parquet(dataset_path)
    else:
        return {"run_id": run_id, "status": "error",
                "error": f"unknown dataset format: {dataset_path}"}

    print(f"[train] loaded {len(ds)} rows from {dataset_path}")

    # 2. Tokenizer + base
    tok = AutoTokenizer.from_pretrained(base_model)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    dtype = torch.bfloat16 if train_cfg.get("bf16", True) else torch.float16

    print(f"[train] loading base in {dtype} ...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        dtype=dtype,
        device_map="auto",
    )

    # 3. Attach LoRA
    lora_cfg = LoraConfig(
        r=lora_cfg_dict["r"],
        lora_alpha=lora_cfg_dict["alpha"],
        lora_dropout=lora_cfg_dict.get("dropout", 0.05),
        target_modules=lora_cfg_dict["target_modules"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"[train] trainable params: {trainable/1e6:.2f}M / {total/1e6:.2f}M "
          f"({100*trainable/total:.2f}%)")

    # 4. Format dataset to chat template + render
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

    # 5. Training
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
        gradient_checkpointing=train_cfg.get("gradient_checkpointing", True),
        seed=train_cfg.get("seed", 42),
        save_strategy="no",
        logging_steps=train_cfg.get("logging_steps", 25),
        max_length=max_length,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_cfg,
        train_dataset=ds_fmt,
        processing_class=tok,
    )

    print(f"[train] starting SFT — {sft_cfg.num_train_epochs} epochs, "
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

    # 6. Save adapter
    adapter_dir = out_dir / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(adapter_dir))
    tok.save_pretrained(str(adapter_dir))

    # 7. Push to HF Hub
    hub_url = None
    if hub_repo:
        from huggingface_hub import HfApi
        api = HfApi()
        try:
            api.create_repo(hub_repo, repo_type="model", exist_ok=True,
                            private=spec.get("hub_private", False))
            api.upload_folder(folder_path=str(adapter_dir),
                              repo_id=hub_repo, repo_type="model")
            hub_url = f"https://huggingface.co/{hub_repo}"
            print(f"[train] pushed -> {hub_url}")
        except Exception as e:
            print(f"[train] hub push failed: {e!r}")

    wall_seconds = round(time.time() - t_start, 1)

    # 8. Manifest (per slm-learning-096: lineage + provenance)
    manifest = {
        "schema_v": 1,
        "run_id": run_id,
        "ts_completed": dt.datetime.now(dt.timezone.utc).isoformat(),
        "compute_target": f"modal-{spec.get('gpu', 'L4').lower()}",
        "wall_seconds": wall_seconds,
        "wall_hours": round(wall_seconds / 3600, 2),
        "base_model": base_model,
        "dataset_volume_path": dataset_path,
        "n_train_rows": len(ds_fmt),
        "lora": lora_cfg_dict,
        "training": train_cfg,
        "training_loss": train_loss,
        "training_metrics": train_metrics,
        "trainable_params_M": round(trainable / 1e6, 2),
        "total_params_M": round(total / 1e6, 2),
        "trainable_fraction": round(100 * trainable / total, 4),
        "hub_url": hub_url,
        "adapter_volume_path": str(adapter_dir),
        "decision_refs": ["slm-learning-094", "slm-learning-096",
                          "slm-learning-097", "slm-learning-105"],
        "status": train_status,
    }
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    models_volume.commit()

    print(f"[train] DONE run_id={run_id} wall={wall_seconds}s "
          f"loss={train_loss:.4f} hub={hub_url}")
    return manifest


@app.function(
    image=image,
    volumes={"/data": data_volume, "/models": models_volume},
    timeout=120,
)
def list_volumes() -> dict:
    """Inspect what's on the slm-data and slm-models volumes."""
    out = {"data": {}, "models": {}}
    for vol_name, base in (("data", "/data"), ("models", "/models")):
        for p in sorted(Path(base).rglob("*")):
            if p.is_file():
                try:
                    size = p.stat().st_size
                except OSError:
                    size = -1
                out[vol_name][str(p.relative_to(base))] = size
    return out


@app.function(
    image=image,
    volumes={"/data": data_volume, "/models": models_volume},
    timeout=600,
    cpu=2,
    memory=4096,
)
def upload_local_jsonl(file_bytes: bytes, target_path: str) -> dict:
    """Receive a local jsonl and write it to the slm-data volume."""
    target = Path("/data") / target_path.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(file_bytes)
    data_volume.commit()
    return {"path": str(target), "bytes": len(file_bytes)}


@app.local_entrypoint()
def upload(local_path: str, volume_path: str) -> None:
    """Upload a local jsonl into the slm-data volume.

    Example:
        modal run modal_app/train_lora.py::upload \\
            data/processed/gad-telemetry-2026-05-06/sft_tooluse.jsonl \\
            processed/gad-telemetry/sft_tooluse.jsonl
    """
    p = Path(local_path)
    if not p.exists():
        print(f"ERROR: local file not found: {local_path}")
        return
    body = p.read_bytes()
    result = upload_local_jsonl.remote(body, volume_path)
    print(f"Uploaded {p} ({result['bytes']:,} bytes) -> /data/{volume_path}")


@app.local_entrypoint()
def main(spec_path: str = "", gpu: str = "L4") -> None:
    """Fire one training run from a JSON spec file."""
    if not spec_path:
        print("usage: modal run modal_app/train_lora.py --spec-path <path> [--gpu L4|A10G|A100]")
        return

    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    spec.setdefault("gpu", gpu)

    print(f"[main] firing {spec['run_id']} on Modal {gpu}...")
    fn = {"L4": train, "A10G": train_a10g, "A100": train_a100}.get(gpu, train)
    result = fn.remote(spec)
    print()
    print(json.dumps(result, indent=2)[:2000])
