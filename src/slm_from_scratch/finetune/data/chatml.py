"""ChatML formatter — turns (instruction, response) into a chat string.

Single concern: a string transform. No model, no tokenizer here.
"""
from __future__ import annotations


def format_pair_as_chatml(
    instruction: str,
    response: str,
    *,
    system_prompt: str = "",
) -> list[dict]:
    """Return a list of `{role, content}` dicts in HF chat-template form."""
    msgs: list[dict] = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.append({"role": "user", "content": instruction})
    msgs.append({"role": "assistant", "content": response})
    return msgs
