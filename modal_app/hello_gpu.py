"""Modal hello-GPU smoke — validates credits + GPU dispatch + storage.

Cheapest possible Modal job: 30 sec on a T4. Confirms the pipeline
works end-to-end before spending real money on serving or training.

Usage:

    modal run modal_app/hello_gpu.py

Or with explicit profile:

    modal run --profile b2gdevs modal_app/hello_gpu.py

Expected output: GPU info, matmul timing, "smoke ok" message.

Per slm-learning-098 + composition-strategy.md: this is the gate before
any serving / training Modal work.
"""
from __future__ import annotations

import modal


app = modal.App("slm-learning-hello-gpu")

# Lightweight image — just torch, no transformers.
image = modal.Image.debian_slim().pip_install(
    "torch==2.9.1",
)


@app.function(
    image=image,
    gpu="T4",
    timeout=120,
)
def smoke() -> dict:
    import json
    import time

    import torch

    info = {
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
    }
    if torch.cuda.is_available():
        info["device_name"] = torch.cuda.get_device_name(0)
        info["device_capability"] = torch.cuda.get_device_capability(0)
        info["total_memory_gb"] = round(
            torch.cuda.get_device_properties(0).total_memory / 1024**3, 2
        )

    # Tiny matmul to prove the GPU actually computes
    t0 = time.time()
    a = torch.randn(2048, 2048, device="cuda")
    b = torch.randn(2048, 2048, device="cuda")
    c = a @ b
    torch.cuda.synchronize()
    info["matmul_2048x2048_seconds"] = round(time.time() - t0, 4)
    info["matmul_result_norm"] = round(float(c.norm()), 2)
    info["status"] = "smoke ok"

    print(json.dumps(info, indent=2))
    return info


@app.local_entrypoint()
def main() -> None:
    result = smoke.remote()
    print()
    print("=== Modal smoke result ===")
    import json as _json
    print(_json.dumps(result, indent=2))
