"""DEPRECATED MOCK — refuses to run.

This file used to print hardcoded "perplexity: 15.4 / accuracy: 0.42 /
pass@1: 0.25" results without actually running any benchmark. That is a
landmine: anything that consumes its output gets fake numbers.

The REAL eval entrypoints are:
  - scripts/eval_humaneval.py   — HumanEval (n=10 by default; n=164 full)
  - scripts/eval_gsm8k.py       — GSM8K (n=50 by default)
  - scripts/eval_swebench.py    — SWE-bench Verified (subset selectable)
  - scripts/eval_checkpoint.py  — GAD-tools 30-case promptfoo eval
  - scripts/eval/eval_doc_verifier.py — doc_verifier_f1 + json_validity
  - scripts/eval/run_comparative_matrix.py — N models x M benchmarks
  - scripts/benchmark/run_per_cohort.py — per-cohort dispatcher (D-4)

This file refuses to run so callers are forced to switch.
"""
from __future__ import annotations
import sys


def main() -> int:
    print(
        "ERROR: scripts/benchmark/run_benchmarks.py is a DEPRECATED MOCK "
        "that returned hardcoded fake scores. It refuses to run.\n\n"
        "Use the per-suite scripts in scripts/eval_*.py + scripts/eval/, "
        "or scripts/eval/run_comparative_matrix.py for an N x M matrix, "
        "or scripts/benchmark/run_per_cohort.py for per-cohort dispatch.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
