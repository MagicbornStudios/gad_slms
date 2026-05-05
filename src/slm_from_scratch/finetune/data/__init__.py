"""Data adapters for fine-tune runs.

Each adapter exposes `build_dataset(config, tokenizer) -> Dataset` so
the trainer can swap sources via config without code changes.
"""
from slm_from_scratch.finetune.data.jsonl_pairs import build_dataset_jsonl
from slm_from_scratch.finetune.data.chatml import format_pair_as_chatml

__all__ = ["build_dataset_jsonl", "format_pair_as_chatml"]
