"""
Evaluate a single checkpoint against HumanEval (pass@1).

  .venv-gpu/Scripts/python.exe scripts/eval_humaneval.py \
      --checkpoint runs/finetuned/dr_stein.pt \
      --out runs/eval/dr_stein_humaneval.json \
      --n 50

For each problem:
  1. Prompt the model with the function signature + docstring (raw text
     completion, no chat template — these models are barely fine-tuned).
  2. Generate up to --max-new-tokens of completion.
  3. Compose `prompt + completion + test + check(entry_point)` and exec
     it in an isolated subprocess with a hard timeout. Pass = subprocess
     exit 0 within the timeout.

Score = pass@1 = passed / total.

Notes:
  - Our 162.8M SmolLM2-derived models are not expected to score above
    chance. The point is to *establish a numeric baseline* and have the
    harness wired before any code-focused training.
  - Subprocess execution is the safety boundary; user is running locally.
    Each candidate runs with a 10s timeout. Net effect of a malicious
    completion is "10s of CPU + a hung interpreter killed by timeout."
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load_problems(parquet_path: Path, n: int) -> list[dict]:
    import pyarrow.parquet as pq
    table = pq.read_table(parquet_path)
    rows = table.to_pylist()
    if n > 0:
        rows = rows[:n]
    return rows


def run_one_test(prompt: str, completion: str, test: str, entry_point: str,
                 timeout_sec: int) -> tuple[bool, str]:
    """Exec a candidate solution in a fresh subprocess. Returns (passed, reason)."""
    script = (
        f"{prompt}{completion}\n\n"
        f"{test}\n\n"
        f"check({entry_point})\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script)
        temp_path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, temp_path],
            timeout=timeout_sec,
            capture_output=True,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0:
            return True, "ok"
        err = (proc.stderr or "").strip().splitlines()
        return False, (err[-1] if err else f"exit={proc.returncode}")[:200]
    except subprocess.TimeoutExpired:
        return False, f"timeout {timeout_sec}s"
    except Exception as e:
        return False, f"runner-error: {e}"[:200]
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "external" / "humaneval" / "test.parquet")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--name", default=None)
    parser.add_argument("--n", type=int, default=50, help="0 = all 164 problems")
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout-sec", type=int, default=10)
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

    from slm_from_scratch.models.loader import load_model_for_eval
    model = load_model_for_eval(args.checkpoint, device=args.device)
    print(f"Loaded {args.checkpoint} (device={model.device}); HumanEval n={len(problems)}, "
          f"max_new_tokens={args.max_new_tokens}, temp={args.temperature}")

    started = time.time()
    results = []
    for i, p in enumerate(problems, start=1):
        prompt = p["prompt"]
        t0 = time.time()
        try:
            completion = model.generate(prompt, max_new_tokens=args.max_new_tokens,
                                        temperature=args.temperature)
        except Exception as e:
            completion = ""
            gen_err = str(e)
        else:
            gen_err = None
        gen_dt = time.time() - t0

        ok, reason = run_one_test(prompt, completion, p["test"], p["entry_point"],
                                  timeout_sec=args.timeout_sec)
        marker = "[OK]" if ok else "[FAIL]"
        print(f"  {marker} {i:03d}/{len(problems)} {p['task_id']} "
              f"(gen {gen_dt:.1f}s, {reason})", flush=True)
        results.append({
            "task_id": p["task_id"],
            "entry_point": p["entry_point"],
            "completion": completion,
            "passed": ok,
            "reason": reason,
            "gen_sec": round(gen_dt, 2),
            "gen_error": gen_err,
        })

    elapsed = time.time() - started
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    pct = 100.0 * passed / total if total else 0.0
    summary = {
        "benchmark": "humaneval",
        "checkpoint": str(args.checkpoint.relative_to(ROOT)) if args.checkpoint.is_relative_to(ROOT) else str(args.checkpoint),
        "device": str(model.device),
        "temperature": args.temperature,
        "max_new_tokens": args.max_new_tokens,
        "n": total,
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_sec": round(elapsed, 1),
        "passed": passed,
        "total": total,
        "pass_at_1": pct,
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n{passed}/{total} passed ({pct:.1f}%) in {elapsed:.1f}s — wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
