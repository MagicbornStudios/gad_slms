"""Multi-adapter LoRA loader — the architectural primitive of composition.

Loads ONE base model and N LoRA adapters into a single PeftModel, and
exposes per-request adapter switching. This is the "many specialists,
one base" pattern that lets us stack 50-100 specialists at minimal
GPU cost (each LoRA is ~5-50 MB; the 1.5B base dominates VRAM).

Why this is the gate to composition

Per .planning/concerns/composition-strategy.md, the entire trillion-
effective-params plan rests on this primitive working. If we can't
get N adapters loaded simultaneously and routed per-task on a 6GB GPU
with our existing 4 specialists, no $5 (let alone $50) shot is
justified.

Usage as a library

    from scripts.serve.multi_adapter_loader import MultiAdapterModel

    model = MultiAdapterModel.from_pretrained(
        base_model_id="Qwen/Qwen2.5-1.5B-Instruct",
        adapters={
            "cli_v2":         "scrubster/dr-stein-stage25-qwen15-instruct-v2",
            "math":           "scrubster/dr-stein-colab-qwen15-math-5k",
            "tooluse":        "scrubster/dr-stein-colab-qwen15-tooluse-sanity",
            "doc_verifier":   "scrubster/dr-stein-stage25-qwen15-doc-verifier-r16",
        },
        device="cuda",
        dtype="bfloat16",
    )

    # Switch to specialist per task
    out = model.generate("Translate to gad CLI: log a state delta",
                         adapter="cli_v2")

    # Bare base (no adapter) for ablation
    out = model.generate("...", adapter=None)

Usage as a CLI smoke

    .venv-gpu/Scripts/python.exe scripts/serve/multi_adapter_loader.py \\
        --smoke \\
        --base Qwen/Qwen2.5-1.5B-Instruct \\
        --adapters cli_v2=scrubster/dr-stein-stage25-qwen15-instruct-v2 \\
                   math=scrubster/dr-stein-colab-qwen15-math-5k

Decision refs: slm-learning-049 (TIES merge), 079 (per-domain ladder),
094 (composition strategy), 097 (3-artifact rule).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterable

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


ROOT = Path(__file__).resolve().parents[2]


class MultiAdapterModel:
    """Wraps a base + N LoRA adapters with per-request switching."""

    def __init__(self, base_model, tokenizer, adapter_names: list[str]):
        self.base_model = base_model
        self.tokenizer = tokenizer
        self.adapter_names = adapter_names
        self._active_adapter: str | None = None

    @classmethod
    def from_pretrained(
        cls,
        *,
        base_model_id: str,
        adapters: dict[str, str],
        device: str = "cuda",
        dtype: str = "bfloat16",
    ) -> "MultiAdapterModel":
        torch_dtype = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }[dtype]

        print(f"[loader] base: {base_model_id}")
        tokenizer = AutoTokenizer.from_pretrained(base_model_id)
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token_id = tokenizer.eos_token_id

        base = AutoModelForCausalLM.from_pretrained(
            base_model_id,
            dtype=torch_dtype,
            device_map=device,
        )
        base.eval()

        if not adapters:
            return cls(base, tokenizer, [])

        first_name, first_path = next(iter(adapters.items()))
        print(f"[loader] adapter [{first_name}] <- {first_path}")
        peft_model = PeftModel.from_pretrained(
            base, first_path, adapter_name=first_name
        )
        loaded = [first_name]

        for name, path in list(adapters.items())[1:]:
            print(f"[loader] adapter [{name}] <- {path}")
            try:
                peft_model.load_adapter(path, adapter_name=name)
                loaded.append(name)
            except Exception as e:
                print(f"[loader] WARN: failed to load {name}: {e}")

        peft_model.eval()
        instance = cls(peft_model, tokenizer, loaded)
        # Default: leave whatever was loaded last as active so a bare
        # caller still gets a specialist behavior. Caller should call
        # .use_adapter(name) or .use_bare_base() explicitly.
        instance.use_adapter(loaded[0])
        return instance

    def use_adapter(self, name: str | None) -> None:
        """Switch the active adapter. None = bare base (adapters disabled)."""
        if not isinstance(self.base_model, PeftModel):
            return  # no adapters loaded
        if name is None:
            self.base_model.disable_adapter_layers()
            self._active_adapter = None
            return
        if name not in self.adapter_names:
            raise ValueError(
                f"adapter {name!r} not loaded; available: {self.adapter_names}"
            )
        self.base_model.enable_adapter_layers()
        self.base_model.set_adapter(name)
        self._active_adapter = name

    @property
    def active_adapter(self) -> str | None:
        return self._active_adapter

    @torch.no_grad()
    def generate(
        self,
        prompt: str,
        *,
        adapter: str | None = "__use_current__",
        max_new_tokens: int = 200,
        temperature: float = 0.0,
        system_prompt: str | None = None,
    ) -> str:
        if adapter != "__use_current__":
            self.use_adapter(adapter)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            text = (
                (system_prompt + "\n\n" if system_prompt else "")
                + prompt + "\n"
            )

        inputs = self.tokenizer(text, return_tensors="pt").to(
            self.base_model.device
        )
        do_sample = temperature > 0.0
        outputs = self.base_model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            temperature=temperature if do_sample else 1.0,
            pad_token_id=self.tokenizer.pad_token_id,
        )
        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True)


def parse_adapter_specs(specs: Iterable[str]) -> dict[str, str]:
    """Parse `name=path` pairs from CLI."""
    out: dict[str, str] = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"adapter spec must be name=path, got {spec!r}")
        name, path = spec.split("=", 1)
        out[name.strip()] = path.strip()
    return out


def smoke_test(model: MultiAdapterModel, *, max_new_tokens: int = 64) -> dict:
    """Run a tiny prompt through each adapter + bare base; capture timing."""
    prompt = "Translate this to a gad CLI command: log a state delta saying tests passed."
    sys_prompt = (
        "You are an assistant. Translate the user's request into a single "
        "gad CLI command. Output only the command on one line."
    )

    results = []

    # Bare base
    t0 = time.time()
    bare = model.generate(prompt, adapter=None, max_new_tokens=max_new_tokens,
                          system_prompt=sys_prompt)
    results.append({
        "adapter": None,
        "elapsed_seconds": round(time.time() - t0, 3),
        "output": bare.strip()[:200],
    })

    # Each adapter
    for name in model.adapter_names:
        t0 = time.time()
        out = model.generate(prompt, adapter=name, max_new_tokens=max_new_tokens,
                             system_prompt=sys_prompt)
        results.append({
            "adapter": name,
            "elapsed_seconds": round(time.time() - t0, 3),
            "output": out.strip()[:200],
        })

    return {
        "smoke": "multi_adapter_loader",
        "n_adapters": len(model.adapter_names),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True,
                        help="HF Hub id or local path of base model")
    parser.add_argument("--adapters", nargs="+", default=[],
                        help="adapter specs as name=path entries")
    parser.add_argument("--smoke", action="store_true",
                        help="Run the smoke test against all adapters")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="bfloat16",
                        choices=["bfloat16", "float16", "float32"])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    adapters = parse_adapter_specs(args.adapters)
    model = MultiAdapterModel.from_pretrained(
        base_model_id=args.base,
        adapters=adapters,
        device=args.device,
        dtype=args.dtype,
    )

    if args.smoke:
        result = smoke_test(model)
        body = json.dumps(result, indent=2, ensure_ascii=False)
        print(body)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(body, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
