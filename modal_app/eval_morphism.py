"""Modal eval app for morphism-expanded models.

A morphism Variant A model (per train_morphism.py) cannot be loaded by
standard AutoModelForCausalLM.from_pretrained() because it has a custom
IdentityProjectionLayer inserted into model.layers. Loading the saved
config.json with num_hidden_layers=N+1 instantiates N+1 standard
Qwen2DecoderLayers, none of which match the inserted layer.

This script re-builds the architecture from scratch:
  1. Load the base model (with original num_hidden_layers).
  2. Insert a fresh IdentityProjectionLayer at the same position.
  3. Load the trained layer weights from identity_projection_layer.pt.
  4. Run HumanEval / MBPP / code_smoke through the resulting model.
  5. Persist results to /models/eval-runs/<persist_run_id>/...

Usage:
    modal run modal_app/eval_morphism.py::main \\
        --run-id morphism-0p5b-variant-a-2026-05-08 \\
        --base-model 'Qwen/Qwen2.5-Coder-0.5B-Instruct' \\
        --insert-after-layer 11 \\
        --benchmark humaneval --limit 164 --gpu A10G \\
        --persist-run-id morphism-0p5b-variant-a-eval-2026-05-08

Decision refs: slm-learning-103, slm-learning-165, slm-learning-169.
"""
from __future__ import annotations

import json
from pathlib import Path

import modal


app = modal.App("slm-learning-eval-morphism")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.9.1",
        "transformers>=4.50",
        "datasets>=3.0",
        "accelerate>=1.0",
        "huggingface_hub>=0.30",
        "pyarrow",
        "pyyaml",
    )
    .add_local_python_source("modal_app")
)

data_volume = modal.Volume.from_name("slm-data", create_if_missing=True)
models_volume = modal.Volume.from_name("slm-models", create_if_missing=True)


@app.function(
    image=image,
    gpu="A10G",
    volumes={"/data": data_volume, "/models": models_volume},
    timeout=5400,
    cpu=4,
    memory=24576,
)
def score_morphism_a10g(args: dict) -> dict:
    return _score_morphism_inner(args)


@app.function(
    image=image,
    gpu="A100",
    volumes={"/data": data_volume, "/models": models_volume},
    timeout=7200,
    cpu=4,
    memory=49152,
)
def score_morphism_a100(args: dict) -> dict:
    return _score_morphism_inner(args)


def _score_morphism_inner(args: dict) -> dict:
    import datetime as dt
    import time

    import torch
    import torch.nn as nn
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from transformers.models.qwen2.modeling_qwen2 import Qwen2RMSNorm

    # Imports of helpers from the eval_adapter module shipped to Modal
    # via `image.add_local_python_source` — done at the bottom of this file.
    from modal_app.eval_adapter import (  # noqa: E402
        CODE_SMOKE_TASKS,
        HUMANEVAL_TEMPLATE,
        _judge,
        _load_humaneval,
        _load_mbpp,
        _load_gad_tools,
    )

    run_id = args["run_id"]
    base_model = args["base_model"]
    insert_after_layer = args.get("insert_after_layer", 11)
    benchmark = args["benchmark"]
    limit = args.get("limit", 20)
    max_new_tokens = args.get("max_new_tokens", 384)
    mode = args.get("mode", "chat")
    persist_run_id = args.get("persist_run_id")

    print(f"[eval-morphism] run_id={run_id} base={base_model} "
          f"benchmark={benchmark} mode={mode} insert_after={insert_after_layer}")

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(base_model)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    dtype = torch.bfloat16
    model = AutoModelForCausalLM.from_pretrained(
        base_model, dtype=dtype, device_map="auto",
    )

    # Re-build the morphism architecture
    inner = model.model
    cfg = inner.config
    hidden_size = cfg.hidden_size

    class IdentityProjectionLayer(nn.Module):
        def __init__(self, hidden_size: int, eps: float = 1e-6):
            super().__init__()
            self.hidden_size = hidden_size
            self.norm = Qwen2RMSNorm(hidden_size, eps=eps)
            self.proj = nn.Linear(hidden_size, hidden_size, bias=True)
            nn.init.zeros_(self.proj.weight)
            nn.init.zeros_(self.proj.bias)

        def forward(
            self, hidden_states, attention_mask=None, position_ids=None,
            past_key_values=None, use_cache=False, cache_position=None,
            position_embeddings=None, **kwargs,
        ):
            return hidden_states + self.proj(self.norm(hidden_states))

    target_device = next(inner.parameters()).device
    new_layer = IdentityProjectionLayer(hidden_size, cfg.rms_norm_eps).to(
        device=target_device, dtype=dtype
    )

    insert_pos = insert_after_layer + 1
    layers = list(inner.layers)
    layers.insert(insert_pos, new_layer)
    inner.layers = nn.ModuleList(layers)
    cfg.num_hidden_layers = cfg.num_hidden_layers + 1
    if hasattr(cfg, "layer_types") and cfg.layer_types is not None:
        new_layer_types = list(cfg.layer_types)
        new_layer_types.insert(insert_pos, "full_attention")
        cfg.layer_types = new_layer_types

    # Load trained layer weights
    layer_state_path = Path(f"/models/runs/{run_id}/identity_projection_layer.pt")
    if not layer_state_path.is_file():
        return {"status": "error",
                "error": f"layer state not found: {layer_state_path}"}
    state = torch.load(str(layer_state_path), map_location=target_device,
                       weights_only=False)
    new_layer.load_state_dict(state)
    print(f"[eval-morphism] loaded trained layer state from {layer_state_path}")

    model.eval()
    print(f"[eval-morphism] model ready in {time.time()-t0:.1f}s")

    if benchmark == "code_smoke":
        cases = CODE_SMOKE_TASKS[:limit]
    elif benchmark == "humaneval":
        cases = _load_humaneval(limit, mode=mode)
    elif benchmark == "mbpp":
        cases = _load_mbpp(limit)
    elif benchmark == "gad_tools":
        cases = _load_gad_tools(limit)
    else:
        return {"status": "error", "error": f"unknown benchmark {benchmark!r}"}

    results = []
    passed = 0
    for i, case in enumerate(cases):
        case_t0 = time.time()
        prompt_text = case["prompt"]
        if mode == "completion":
            text_in = prompt_text
        else:
            msgs = [{"role": "user", "content": prompt_text}]
            try:
                text_in = tok.apply_chat_template(
                    msgs, tokenize=False, add_generation_prompt=True
                )
            except Exception:
                text_in = prompt_text + "\n"

        inputs = tok(text_in, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tok.pad_token_id,
            )
        new = out[0][inputs["input_ids"].shape[1]:]
        completion = tok.decode(new, skip_special_tokens=True)
        elapsed = time.time() - case_t0

        ok, why = _judge(case, completion)
        if ok:
            passed += 1
        results.append({
            "id": case.get("id", f"case-{i}"),
            "passed": ok,
            "judge_reason": why,
            "elapsed_s": round(elapsed, 2),
            "completion_full": completion,
            "completion_preview": completion[:300],
        })

    score = round(passed / max(1, len(cases)), 4)
    summary = {
        "schema_v": 2,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "adapter_id": f"MORPHISM:{run_id}",
        "base_model": base_model,
        "morphism_run_id": run_id,
        "insert_after_layer": insert_after_layer,
        "benchmark": benchmark,
        "mode": mode,
        "n": len(cases),
        "passed": passed,
        "score": score,
        "results": results,
        "decision_refs": ["slm-learning-103", "slm-learning-165",
                          "slm-learning-169"],
    }

    if persist_run_id:
        out_dir = Path(f"/models/eval-runs/{persist_run_id}")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{benchmark}_{mode}_morphism_{run_id}_n{len(cases)}.json"
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        models_volume.commit()
        print(f"[eval-morphism] persisted full results to {out_path}")
        summary["persisted_path"] = str(out_path)

    print(f"[eval-morphism] DONE {benchmark} ({mode}): "
          f"{passed}/{len(cases)} = {score:.3f}")
    return summary


@app.local_entrypoint()
def main(run_id: str, base_model: str, insert_after_layer: int = 11,
         benchmark: str = "humaneval", limit: int = 20, gpu: str = "A10G",
         max_new_tokens: int = 384, mode: str = "chat",
         persist_run_id: str = "") -> None:
    args = {
        "run_id": run_id,
        "base_model": base_model,
        "insert_after_layer": insert_after_layer,
        "benchmark": benchmark,
        "limit": limit,
        "max_new_tokens": max_new_tokens,
        "mode": mode,
        "persist_run_id": persist_run_id or None,
    }
    fn = {"A10G": score_morphism_a10g, "A100": score_morphism_a100}.get(
        gpu, score_morphism_a10g)
    print(f"[main] firing morphism eval on {gpu} for {run_id} "
          f"on {benchmark} (n={limit}, mode={mode})")
    result = fn.remote(args)
    print()
    print(json.dumps(result, indent=2)[:3000])
