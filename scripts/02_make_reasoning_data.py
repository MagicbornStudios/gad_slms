from __future__ import annotations

import argparse
import random
from pathlib import Path


def addition_example(a: int, b: int) -> str:
    answer = a + b
    return (
        f"Question: What is {a} + {b}?\n"
        f"Reasoning: Break the problem into numbers. {a} plus {b} equals {answer}.\n"
        f"Answer: {answer}\n"
        f"<|end|>\n"
    )


def subtraction_example(a: int, b: int) -> str:
    high = max(a, b)
    low = min(a, b)
    answer = high - low
    return (
        f"Question: What is {high} - {low}?\n"
        f"Reasoning: Start at {high} and remove {low}. The remaining value is {answer}.\n"
        f"Answer: {answer}\n"
        f"<|end|>\n"
    )


def comparison_example(a: int, b: int) -> str:
    if a > b:
        answer = f"{a} is greater than {b}"
        reasoning = f"Compare the two numbers. {a} is larger than {b}."
    elif b > a:
        answer = f"{b} is greater than {a}"
        reasoning = f"Compare the two numbers. {b} is larger than {a}."
    else:
        answer = f"{a} equals {b}"
        reasoning = f"Compare the two numbers. They are the same value."
    return (
        f"Question: Which is greater, {a} or {b}?\n"
        f"Reasoning: {reasoning}\n"
        f"Answer: {answer}\n"
        f"<|end|>\n"
    )


def parity_example(a: int) -> str:
    answer = "even" if a % 2 == 0 else "odd"
    return (
        f"Question: Is {a} even or odd?\n"
        f"Reasoning: Divide {a} by 2 and check the remainder. The remainder is {a % 2}.\n"
        f"Answer: {a} is {answer}\n"
        f"<|end|>\n"
    )


def make_dataset(n: int, max_n: int, seed: int) -> str:
    rng = random.Random(seed)
    examples = []
    makers = ["add", "subtract", "compare", "parity"]
    for _ in range(n):
        kind = rng.choice(makers)
        a = rng.randint(0, max_n)
        b = rng.randint(0, max_n)
        if kind == "add":
            examples.append(addition_example(a, b))
        elif kind == "subtract":
            examples.append(subtraction_example(a, b))
        elif kind == "compare":
            examples.append(comparison_example(a, b))
        elif kind == "parity":
            examples.append(parity_example(a))
        else:
            raise AssertionError(f"Unknown example kind: {kind}")
    rng.shuffle(examples)
    return "\n".join(examples)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create synthetic reasoning text for a tiny language model.")
    parser.add_argument("--out", type=Path, default=Path("data/reasoning.txt"))
    parser.add_argument("--n", type=int, default=20_000)
    parser.add_argument("--max-n", type=int, default=99)
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    text = make_dataset(n=args.n, max_n=args.max_n, seed=args.seed)
    args.out.write_text(text, encoding="utf-8")
    print(f"Wrote {args.n} examples to {args.out}")
    print(f"Characters: {len(text):,}")


if __name__ == "__main__":
    main()
