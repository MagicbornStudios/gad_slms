"""HF SmolLM2 + PEFT-LoRA adapter wrapper.

Mirrors the surface of `DrSteinModel` (.device, .generate(prompt,
max_new_tokens, temperature)) so the existing eval scripts can score
either kind of checkpoint without branching everywhere.

Single concern: load an adapter, expose a uniform generate() that
honors temp=0 (greedy) and EOS early-stop just like our MiniLlama path.
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel


DEFAULT_SYSTEM_PROMPT = (
    "You are Dr. Stein. Translate the user's request into a single gad "
    "CLI command. Output only the command on one line."
)


class HFAdapterModel:
    """Wraps a HF base model + PEFT adapter behind a uniform generate API.

    Eval prompts arrive as raw user instructions; this wrapper applies the
    same ChatML system prompt used during fine-tuning so eval matches train.
    """

    name = "Dr. Stein (PEFT)"

    def __init__(
        self,
        adapter_dir: str | Path,
        *,
        base_model: str | None = None,
        device: str = "auto",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self.system_prompt = system_prompt
        adapter_dir = Path(adapter_dir)
        cfg_path = adapter_dir / "adapter_config.json"
        if not cfg_path.exists():
            raise FileNotFoundError(
                f"adapter_config.json not found in {adapter_dir} — "
                "this is not a PEFT adapter directory"
            )
        if base_model is None:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            base_model = cfg.get("base_model_name_or_path")
            if not base_model:
                raise ValueError(
                    "base_model_name_or_path missing from adapter_config.json"
                )

        self.device = self._resolve_device(device)
        # Tokenizer lives in the adapter dir (saved by SFTTrainer); fall back
        # to base if missing (HF restores chat template either way).
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(str(adapter_dir))
        except Exception:
            self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        dtype = torch.bfloat16 if self.device.type == "cuda" else torch.float32
        print(f"Loading base {base_model} (device={self.device}) ...")
        base = AutoModelForCausalLM.from_pretrained(
            base_model, dtype=dtype, device_map=None,
        ).to(self.device)
        print(f"Attaching adapter from {adapter_dir} ...")
        self.model = PeftModel.from_pretrained(base, str(adapter_dir))
        self.model.eval()

    @staticmethod
    def _resolve_device(device: str) -> torch.device:
        if device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(device)

    def _wrap_chatml(self, prompt: str) -> str:
        """Apply the trained-with system prompt + ChatML user turn."""
        msgs = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        return self.tokenizer.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True,
        )

    @torch.no_grad()
    def generate(
        self, prompt: str, max_new_tokens: int = 50, temperature: float = 0.0
    ) -> str:
        """Generate completion. temperature=0.0 means greedy."""
        wrapped = self._wrap_chatml(prompt)
        ids = self.tokenizer(wrapped, return_tensors="pt").to(self.device)
        gen_kwargs = {
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self.tokenizer.eos_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        if temperature == 0.0:
            gen_kwargs["do_sample"] = False
        else:
            gen_kwargs.update(
                {"do_sample": True, "temperature": temperature, "top_k": 50}
            )
        out = self.model.generate(**ids, **gen_kwargs)
        new = out[0][ids.input_ids.shape[1]:]
        return self.tokenizer.decode(new, skip_special_tokens=True)
