"""Modal vLLM serving for Kael adapter — PENDING TRAINING.

Currently a placeholder. The Kael LoRA adapter `lora-kael-1p5b-v1` does
not exist yet — see soul_routes.toml `kael-of-tarro-v1-intended` and task
SL-T-04-kael-house-dataset for the dataset capture pipeline that must
ship before this serve can deploy.

Once the adapter exists at scrubster/kael-stage-N-qwenXp5-coder-vN or
similar, replace DEFAULT_ADAPTER below + deploy via:

  modal deploy modal_app/kael_serve.py

Reference template: modal_app/serve_vllm.py (Dr. Stein serve).
Decision refs: GLOBAL-D-336 (own-base direction), slm-learning Kael-house
canonical consolidation timeline.
"""
# NOTE: do NOT add `from __future__ import annotations` here — Modal's
# class parameter type validator needs real type objects, not strings.
import modal


app = modal.App("slm-learning-kael-vllm")

DEFAULT_BASE = "Qwen/Qwen2.5-Coder-7B-Instruct"  # per soul_routes.toml intended route
DEFAULT_ADAPTER = ""                              # PENDING — see Kael-house dataset capture (SL-T-04)
DEFAULT_SERVED_NAME = "kael-of-tarro-v1"


def kael_pending() -> None:
    """Hard error for any caller that imports + runs this module pre-training."""
    raise NotImplementedError(
        "kael_serve.py is a placeholder. The Kael LoRA adapter "
        "(lora-kael-1p5b-v1) has not been trained yet. See "
        "soul_routes.toml `kael-of-tarro-v1-intended` and task "
        "SL-T-04-kael-house-dataset. Replace DEFAULT_ADAPTER and "
        "scaffold the VLLMEngine class (mirror modal_app/serve_vllm.py) "
        "before deploying."
    )


@app.local_entrypoint()
def smoke() -> None:
    """Refuse to run until the adapter exists."""
    kael_pending()
