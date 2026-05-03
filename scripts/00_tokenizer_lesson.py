from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from slm_from_scratch.tokenizer import CharTokenizer


def print_section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def main() -> None:
    text = "Question: What is 2 + 2?\nReasoning: 2 plus 2 equals 4.\nAnswer: 4\n"

    print_section("1. Raw text")
    print(repr(text))
    print()
    print(text)

    tokenizer = CharTokenizer.from_text(text)

    print_section("2. Vocabulary")
    print("The tokenizer builds a table of every character it sees.")
    print()
    print("Character -> token ID")
    for character, token_id in tokenizer.stoi.items():
        print(f"{repr(character):>8} -> {token_id}")

    print()
    print(f"Vocabulary size: {tokenizer.vocab_size}")

    encoded = tokenizer.encode(text)

    print_section("3. Encoding")
    print("Encoding converts text into token IDs.")
    print()
    print(encoded)

    decoded = tokenizer.decode(encoded)

    print_section("4. Decoding")
    print("Decoding converts token IDs back into text.")
    print()
    print(repr(decoded))
    print()
    print(decoded)

    print_section("5. Round trip check")
    print("If this says True, the tokenizer can safely convert text -> IDs -> text.")
    print()
    print(decoded == text)

    print_section("6. Next-token prediction view")
    print("A language model trains by seeing an input sequence and predicting the next token.")
    print()
    print("For example:")

    for index in range(min(24, len(encoded) - 1)):
        input_id = encoded[index]
        target_id = encoded[index + 1]
        input_char = tokenizer.decode([input_id])
        target_char = tokenizer.decode([target_id])
        print(
            f"input token {input_id:>2} {repr(input_char):>6} "
            f"-> target token {target_id:>2} {repr(target_char):>6}"
        )

    print_section("7. Unknown character failure")
    print("This tokenizer only knows characters from the training text.")
    print("So if we encode a new character that was not in the vocabulary, it fails.")
    print()

    try:
        tokenizer.encode("Question: What is 9 * 9?")
    except ValueError as error:
        print("Expected error:")
        print(error)

    print_section("Lesson complete")
    print("You now have the first piece of an LLM pipeline:")
    print()
    print("text -> tokenizer -> token IDs -> model -> predicted token IDs -> decoded text")


if __name__ == "__main__":
    main()
