"""Re-judge a persisted HumanEval eval JSON with the patched fence-stripping
regex. Used to verify the fix at scripts/diag-2026-05-08/_eval_ladder_*_full.json
without paying for a Modal re-fire.

The patch replaces \\s* (which ate the body's 4-space indent on the first
line) with [ \\t]* (inline whitespace only). This script applies the
patched judge to existing completion_full strings and reports the new
score.

Usage:
    python scripts/eval/rejudge_he_local.py tmp/diag-2026-05-08/_14b_he_full.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from datasets import load_dataset


def _strip_post_answer_pollution(code: str) -> str:
    # Light strip — drop trailing pure-whitespace and any obvious test/check
    # noise the model trailed. Real strip lives in eval_adapter.py.
    lines = code.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def patched_judge(prefix: str, completion: str, test_block: str,
                  entry_point: str) -> tuple[bool, str]:
    code = completion
    if "<think>" in code:
        if "</think>" in code:
            code = re.sub(r"<think>.*?</think>", "", code, flags=re.DOTALL)
        else:
            code = code.split("<think>")[0]

    # PATCHED REGEX — was \s*\n?, now [ \t]*\n?
    m = re.search(r"```(?:python)?[ \t]*\n?(.*?)\n?```", code, re.DOTALL)
    if m:
        code = m.group(1).rstrip()
        lines = code.split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        code = "\n".join(lines)

    imports = (
        "from typing import List, Dict, Tuple, Optional, Any, Set, "
        "FrozenSet, Union, Callable, Iterable, Iterator\n"
        "import math, re, json, collections, itertools, functools\n\n"
    )

    if prefix:
        code = _strip_post_answer_pollution(code)
        first_nonblank = next((ln for ln in code.split("\n") if ln.strip()), "")
        if first_nonblank and not first_nonblank[0].isspace():
            stripped = first_nonblank.lstrip()
            is_full_def = (stripped.startswith("def ") or
                           stripped.startswith("async def ") or
                           stripped.startswith("from ") or
                           stripped.startswith("import "))
            if not is_full_def:
                code = "\n".join("    " + ln if ln.strip() else ln
                                 for ln in code.split("\n"))
        program = imports + prefix + code + "\n\n" + textwrap.dedent(test_block) + "\n"
    else:
        program = imports + textwrap.dedent(code) + "\n\n" + textwrap.dedent(test_block) + "\n"

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                       encoding="utf-8") as f:
        f.write(program)
        path = f.name

    try:
        proc = subprocess.run(["python", path], capture_output=True, text=True,
                              timeout=15)
        if proc.returncode == 0:
            return True, "ok"
        return False, (proc.stderr or proc.stdout or "non-zero exit")[:200]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, repr(e)[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Path to persisted humaneval_*.json")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    data = json.load(open(args.input, encoding="utf-8"))
    results = data["results"]
    if args.limit:
        results = results[:args.limit]

    ds = load_dataset("openai/openai_humaneval", split="test")
    prefix_by_id = {row["task_id"]: row["prompt"] for row in ds}
    test_by_id = {row["task_id"]: row["test"] + f"\ncheck({row['entry_point']})"
                  for row in ds}

    n_pass = 0
    n_total = len(results)
    new_pass_was_fail = 0
    new_fail_was_pass = 0
    for r in results:
        tid = r["id"]
        prefix = prefix_by_id.get(tid, "")
        test = test_by_id.get(tid, "")
        passed, _reason = patched_judge(prefix, r["completion_full"], test,
                                         entry_point=tid.split("/")[-1])
        if passed:
            n_pass += 1
        was_passed = r["passed"]
        if passed and not was_passed:
            new_pass_was_fail += 1
        if was_passed and not passed:
            new_fail_was_pass += 1

    pct = round(100 * n_pass / max(1, n_total), 2)
    print(f"Input: {args.input}")
    print(f"Original score: {data['score']*100:.2f}% ({data['passed']}/{data['n']})")
    print(f"Patched score:  {pct}% ({n_pass}/{n_total})")
    print(f"Changes: +{new_pass_was_fail} flipped fail->pass, "
          f"-{new_fail_was_pass} flipped pass->fail (regression)")


if __name__ == "__main__":
    sys.exit(main())
