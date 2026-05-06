"""Windows-host OpenAI-compatible adapter server.

Fallback for scripts/serve/vllm_adapter.sh when vLLM is unavailable
(Windows host, no WSL, no remote GPU). Uses FastAPI + transformers + PEFT
to expose POST /v1/chat/completions for any scrubster/dr-stein-* adapter.

Usage:
    .venv-gpu/Scripts/python.exe scripts/serve/serve_adapter.py \
        --adapter scrubster/dr-stein-colab-cli \
        --base Qwen/Qwen2.5-1.5B-Instruct \
        --port 8000

Decision context: slm-learning-025 (bf16 default), slm-learning-040 (vLLM gate).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from typing import List, Optional

# Heavy imports inside main() so --help is fast.


def build_app(model, tokenizer, served_name):
    from fastapi import FastAPI
    from pydantic import BaseModel

    class ChatMessage(BaseModel):
        role: str
        content: str

    class ChatCompletionRequest(BaseModel):
        model: str
        messages: List[ChatMessage]
        max_tokens: Optional[int] = 256
        temperature: Optional[float] = 0.0
        top_p: Optional[float] = 1.0
        stream: Optional[bool] = False

    app = FastAPI(title="dr-stein-adapter-server")

    @app.get("/v1/models")
    def list_models():
        return {
            "object": "list",
            "data": [{"id": served_name, "object": "model", "owned_by": "scrubster"}],
        }

    @app.post("/v1/chat/completions")
    def chat(req: ChatCompletionRequest):
        prompt = tokenizer.apply_chat_template(
            [{"role": m.role, "content": m.content} for m in req.messages],
            tokenize=False,
            add_generation_prompt=True,
        )
        import torch

        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        t0 = time.time()
        do_sample = (req.temperature or 0.0) > 0.0
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=req.max_tokens or 256,
                do_sample=do_sample,
                temperature=req.temperature if do_sample else 1.0,
                top_p=req.top_p,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.eos_token_id,
            )
        gen_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        text = tokenizer.decode(gen_tokens, skip_special_tokens=True)
        latency_ms = int((time.time() - t0) * 1000)
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:16]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": served_name,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text.strip()},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": int(inputs["input_ids"].shape[1]),
                "completion_tokens": int(gen_tokens.shape[0]),
                "total_tokens": int(outputs.shape[1]),
            },
            "x_latency_ms": latency_ms,
        }

    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", required=True, help="HF Hub adapter repo, e.g. scrubster/dr-stein-colab-cli")
    parser.add_argument("--base", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--served-name", default="adapter")
    parser.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"])
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
    dtype = dtype_map[args.dtype]

    print(f"[serve] loading base {args.base} dtype={args.dtype}", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    base = AutoModelForCausalLM.from_pretrained(
        args.base,
        torch_dtype=dtype,
        device_map="auto" if torch.cuda.is_available() else None,
    )
    print(f"[serve] attaching adapter {args.adapter}", file=sys.stderr)
    model = PeftModel.from_pretrained(base, args.adapter)
    model.eval()

    import uvicorn

    app = build_app(model, tokenizer, args.served_name)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
