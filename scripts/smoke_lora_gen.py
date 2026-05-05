"""Quick smoke generation on the Stage 2.5 LoRA adapter — five prompts."""
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

ROOT = Path(__file__).resolve().parents[1]

BASE = "HuggingFaceTB/SmolLM2-135M-Instruct"
ADAPTER = ROOT / "experiments" / "runs" / "stage25_gad_tools_lora" / "adapter"

PROMPTS = [
    "Take a note that the build is broken on Windows.",
    "Mark task 03-04 as done.",
    "What's the next action I should pick up?",
    "Run an evolution scan for slm-learning.",
    "Show me open handoffs.",
    "Add a new task under phase 03 to draft GAD-tool training pairs.",
    "Where is the project state file located?",
    "Log a state delta saying we just shipped Stage 2.5.",
]

SYSTEM = (
    "You are Dr. Stein. Translate the user's request into a single gad "
    "CLI command. Output only the command on one line."
)

tok = AutoTokenizer.from_pretrained(str(ADAPTER))
model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16, device_map="auto")
model = PeftModel.from_pretrained(model, str(ADAPTER))
model.eval()

for p in PROMPTS:
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": p}]
    s = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    ids = tok(s, return_tensors="pt").to(model.device)
    out = model.generate(
        **ids,
        max_new_tokens=40,
        do_sample=False,
        pad_token_id=tok.eos_token_id,
    )
    gen = tok.decode(out[0][ids.input_ids.shape[1]:], skip_special_tokens=True)
    print(f">> {p}")
    print(f"   -> {gen.strip()}")
    print()
