from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass
class CharTokenizer:
    """A deliberately simple character tokenizer.

    This is not how production LLMs tokenize text, but it is perfect for
    learning because every operation is visible: text -> integer ids -> text.
    """

    stoi: Dict[str, int]
    itos: Dict[int, str]

    @classmethod
    def from_text(cls, text: str, extra_tokens: Iterable[str] | None = None) -> "CharTokenizer":
        chars = sorted(set(text))
        if extra_tokens is not None:
            for token in extra_tokens:
                if len(token) != 1:
                    raise ValueError("CharTokenizer extra tokens must be single characters")
                if token not in chars:
                    chars.append(token)
        stoi = {ch: i for i, ch in enumerate(chars)}
        itos = {i: ch for ch, i in stoi.items()}
        return cls(stoi=stoi, itos=itos)

    @property
    def vocab_size(self) -> int:
        return len(self.stoi)

    def encode(self, text: str) -> List[int]:
        missing = sorted({ch for ch in text if ch not in self.stoi})
        if missing:
            visible = ", ".join(repr(ch) for ch in missing[:20])
            raise ValueError(f"Text contains characters missing from tokenizer vocabulary: {visible}")
        return [self.stoi[ch] for ch in text]

    def decode(self, ids: Iterable[int]) -> str:
        return "".join(self.itos[int(i)] for i in ids)

    def to_state(self) -> Dict[str, Dict]:
        return {"stoi": self.stoi, "itos": {str(k): v for k, v in self.itos.items()}}

    @classmethod
    def from_state(cls, state: Dict[str, Dict]) -> "CharTokenizer":
        stoi = {str(k): int(v) for k, v in state["stoi"].items()}
        itos = {int(k): str(v) for k, v in state["itos"].items()}
        return cls(stoi=stoi, itos=itos)
