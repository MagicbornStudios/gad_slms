"""
Claude-subagent teacher for GAD-tool-call distillation.

Takes the hand-curated seed in data/gad_tool_pairs.jsonl, asks a cheap
Claude model (default haiku-4-5) to generate N paraphrases per seed,
and appends the new (instruction, command) pairs to
data/distilled_pairs.jsonl.

Usage:
  # dry-run: print what would be sent, no API calls
  python scripts/distill_gad_pairs.py --dry-run

  # real distillation, 3 paraphrases per seed pair, haiku-4-5
  python scripts/distill_gad_pairs.py --paraphrases-per-seed 3

  # use a different model
  python scripts/distill_gad_pairs.py --model claude-sonnet-4-6

Requires ANTHROPIC_API_KEY in env. The teacher's system prompt forces
JSON-only output so we can parse multiple paraphrases per call cheaply.

Why Claude subagent and not OpenCode: see
~/.claude/projects/.../memory/feedback_distillation_teacher.md and
.planning/tasks/03-04.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "gad_tool_pairs.jsonl"
OUT = ROOT / "data" / "distilled_pairs.jsonl"

SYSTEM_PROMPT = """You generate training data for a small language model that translates natural-language requests into gad CLI commands.

You will receive a single (instruction, command) seed pair. Produce N alternative natural-language instructions that should map to the SAME command.

Rules:
- Each new instruction must be in plain English a developer would actually say.
- Each must clearly imply the same command — no ambiguity with other gad subcommands.
- Vary phrasing: imperatives, questions, hedged requests, terse fragments.
- Output ONLY a JSON array of strings. No prose, no markdown, no code fences.

Example:
  Seed instruction: "Take a note that the build is broken on Windows."
  Seed command: gad note add "build is broken on Windows"
  N=3
  Output: ["jot down: build broke on windows", "save a note about the broken windows build", "remember the windows build is broken"]
"""


def load_seeds(path: Path) -> list[dict]:
    pairs = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def call_claude(client, model: str, instruction: str, command: str, n: int,
                max_tokens: int = 512) -> list[str]:
    user = (
        f'Seed instruction: "{instruction}"\n'
        f"Seed command: {command}\n"
        f"N={n}\n"
        f"Output the JSON array now."
    )
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
    )
    raw = resp.content[0].text.strip()
    # Tolerate accidental code fences / leading prose
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        arr = json.loads(raw)
    except json.JSONDecodeError:
        # last-ditch: find the first [ ... ] block
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            arr = json.loads(raw[start:end + 1])
        else:
            raise
    if not isinstance(arr, list):
        raise ValueError(f"expected JSON list, got {type(arr).__name__}")
    return [str(x).strip() for x in arr if str(x).strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-file", type=Path, default=SEED)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--model", default="claude-haiku-4-5",
                        help="Cheap teacher model. claude-haiku-4-5 default.")
    parser.add_argument("--paraphrases-per-seed", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0,
                        help="Only process the first N seeds (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print a sample request, don't call the API")
    parser.add_argument("--max-tokens", type=int, default=512)
    args = parser.parse_args()

    if not args.seed_file.exists():
        print(f"seed file not found: {args.seed_file}", file=sys.stderr)
        return 2

    seeds = load_seeds(args.seed_file)
    if args.limit > 0:
        seeds = seeds[:args.limit]
    print(f"Loaded {len(seeds)} seed pairs from {args.seed_file}")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        sample = seeds[0]
        print(f"model: {args.model}")
        print(f"system_prompt (first 200 chars): {SYSTEM_PROMPT[:200]}...")
        print(f"sample user message:")
        print(f'  Seed instruction: "{sample["instruction"]}"')
        print(f"  Seed command: {sample['command']}")
        print(f"  N={args.paraphrases_per_seed}")
        est_tokens = len(seeds) * (args.max_tokens + 200)
        print(f"\nEstimated total output tokens: ~{est_tokens:,}")
        return 0

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ANTHROPIC_API_KEY not set. Export it or use --dry-run.", file=sys.stderr)
        return 2

    try:
        from anthropic import Anthropic
    except ImportError:
        print("anthropic SDK not installed. pip install anthropic", file=sys.stderr)
        return 2

    client = Anthropic()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    written = 0
    failures = 0
    with args.out.open("a", encoding="utf-8") as fout:
        for i, seed in enumerate(seeds, start=1):
            try:
                paraphrases = call_claude(
                    client, args.model,
                    seed["instruction"], seed["command"],
                    n=args.paraphrases_per_seed,
                    max_tokens=args.max_tokens,
                )
            except Exception as e:
                print(f"  [FAIL] {i:03d}/{len(seeds)} {seed['instruction'][:50]}... -> {e}",
                      flush=True)
                failures += 1
                continue
            for new_instr in paraphrases:
                fout.write(json.dumps({
                    "instruction": new_instr,
                    "command": seed["command"],
                    "source": "claude-distill",
                    "teacher": args.model,
                    "seed_instruction": seed["instruction"],
                }) + "\n")
                written += 1
            print(f"  [OK]   {i:03d}/{len(seeds)} +{len(paraphrases)} pairs "
                  f"({seed['instruction'][:40]}...)", flush=True)

    elapsed = time.time() - t0
    print(f"\nWrote {written} new pairs ({failures} failures) in {elapsed:.1f}s -> {args.out}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
