from typing import List, Dict
from slm_from_scratch.models.kael import KaelModel

class DrSteinModel(KaelModel):
    """
    Dr. Stein: Meta-SLM & GAD Expert
    Extends Kael's SmolLM2 architecture base but injects GAD context.
    """
    def __init__(self, model_path: str = None):
        if model_path is None:
            from pathlib import Path
            root = Path(__file__).resolve().parents[3]
            model_path = root / "runs" / "finetuned" / "dr_stein.pt"
            # Fallback to pretrained if finetuned doesn't exist yet
            if not model_path.exists():
                model_path = root / "runs" / "pretrained" / "smollm2_135M.pt"
        
        super().__init__(model_path)
        self.name = "Dr. Stein"

    def chat(self, messages: List[Dict[str, str]]) -> str:
        # Load Dr. Stein's soul if available
        system_prompt = "You are Dr. Stein, an eccentric mad scientist AI specialized in the GAD framework."
        try:
            from pathlib import Path
            root = Path(__file__).resolve().parents[3]
            soul_path = root / "narrative" / "souls" / "dr-stein.md"
            if soul_path.exists():
                system_prompt = soul_path.read_text()[:500]
        except:
            pass

        # Because SmolLM2 is an instruct model, we just prepend the system prompt as a system message
        if not any(m['role'] == 'system' for m in messages):
            messages = [{"role": "system", "content": system_prompt}] + messages

        return super().chat(messages)

    def chat_stream(self, messages: List[Dict[str, str]]):
        system_prompt = "You are Dr. Stein, an eccentric mad scientist AI specialized in the GAD framework."
        try:
            from pathlib import Path
            root = Path(__file__).resolve().parents[3]
            soul_path = root / "narrative" / "souls" / "dr-stein.md"
            if soul_path.exists():
                system_prompt = soul_path.read_text()[:500]
        except:
            pass

        if not any(m['role'] == 'system' for m in messages):
            messages = [{"role": "system", "content": system_prompt}] + messages

        yield from super().chat_stream(messages)

    def generate_tool_call(self, prompt: str) -> Dict[str, str]:
        # Specialized method to force the model to output a JSON string, then parse it
        response = super().generate(prompt + " -> {", max_new_tokens=40)
        return {
            "name": "edit_file",
            "arguments": "{\"path\": \".planning/STATE.xml\", \"content\": \"" + response.replace('"', '') + "\"}"
        }
