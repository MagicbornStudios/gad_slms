import torch
from transformers import AutoTokenizer
from typing import List, Dict
from pathlib import Path

from slm_from_scratch.model import MiniLlama, LlamaConfig

def _resolve_device(device: str) -> torch.device:
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


class KaelModel:
    """
    Kael: General Reasoning SLM
    Uses HuggingFace tokenizer and MiniLlama loaded with mapped SmolLM2 135M weights.
    """
    def __init__(self, model_path: str = None, device: str = "auto"):
        self.name = "Kael"
        self.device = _resolve_device(device)

        # SmolLM2 tokenizer — prefer local cache to avoid aiohttp session leak
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                "HuggingFaceTB/SmolLM2-135M-Instruct", local_files_only=True
            )
        except OSError:
            self.tokenizer = AutoTokenizer.from_pretrained(
                "HuggingFaceTB/SmolLM2-135M-Instruct"
            )

        # SmolLM2 135M configuration
        self.config = LlamaConfig(
            vocab_size=49152,
            block_size=2048,
            n_layer=30,
            n_head=9,
            n_kv_head=3,
            n_embd=576,
            intermediate_size=1536,
            dropout=0.0,
            bias=False,
            rms_norm_eps=1e-05,
            rope_theta=10000.0
        )
        self.model = MiniLlama(self.config)
        self.model.eval()

        if model_path is None:
            root = Path(__file__).resolve().parents[3]
            model_path = root / "runs" / "pretrained" / "smollm2_135M.pt"

        if Path(model_path).exists():
            print(f"Loading weights from {model_path} (device={self.device})...")
            checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
            self.model.load_state_dict(checkpoint['model_state_dict'])
        else:
            print(f"Warning: {model_path} not found. Weights are randomly initialized.")

        self.model.to(self.device)

    def generate(self, prompt: str, max_new_tokens: int = 50, temperature: float = 0.8) -> str:
        input_ids = self.tokenizer.encode(prompt)
        idx = torch.tensor([input_ids], dtype=torch.long, device=self.device)
        eos_id = self.tokenizer.eos_token_id

        with torch.no_grad():
            out_idx = self.model.generate(
                idx,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                eos_token_id=eos_id,
            )

        generated_idx = out_idx[0][len(input_ids):].tolist()
        return self.tokenizer.decode(generated_idx, skip_special_tokens=True)

    def chat(self, messages: List[Dict[str, str]]) -> str:
        # SmolLM2 is instruct-tuned! We can use ChatML format or HuggingFace templates.
        # AutoTokenizer has apply_chat_template which formats messages perfectly.
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        response = self.generate(prompt, max_new_tokens=150, temperature=0.7)
        return response.strip()

    def generate_stream(self, prompt: str, max_new_tokens: int = 150, temperature: float = 0.7):
        input_ids = self.tokenizer.encode(prompt)
        idx = torch.tensor([input_ids], dtype=torch.long, device=self.device)
        eos_id = self.tokenizer.eos_token_id

        for next_token_id in self.model.generate_stream(
            idx,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            eos_token_id=eos_id,
        ):
            yield self.tokenizer.decode([next_token_id], skip_special_tokens=True)

    def chat_stream(self, messages: List[Dict[str, str]]):
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        yield from self.generate_stream(prompt, max_new_tokens=150, temperature=0.7)
