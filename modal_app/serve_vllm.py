"""Modal vLLM serving — exposes a trained adapter as an OpenAI-compatible endpoint.

This is the critical infrastructure piece per slm-learning-104 launch
timeline: until our model is reachable at an OpenAI-compatible URL,
opencode/codex/claude-cli/the comparator-matrix cannot route to it.

The deployment loads:
- A base model (e.g. Qwen2.5-1.5B-Instruct)
- An adapter from HF Hub OR slm-models volume
And exposes /v1/chat/completions on a public URL.

Architecture: Modal class (long-lived container) with vLLM AsyncEngine.

Usage

  # Deploy (publishes a stable URL)
  modal deploy modal_app/serve_vllm.py

  # The deployed URL has the shape
  #   https://b2gdevs--slm-learning-vllm-vllm-engine-serve.modal.run
  # which is OpenAI-compatible. Then:
  #
  # 1) opencode --model openrouter/<...>      -> hits frontier
  # 2) opencode --model https://<our-url>/v1  -> hits our model
  # 3) curl https://<our-url>/v1/chat/completions ... -> direct
  # 4) scripts/eval/run_comparative_matrix.py with kind=local
  #    pointed at the URL -> our row in the matrix

Adapter selection

The serve function reads MODAL_ADAPTER_ID + MODAL_BASE_MODEL from
function args (passed via deploy-time env or CLI args). For initial
deployment we pin to v2 (scrubster/dr-stein-stage25-qwen15-instruct-v2).

Cost note

vLLM container scale-to-zero is enabled — cold start is ~30-60s but
idle cost goes to $0. While serving on L4, ~$0.80/hr. Realistic
monthly cost at light usage: ~$5-20.

Decision refs: slm-learning-094, 104, 105.
"""
# NOTE: do NOT add `from __future__ import annotations` here — Modal's
# class parameter type validator needs real type objects, not strings.
import modal


app = modal.App("slm-learning-vllm")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm>=0.7",
        "torch==2.9.1",
        "huggingface_hub>=0.30",
    )
)

models_volume = modal.Volume.from_name("slm-models", create_if_missing=True)


# Default deployment: v2 CLI translator. Operator overrides via the
# `serve` function args.
DEFAULT_BASE = "Qwen/Qwen2.5-1.5B-Instruct"
DEFAULT_ADAPTER = "scrubster/dr-stein-stage25-qwen15-instruct-v2"
DEFAULT_SERVED_NAME = "dr-stein-cli-v2"


@app.cls(
    image=image,
    gpu="L4",
    volumes={"/models": models_volume},
    timeout=10 * 60,  # 10 min before cold-restart on idle
    min_containers=0,  # scale-to-zero
    max_containers=2,
    scaledown_window=300,  # idle 5 min then shutdown
)
@modal.concurrent(max_inputs=8)
class VLLMEngine:
    base_model: str = modal.parameter(default=DEFAULT_BASE)
    adapter_id: str = modal.parameter(default=DEFAULT_ADAPTER)
    served_name: str = modal.parameter(default=DEFAULT_SERVED_NAME)
    enable_lora: bool = modal.parameter(default=True)
    max_model_len: int = modal.parameter(default=4096)

    @modal.enter()
    def load(self) -> None:
        import os
        import time

        from vllm import AsyncEngineArgs, AsyncLLMEngine

        t0 = time.time()
        # Resolve adapter: either HF Hub id or a path on the volume
        adapter_path = None
        if self.enable_lora and self.adapter_id:
            if self.adapter_id.startswith("/models/"):
                adapter_path = self.adapter_id
            elif "/" in self.adapter_id and not self.adapter_id.startswith("/"):
                # HF Hub style: org/repo
                adapter_path = self.adapter_id
            else:
                adapter_path = self.adapter_id
            print(f"[vllm] adapter: {adapter_path}")

        engine_args = AsyncEngineArgs(
            model=self.base_model,
            served_model_name=self.served_name,
            dtype="bfloat16",
            gpu_memory_utilization=0.85,
            max_model_len=self.max_model_len,
            enable_lora=self.enable_lora,
            max_lora_rank=64,
            disable_log_stats=False,
        )
        self.engine = AsyncLLMEngine.from_engine_args(engine_args)
        self._adapter_path = adapter_path

        # Pre-load the LoRA so the first request doesn't pay the cost
        if self.enable_lora and adapter_path:
            from vllm.lora.request import LoRARequest
            self._lora_req = LoRARequest(
                lora_name=self.served_name,
                lora_int_id=1,
                lora_path=adapter_path,
            )
            print(f"[vllm] LoRA pre-registered as int_id=1 ({self.served_name})")
        else:
            self._lora_req = None

        print(f"[vllm] ready in {time.time()-t0:.1f}s "
              f"(base={self.base_model}, adapter={adapter_path})")

    @modal.fastapi_endpoint(method="GET")
    def health(self) -> dict:
        return {
            "status": "ok",
            "base_model": self.base_model,
            "served_name": self.served_name,
            "adapter": self.adapter_id,
            "max_model_len": self.max_model_len,
        }

    @modal.fastapi_endpoint(method="POST", docs=False)
    async def chat_completions(self, request: dict) -> dict:
        """OpenAI /v1/chat/completions compatible endpoint."""
        import time
        import uuid

        from vllm import SamplingParams

        messages = request.get("messages", [])
        max_tokens = int(request.get("max_tokens", 256))
        temperature = float(request.get("temperature", 0.0))
        stop = request.get("stop")

        # Render messages to chat-template prompt via the engine's tokenizer
        tokenizer = await self.engine.get_tokenizer()
        try:
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )
        except Exception:
            # Fallback: simple concat
            prompt = "\n\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}"
                for m in messages
            )

        sampling = SamplingParams(
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=1.0 if temperature == 0.0 else 0.95,
            stop=stop,
        )

        request_id = str(uuid.uuid4())
        kwargs = {}
        if self._lora_req:
            kwargs["lora_request"] = self._lora_req

        t0 = time.time()
        gen = self.engine.generate(prompt, sampling, request_id, **kwargs)
        final = None
        async for output in gen:
            final = output
        wall = time.time() - t0

        text = final.outputs[0].text if final and final.outputs else ""
        prompt_tokens = len(final.prompt_token_ids) if final else 0
        completion_tokens = (
            len(final.outputs[0].token_ids) if final and final.outputs else 0
        )

        return {
            "id": f"chatcmpl-{request_id[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.served_name,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "_modal_wall_seconds": round(wall, 3),
        }


@app.local_entrypoint()
def smoke() -> None:
    """Spin up the engine + send a tiny test chat completion."""
    import json as _json
    import urllib.request

    # Get the engine instance with default params (v2 CLI adapter)
    engine = VLLMEngine()
    # Trigger a warm load by hitting health
    health_url = engine.health.web_url
    chat_url = engine.chat_completions.web_url
    print(f"[smoke] health: {health_url}")
    print(f"[smoke] chat:   {chat_url}")

    payload = {
        "messages": [
            {"role": "system", "content": "You are an assistant. Translate the user's request into a single gad CLI command. Output only the command on one line."},
            {"role": "user", "content": "Take a note that the build is broken on Windows."},
        ],
        "max_tokens": 64,
        "temperature": 0.0,
    }
    body = _json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        chat_url, data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    print(f"[smoke] sending POST...")
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = _json.loads(resp.read().decode("utf-8"))
    print(_json.dumps(result, indent=2))
