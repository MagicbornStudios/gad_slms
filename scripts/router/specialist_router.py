"""Task -> specialist-adapter router (rule-based v1).

Different from `runtime_select.py` (which picks a CLI runtime like
codex / gemini / opencode). This router picks the LoRA ADAPTER inside
our model's multi-adapter ensemble — given a task instruction, decide
which specialist (cli_v2 / math / tooluse / doc_verifier / generic)
should handle it.

Per .planning/concerns/composition-strategy.md, this is the "Hard
router (rule-based v1)" component. Soft router replaces this once we
have 500+ routing decisions logged.

Heuristics

- Math word-problem-shaped instructions -> math
- gad CLI translation requests -> cli_v2
- "verify this claim against the codebase" -> doc_verifier
- "predict next tool call" or tool-call-shaped context -> tooluse
- everything else -> generic (use bare base)

Usage

    from scripts.router.specialist_router import classify

    adapter = classify("Mark task 02-02 as done.")
    # -> "cli_v2"

    adapter = classify("If a train leaves Chicago at 3pm...")
    # -> "math"

    adapter = classify(None)
    # -> "generic"  (None / unknown defaults to bare-base)

CLI

    .venv/Scripts/python.exe scripts/router/specialist_router.py \\
        --instruction "Verify the claim 'gad CLI lives at gad/main.py'"
    -> doc_verifier
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Callable


SPECIALIST_GENERIC = "generic"
SPECIALIST_CLI = "cli_v2"
SPECIALIST_MATH = "math"
SPECIALIST_TOOLUSE = "tooluse"
SPECIALIST_DOC_VERIFIER = "doc_verifier"

KNOWN_SPECIALISTS = {
    SPECIALIST_GENERIC,
    SPECIALIST_CLI,
    SPECIALIST_MATH,
    SPECIALIST_TOOLUSE,
    SPECIALIST_DOC_VERIFIER,
}


# Each rule returns the specialist name OR None (no match). Order matters —
# more specific rules first.
def _is_doc_verifier(instr: str) -> bool:
    s = instr.lower()
    return (
        ("verify" in s and "claim" in s)
        or "verify the following claim" in s
        or "claim category" in s
        or s.startswith("verify the claim")
    )


def _is_math(instr: str) -> bool:
    s = instr.lower()
    # Word-problem cues
    word_cues = (
        "if a", "how many", "how much", "calculate",
        "what is the value", "solve for", "x =", "y =",
        "speed of", "rate of", "find the", "the sum of",
        "the product of", "the difference between",
        "twice as", "times as", "times faster", "times the speed",
        "how old", "years ago", "blinks", "ratio of",
        "percent of", "percentage of", "average of",
    )
    if any(c in s for c in word_cues):
        return True
    # Bare equation patterns
    if re.search(r"\d+\s*[+\-*/=^]\s*\d+", instr):
        return True
    # Multiple numbers + question mark = likely math
    nums = re.findall(r"\b\d+\b", instr)
    if len(nums) >= 2 and "?" in instr:
        return True
    return False


def _is_cli(instr: str) -> bool:
    s = instr.lower()
    cli_cues = (
        "log a state", "log a delta",
        "track an error", "record a decision",
        "claim handoff", "stamp task", "mark task",
        "add a note", "take a note", "jot down",
        "what's the next action", "next-action",
        "hydrate", "snapshot",
        "open handoff", "open handoffs", "list tasks", "list notes",
        "blocked", "verify phase", "promote",
        "what's blocking",
        # broader cues for natural-language asks
        "what tasks are open", "what tasks", "tasks are open",
        "diagnose", "health of", "health check",
        "phase ", "close out phase", "append a phase",
        "remember to", "remind me", "remind myself",
        "i want to remember", "i want to remind",
        "list every gad", "list all gad", "list registered",
        "every gad project", "current evolution",
        "what recipes",
        "show me the open", "show me the current",
    )
    if any(c in s for c in cli_cues):
        return True
    if "gad " in s or " gad" in s:
        return True
    # Phrasing like "JSON tool call that adds a note" is CLI translation
    # of an action verb (note, task, decision); tooluse is about
    # session-level tool-call sequencing
    if any(v in s for v in ("adds a note", "adds a task", "adds a decision")):
        return True
    return False


def _is_tooluse(instr: str) -> bool:
    s = instr.lower()
    cues = (
        "[tool_call]",
        "tool call",
        "next tool call",
        "choose the next",
        "given the recent tool",
        "Tool(",
    )
    if any(c.lower() in s for c in cues):
        return True
    return False


_RULES: list[tuple[Callable[[str], bool], str]] = [
    (_is_doc_verifier, SPECIALIST_DOC_VERIFIER),
    (_is_tooluse, SPECIALIST_TOOLUSE),
    (_is_cli, SPECIALIST_CLI),
    (_is_math, SPECIALIST_MATH),
]


def classify(instruction: str | None) -> str:
    """Return one of KNOWN_SPECIALISTS for an instruction string."""
    if not instruction or not instruction.strip():
        return SPECIALIST_GENERIC
    for rule_fn, label in _RULES:
        try:
            if rule_fn(instruction):
                return label
        except Exception:
            continue
    return SPECIALIST_GENERIC


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction", "-i", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    label = classify(args.instruction)
    if args.json:
        print(json.dumps({
            "instruction": args.instruction[:200],
            "specialist": label,
            "known_specialists": sorted(KNOWN_SPECIALISTS),
        }, indent=2))
    else:
        print(label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
