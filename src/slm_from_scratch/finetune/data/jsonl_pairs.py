"""Load (instruction, response) JSONL → HF Dataset of ChatML strings.

Single concern: read JSONL, apply tokenizer chat template, return a
Dataset with a `text` column ready for SFTTrainer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slm_from_scratch.finetune.config import DataSettings

from datasets import Dataset

from slm_from_scratch.finetune.data.chatml import format_pair_as_chatml


def _read_jsonl(path: Path) -> list[dict]:
    pairs: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            pairs.append(json.loads(line))
    return pairs


def build_dataset_jsonl(settings: "DataSettings", tokenizer) -> Dataset:
    """Read settings.path, format each row as ChatML, return a Dataset."""
    path = Path(settings.path)
    if not path.exists():
        raise FileNotFoundError(f"data file not found: {path}")
    raw = _read_jsonl(path)
    if not raw:
        raise ValueError(f"data file is empty: {path}")

    instr_field = settings.instruction_field
    resp_field = settings.response_field
    system_prompt = settings.system_prompt

    def render(example: dict) -> str:
        msgs = format_pair_as_chatml(
            example[instr_field],
            example[resp_field],
            system_prompt=system_prompt,
        )
        return tokenizer.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=False,
        )

    rendered = [{"text": render(r)} for r in raw if instr_field in r and resp_field in r]
    if not rendered:
        raise ValueError(
            f"no usable rows in {path}: expected fields "
            f"'{instr_field}' and '{resp_field}'"
        )
    return Dataset.from_list(rendered)
