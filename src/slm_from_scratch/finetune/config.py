"""Declarative config for a single Stage 2.5+ fine-tune run.

One file = one concern: parsing + validating the config that drives a run.
Everything else (model loading, data, training, eval) reads this object.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal, Optional

import yaml

AdapterKind = Literal["lora", "qlora", "full"]
DataSource = Literal["jsonl_pairs", "hf_streaming"]
ComputeTarget = Literal[
    "local-cuda-0",  # primary local GPU (default)
    "local-cuda-1",  # secondary local GPU (eGPU once detected)
    "colab-t4",      # remote: Colab free-tier T4
    "colab-a100",    # remote: Colab Pro A100
    "kaggle-t4x2",   # remote: Kaggle dual-T4
    "hf-spaces",     # remote: HF Spaces compute
]


@dataclass
class LoRASettings:
    r: int = 16
    alpha: int = 32
    dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ])


@dataclass
class DataSettings:
    source: DataSource = "jsonl_pairs"
    path: str = "data/gad_tool_pairs.jsonl"
    max_length: int = 512
    instruction_field: str = "instruction"
    response_field: str = "command"
    system_prompt: str = (
        "You are Dr. Stein. Translate the user's request into a single gad "
        "CLI command. Output only the command on one line."
    )


@dataclass
class TrainingSettings:
    epochs: int = 3
    learning_rate: float = 2e-4
    batch_size: int = 4
    gradient_accumulation: int = 4
    warmup_ratio: float = 0.05
    weight_decay: float = 0.0
    bf16: bool = True
    gradient_checkpointing: bool = True
    seed: int = 42
    save_strategy: Literal["epoch", "no"] = "epoch"
    logging_steps: int = 5


@dataclass
class EvalSettings:
    """Auto-eval after training. Each entry is a benchmark name; runner
    looks up the matching eval script."""
    run_after_train: bool = True
    benchmarks: list[str] = field(default_factory=lambda: ["gad_tools"])
    temperature: float = 0.0
    max_new_tokens: int = 50


@dataclass
class HubSettings:
    """Auto-publish trained adapter to HF Hub after training.

    Decision slm-learning-023: public repos by default for cost; one
    repo per adapter named <user>/dr-stein-<config-slug>. Set
    publish=False on a per-config basis to disable.
    """
    publish: bool = True
    private: bool = False


@dataclass
class FinetuneConfig:
    """Full spec for one fine-tune run. Serializable to/from YAML."""
    name: str
    base_model: str = "HuggingFaceTB/SmolLM2-135M-Instruct"
    adapter: AdapterKind = "lora"
    compute_target: ComputeTarget = "local-cuda-0"
    output_root: str = "experiments/runs"
    notes: str = ""

    lora: LoRASettings = field(default_factory=LoRASettings)
    data: DataSettings = field(default_factory=DataSettings)
    training: TrainingSettings = field(default_factory=TrainingSettings)
    eval: EvalSettings = field(default_factory=EvalSettings)
    hub: HubSettings = field(default_factory=HubSettings)

    @property
    def output_dir(self) -> Path:
        return Path(self.output_root) / self.name

    def to_dict(self) -> dict:
        return asdict(self)


def _build_dataclass(cls, payload: dict):
    """Recursively turn nested dicts into dataclass instances.

    Uses typing.get_type_hints so PEP 563 string annotations resolve to
    real classes (otherwise nested dataclasses silently arrive as dicts).
    """
    import typing
    if not isinstance(payload, dict):
        return payload
    field_types = typing.get_type_hints(cls)
    kwargs = {}
    for k, v in payload.items():
        if k not in field_types:
            continue
        ftype = field_types[k]
        if hasattr(ftype, "__dataclass_fields__"):
            kwargs[k] = _build_dataclass(ftype, v)
        else:
            kwargs[k] = v
    return cls(**kwargs)


def load_config(path: str | Path) -> FinetuneConfig:
    """Read a YAML config and return a validated FinetuneConfig."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "name" not in raw:
        raise ValueError("config must be a dict with at least a 'name' field")
    return _build_dataclass(FinetuneConfig, raw)
