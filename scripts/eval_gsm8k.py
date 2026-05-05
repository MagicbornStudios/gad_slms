"""
Evaluate a single checkpoint against GSM8K (exact-match on final number).

  .venv-gpu/Scripts/python.exe scripts/eval_gsm8k.py \
      --checkpoint runs/finetuned/dr_stein.pt \
      --out runs/eval/dr_stein_gsm8k.json \
      --n 100

Prompt format (zero-shot, raw text):
    Question: <q>
    Answer:

Parse: extract the last integer (or float) in the model's response and
compare to the gold answer (number after `####` in the GSM8K target).

Score = exact-match accuracy on the parsed final number.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


GOLD_RE = re.compile(r"####\s*([-+]?\d[\d,]*\.?\d*)")
NUM_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def normalize_number(raw: str) -> str | None:
    if raw is None:
        return None
    cleaned = raw.replace(",", "").strip()
    try:
        # Round to 6 decimal places to absorb trivial float noise; strip trailing zeros.
        f = float(cleaned)
        if f.is_integer():
            return str(int(f))
        return f"{f:.6f}".rstrip("0").rstrip(".")
    except ValueError:
        return None


def gold_number(answer: str) -> str | None:
    m = GOLD_RE.search(answer)
    if not m:
        return None
    return normalize_number(m.group(1))


def parse_predicted(text: str) -> str | None:
    # Prefer a number after a `####` marker if the model emitted one (GSM8K style).
    m = GOLD_RE.search(text)
    if m:
        return normalize_number(m.group(1))
    # Otherwise fall back to the LAST number in the text.
    nums = NUM_RE.findall(text)
    if not nums:
        return None
    return normalize_number(nums[-1])


def load_problems(parquet_path: Path, n: int) -> list[dict]:
    import pyarrow.parquet as pq
    rows = pq.read_table(parquet_path).to_pylist()
    if n > 0:
        rows = rows[:n]
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "external" / "gsm8k" / "test.parquet")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--name", default=None)
    parser.add_argument("--n", type=int, default=100, help="0 = all 1319 problems")
    parser.add_argument("--max-new-tokens", type=int, default=200)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    if not args.checkpoint.exists():
        print(f"checkpoint not found: {args.checkpoint}", file=sys.stderr)
        return 2
    if not args.data.exists():
        print(f"data not found: {args.data}", file=sys.stderr)
        return 2

    problems = load_problems(args.data, args.n)
    if not problems:
        print("no problems loaded", file=sys.stderr)
        return 2

    from slm_from_scratch.models.dr_stein import DrSteinModel
    model = DrSteinModel(model_path=str(args.checkpoint), device=args.device)
    print(f"Loaded {args.checkpoint} (device={model.device}); GSM8K n={len(problems)}, "
          f"max_new_tokens={args.max_new_tokens}, temp={args.temperature}")

    started = time.time()
    results = []
    for i, p in enumerate(problems, start=1):
        question = p["question"]
        gold = gold_number(p["answer"])
        prompt = f"Question: {question}\nAnswer:"
        t0 = time.time()
        try:
            completion = model.generate(prompt, max_new_tokens=args.max_new_tokens,
                                        temperature=args.temperature)
            gen_err = None
        except Exception as e:
            completion = ""
            gen_err = str(e)
        gen_dt = time.time() - t0

        predicted = parse_predicted(completion)
        ok = (gold is not None and predicted is not None and gold == predicted)
        marker = "[OK]" if ok else "[FAIL]"
        if i <= 5 or i % 25 == 0:
            print(f"  {marker} {i:04d}/{len(problems)} pred={predicted} gold={gold} "
                  f"(gen {gen_dt:.1f}s)", flush=True)
        results.append({
            "question": question,
            "gold": gold,
            "predicted": predicted,
            "completion": completion,
            "passed": ok,
            "gen_sec": round(gen_dt, 2),
            "gen_error": gen_err,
        })

    elapsed = time.time() - started
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    pct = 100.0 * passed / total if total else 0.0
    summary = {
        "benchmark": "gsm8k",
        "checkpoint": str(args.checkpoint.relative_to(ROOT)) if args.checkpoint.is_relative_to(ROOT) else str(args.checkpoint),
        "device": str(model.device),
        "temperature": args.temperature,
        "max_new_tokens": args.max_new_tokens,
        "n": total,
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_sec": round(elapsed, 1),
        "passed": passed,
        "total": total,
        "accuracy": pct,
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n{passed}/{total} correct ({pct:.1f}%) in {elapsed:.1f}s — wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
