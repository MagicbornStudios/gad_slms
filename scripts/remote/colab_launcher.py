"""Render a FinetuneConfig to a Colab notebook + push for execution.

Stub. The shape is:
  1. Render a notebook from `templates/colab_finetune.ipynb` with
     the config inlined.
  2. Push the notebook + the JSONL data file to a HF Hub dataset repo
     (so Colab can `git clone` it without auth).
  3. Print the Colab URL the user opens once.
  4. After the user runs it and the notebook pushes the adapter to a
     HF model repo, run `pull_remote_run.py --name <run>` to download
     the adapter + manifest into `experiments/runs/<name>/`.

Implementing the full flow lands when the local pipeline has produced
at least one >50% GAD-tools result; otherwise we're just paying remote
ceremony for something we should fix locally first.
"""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "colab_launcher.py is a stub. See decision slm-learning-020 and "
        ".planning/notes/2026-05-05-multi-gpu-training-track.md for the "
        "intended flow.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
