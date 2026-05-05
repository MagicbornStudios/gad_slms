"""Push a trained adapter directory to the Hugging Face Hub.

Single concern: given a local adapter dir + a FinetuneConfig, create
(or update) a public HF Hub repo and upload everything in the dir.
Returns the repo URL or None if publishing was skipped (no token / opt-out).

Naming (decision slm-learning-023):
    <hf-username>/dr-stein-<config-name-hyphenated>

Username is discovered at runtime via HfApi().whoami() so the same code
works for any user who's run `hf auth login`. If no token is set, the
publish step logs a warning and returns None — training still succeeded.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from slm_from_scratch.finetune.config import FinetuneConfig


REPO_PREFIX = "dr-stein"


def _slugify(name: str) -> str:
    return name.replace("_", "-").lower()


def _build_readme(cfg: "FinetuneConfig", repo_id: str) -> str:
    return f"""---
library_name: peft
base_model: {cfg.base_model}
tags:
  - lora
  - peft
  - dr-stein
  - slm-learning
  - gad-cli
---

# {repo_id}

PEFT/LoRA adapter for `{cfg.base_model}`, fine-tuned on the
slm-learning GAD-tool translation track.

- Trained on: 153 hand-curated `(instruction, gad CLI command)` pairs
- Adapter kind: {cfg.adapter} (r={cfg.lora.r}, alpha={cfg.lora.alpha})
- Target modules: {", ".join(cfg.lora.target_modules)}
- Run name: `{cfg.name}`
- Compute: `{cfg.compute_target}`

## Loading

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("{cfg.base_model}")
tok = AutoTokenizer.from_pretrained("{cfg.base_model}")
model = PeftModel.from_pretrained(base, "{repo_id}")
```

## Notes

{cfg.notes}
"""


def publish_adapter(
    cfg: "FinetuneConfig",
    adapter_dir: Path,
    *,
    private: bool = False,
    skip_if_no_token: bool = True,
) -> Optional[str]:
    """Upload `adapter_dir` to HF Hub. Return repo URL or None on skip.

    Args:
        cfg: the finetune config (used for naming + README metadata).
        adapter_dir: local path holding adapter_config.json + weights.
        private: if True, create a private repo. Default public per
            decision slm-learning-023 (cost-driven).
        skip_if_no_token: if no HF token is configured, return None
            instead of raising. Default True so training never fails
            on a missing publish step.
    """
    try:
        from huggingface_hub import HfApi, get_token
    except ImportError:
        print("[hub] huggingface_hub not installed — skipping publish")
        return None

    # huggingface_hub 1.x removed HfFolder; the canonical token getter is
    # `get_token()` which honors ~/.cache/huggingface/token + HF_TOKEN env.
    token = get_token() or os.environ.get("HF_TOKEN")
    if not token:
        msg = (
            "[hub] no HF token found (run `hf auth login` or set HF_TOKEN). "
            "Skipping publish — training output remains on disk."
        )
        if skip_if_no_token:
            print(msg)
            return None
        raise RuntimeError(msg)

    api = HfApi(token=token)
    try:
        username = api.whoami(token=token)["name"]
    except Exception as exc:
        print(f"[hub] whoami failed ({exc}); skipping publish")
        return None

    repo_id = f"{username}/{REPO_PREFIX}-{_slugify(cfg.name)}"
    print(f"[hub] creating + pushing to {repo_id} (private={private}) ...")

    api.create_repo(
        repo_id=repo_id,
        repo_type="model",
        private=private,
        exist_ok=True,
    )

    readme_path = adapter_dir / "README.md"
    readme_path.write_text(
        _build_readme(cfg, repo_id), encoding="utf-8"
    )

    # `huggingface_hub.HfApi.upload_folder` was observed to stall silently
    # mid-upload at ~28% on a 73 MB safetensors file (no exception, no
    # progress, no error). Shelling out to the `hf upload` CLI is the
    # canonical 1.x path and includes resume + retry. Find the CLI in
    # this venv (entry-point shim alongside python) so we don't depend
    # on PATH being set up.
    import shutil
    import subprocess
    import sys

    hf_cli = shutil.which("hf") or str(
        Path(sys.executable).parent / ("hf.exe" if os.name == "nt" else "hf")
    )
    cmd = [
        hf_cli, "upload",
        repo_id, str(adapter_dir), ".",
        "--repo-type", "model",
        "--commit-message", f"Stage 2.5 adapter: {cfg.name}",
    ]
    proc = subprocess.run(cmd, env={**os.environ, "HF_TOKEN": token})
    if proc.returncode != 0:
        print(f"[hub] hf upload returned rc={proc.returncode}; check log")
        return None

    url = f"https://huggingface.co/{repo_id}"
    print(f"[hub] pushed: {url}")
    return url
