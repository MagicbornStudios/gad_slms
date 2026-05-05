"""Streaming HF datasets adapter (placeholder).

Per decision slm-learning-012, code/math/reasoning tracks pull from
HF datasets (FineWeb, The Stack, OpenMathInstruct, OpenCodeReasoning,
FineMath). Streaming so we never download TBs to disk.

This module is a stub: implement when the first non-jsonl track lands.
Keeping the file present so the data/ package exposes a clear seam for
the future adapter.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slm_from_scratch.finetune.config import DataSettings


def build_dataset_hf_streaming(settings: "DataSettings", tokenizer):
    raise NotImplementedError(
        "HF streaming adapter not implemented yet — see decision "
        "slm-learning-012 and note .planning/notes/2026-05-05-report-cadence.md"
    )
