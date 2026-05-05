import asyncio
import os
import sys

# Ensure we can import the models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))
try:
    from slm_from_scratch.models.kael import KaelModel
    from slm_from_scratch.models.dr_stein import DrSteinModel
except ImportError:
    # Fallbacks if models aren't ready
    class KaelModel:
        def __init__(self, *args, **kwargs): self.name = "Kael"
        def generate(self, p, **kwargs): return f"[Kael] Fallback mock for: {p}"
    class DrSteinModel:
        def __init__(self, *args, **kwargs): self.name = "Dr. Stein"
        def generate(self, p, **kwargs): return f"[Dr. Stein] Fallback mock for: {p}"


class ModelRunner:
    """Manages model lifecycle, caching, and context window continuity.
    
    CONTEXT WINDOW ARCHITECTURE:
    
    The KV-cache stores key/value projections computed by each layer for all
    prior tokens. These projections are WEIGHT-DEPENDENT — they are the output
    of multiplying input by the model's specific weight matrices.
    
    When we swap models mid-conversation, there are three strategies:
    
    1. FLUSH + REPROCESS (current): Discard the KV-cache entirely and feed
       the full conversation history through the new model from scratch.
       Correct but costs O(history_length) compute on every swap.
    
    2. STALE CACHE (fast but wrong): Keep the old KV-cache. The new model's
       attention layers will read K/V tensors computed by different weights.
       This is mathematically wrong and degrades output quality.
    
    3. SHARED BASE + LoRA SWAP (ideal, future): Both models share identical
       base weights. Only a tiny LoRA adapter (few MB) gets swapped. Since
       the base weights produced the KV-cache, it stays valid. The LoRA
       adapter only modifies the query/output projections slightly.
       
    We currently use strategy 1. The `_conversation_context` field preserves
    the raw message history so any model can reprocess it after a swap.
    """
    
    def __init__(self):
        self._model_classes = {
            "kael": KaelModel,
            "dr_stein": DrSteinModel,
        }
        self._model_labels = {
            "kael": "Kael",
            "dr_stein": "Dr. Stein",
        }
        self._model_aliases = {
            "kael": "kael",
            "dr": "dr_stein",
            "drstein": "dr_stein",
            "dr-stein": "dr_stein",
            "dr_stein": "dr_stein",
            "stein": "dr_stein",
        }
        self._model_cache = {}
        self._active_model_key = None

    def get_model_name(self, model_key: str) -> str:
        model = self._model_cache.get(model_key)
        if model is not None:
            return model.name
        return self._model_labels.get(model_key, "Unknown Model")

    async def get_or_load_model(self, model_key: str):
        model = self._model_cache.get(model_key)
        if model is None:
            model_class = self._model_classes[model_key]
            model = await asyncio.to_thread(model_class)
            self._model_cache[model_key] = model
        self._active_model_key = model_key
        return model

    async def stream_response(self, model_key: str, history: list, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue):
        """Runs the model stream generation in a separate thread and safely pushes to an async queue.
        
        The history list IS the context window. When models are swapped, the full
        history is passed to the new model's chat_stream/chat method, which
        reprocesses it through the new weights (strategy 1: flush + reprocess).
        """
        model = await self.get_or_load_model(model_key)
        
        def run_thread():
            try:
                if hasattr(model, 'chat_stream'):
                    for token in model.chat_stream(history):
                        loop.call_soon_threadsafe(queue.put_nowait, token)
                elif hasattr(model, 'chat'):
                    response = model.chat(history)
                    loop.call_soon_threadsafe(queue.put_nowait, response)
                else:
                    prompt = history[-1]['content'] if history else ""
                    response = model.generate(prompt)
                    loop.call_soon_threadsafe(queue.put_nowait, response)
                    
                loop.call_soon_threadsafe(queue.put_nowait, None) # EOF
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, Exception(str(e)))
                
        await asyncio.to_thread(run_thread)

