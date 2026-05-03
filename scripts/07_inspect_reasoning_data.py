from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the generated reasoning dataset.")
    parser.add_argument("--path", type=Path, default=Path("data/reasoning.txt"))
    parser.add_argument("--examples", type=int, default=3)
    parser.add_argument("--chars", type=int, default=2200)
    args = parser.parse_args()

    if not args.path.exists():
        raise FileNotFoundError(
            f"Missing {args.path}. Generate it first with scripts/02_make_reasoning_data.py."
        )

    text = args.path.read_text(encoding="utf-8")
    examples = [item.strip() for item in text.split("<|end|>") if item.strip()]

    print(f"path: {args.path}")
    print(f"characters: {len(text):,}")
    print(f"examples: {len(examples):,}")
    print()
    print("=" * 80)
    print("FIRST EXAMPLES")
    print("=" * 80)

    for index, example in enumerate(examples[: args.examples], start=1):
        print()
        print(f"--- example {index} ---")
        print(example)
        print("<|end|>")

    print()
    print("=" * 80)
    print("RAW START OF FILE")
    print("=" * 80)
    print(text[: args.chars])


if __name__ == "__main__":
    main()
