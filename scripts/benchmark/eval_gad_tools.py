"""DEPRECATED MOCK — refuses to run.

This file used to print a hardcoded "Tool Eval Score: 3/3 (100%)" without
actually evaluating anything. That is a landmine: if any tooling ever
calls it, it returns a fake-passing score that misrepresents adapter
quality.

The REAL gad-tools eval lives at:
  - scripts/eval_checkpoint.py (the canonical 30-case promptfoo-gad-tools
    runner used by every real adapter eval, e.g.
    experiments/runs/<run>/eval_gad_tools.json)
  - scripts/delta/eval_candidate.py --benchmarks gad_tools (the daemon-
    facing wrapper that produces a verdict envelope)
  - scripts/benchmark/run_per_cohort.py (the per-cohort dispatcher per
    workstream-d-4)

Use those instead. This file refuses to run with a clear error so a
caller is forced to switch over.
"""
from __future__ import annotations
import sys


def main() -> int:
    print(
        "ERROR: scripts/benchmark/eval_gad_tools.py is a DEPRECATED MOCK "
        "that returned hardcoded fake scores. It refuses to run.\n\n"
        "Use one of:\n"
        "  scripts/eval_checkpoint.py --candidate <adapter>\n"
        "  scripts/delta/eval_candidate.py --candidate-dir <dir> "
        "--benchmarks gad_tools\n"
        "  scripts/benchmark/run_per_cohort.py --adapter <id> --cohort-id "
        "<project>-eval",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
