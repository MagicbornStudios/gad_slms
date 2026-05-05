"""Top-level driver: config -> trained adapter + manifest + (optional) eval.

The only file that knows about *all* the other modules. Everything else
is single-concern; this is the composition root.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from slm_from_scratch.finetune.data import build_dataset_jsonl
from slm_from_scratch.finetune.eval_hook import run_evals
from slm_from_scratch.finetune.hub_publish import publish_adapter
from slm_from_scratch.finetune.manifest import write_manifest
from slm_from_scratch.finetune.model import attach_lora, load_base_model
from slm_from_scratch.finetune.model.lora_adapter import count_trainable
from slm_from_scratch.finetune.trainer import train
from slm_from_scratch.finetune.vram_budget import check_budget

if TYPE_CHECKING:
    from slm_from_scratch.finetune.config import FinetuneConfig


DATA_BUILDERS = {
    "jsonl_pairs": build_dataset_jsonl,
}


def _build_dataset(cfg: "FinetuneConfig", tokenizer):
    builder = DATA_BUILDERS.get(cfg.data.source)
    if builder is None:
        raise ValueError(
            f"unknown data source '{cfg.data.source}'. "
            f"known: {list(DATA_BUILDERS.keys())}"
        )
    return builder(cfg.data, tokenizer)


def _hidden_and_layer_count(model) -> tuple[int, int]:
    base = getattr(model, "config", None)
    if base is None:
        return 768, 12
    return (
        getattr(base, "hidden_size", 768),
        getattr(base, "num_hidden_layers", 12),
    )


def run_finetune(cfg: "FinetuneConfig", *, dry_run: bool = False) -> Path:
    """Run one fine-tune end to end. Returns the run output directory."""
    print(f"[run] {cfg.name} adapter={cfg.adapter} base={cfg.base_model}")
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    print("[load] base model + tokenizer ...")
    tokenizer, model = load_base_model(cfg)
    n_total = sum(p.numel() for p in model.parameters())
    hidden, n_layer = _hidden_and_layer_count(model)
    print(f"       params={n_total / 1e6:.1f}M hidden={hidden} layers={n_layer}")

    print("[lora] attaching adapter ...")
    model = attach_lora(model, cfg)
    n_trainable, _ = count_trainable(model)
    print(f"       trainable={n_trainable / 1e6:.2f}M ({100 * n_trainable / n_total:.2f}% of base)")

    print("[budget] checking VRAM ...")
    vram = check_budget(
        n_total,
        adapter=cfg.adapter,
        n_trainable_params=n_trainable,
        batch_size=cfg.training.batch_size,
        seq_len=cfg.data.max_length,
        hidden_size=hidden,
        n_layer=n_layer,
        grad_checkpointing=cfg.training.gradient_checkpointing,
        weights_already_loaded=True,  # model is already on GPU above
    )
    print(f"       device={vram.device} fits={vram.fits} | {vram.reason}")
    if not vram.fits and not dry_run:
        raise RuntimeError(
            f"planned run does not fit budget: {vram.reason}. "
            "Lower batch_size, switch to qlora, or move to remote."
        )

    print("[data] building dataset ...")
    dataset = _build_dataset(cfg, tokenizer)
    print(f"       {len(dataset)} examples (text column)")

    if dry_run:
        print("[dry-run] skipping train + eval, writing manifest only.")
        write_manifest(
            cfg,
            adapter_dir=cfg.output_dir / "adapter",
            vram=vram,
            n_trainable=n_trainable,
            n_total=n_total,
            train_seconds=0.0,
            extra={"dry_run": True, "dataset_size": len(dataset)},
        )
        return cfg.output_dir

    print("[train] starting SFT ...")
    t0 = time.time()
    adapter_dir = train(model, tokenizer, dataset, cfg)
    train_seconds = time.time() - t0
    print(f"       saved adapter to {adapter_dir} ({train_seconds:.1f}s)")

    eval_results: dict = {}
    if cfg.eval.run_after_train:
        print(f"[eval] running {cfg.eval.benchmarks} ...")
        eval_results = run_evals(adapter_dir, cfg)

    hub_url: str | None = None
    if cfg.hub.publish:
        print("[hub] publishing adapter ...")
        hub_url = publish_adapter(
            cfg, adapter_dir, private=cfg.hub.private,
        )

    extra_manifest: dict = {}
    if hub_url is not None:
        extra_manifest["hub_url"] = hub_url

    write_manifest(
        cfg,
        adapter_dir=adapter_dir,
        vram=vram,
        n_trainable=n_trainable,
        n_total=n_total,
        train_seconds=train_seconds,
        eval_results=eval_results,
        extra=extra_manifest or None,
    )
    print(f"[done] {cfg.output_dir}")
    return cfg.output_dir
