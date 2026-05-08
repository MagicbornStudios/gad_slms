"""Frontier comparator — runs HumanEval / MBPP against frontier API models.

Per slm-learning-103 (compare-and-compete), every candidate must produce
a frontier comparator row alongside our own evals. This script provides
that row for the bare 0.5B base + any candidate adapter we serve.

Comparator pool (configurable via CLI flags):
  - claude-cli (Anthropic API; needs ANTHROPIC_API_KEY)
  - OpenRouter free tier (needs OPENROUTER_API_KEY):
      meta-llama/llama-3.3-70b-instruct:free
      nvidia/llama-3.1-nemotron-70b-instruct:free
  - bare local Qwen 7B-Instruct (via vLLM if running locally; or skip)

Output: reports/comparators/<date>/frontier_he_<model>.json with the
same schema as modal_app/eval_adapter.py's persist_run_id output, so
downstream aggregators see identical fields.

Usage (when keys are present):
    python scripts/eval/frontier_comparator.py \\
        --model anthropic:claude-haiku-4-5 \\
        --benchmark humaneval --limit 164 \\
        --out-dir reports/comparators/2026-05-08

    python scripts/eval/frontier_comparator.py \\
        --model openrouter:meta-llama/llama-3.3-70b-instruct:free \\
        --benchmark mbpp --limit 164 \\
        --out-dir reports/comparators/2026-05-08

Status: scaffolded, untested against APIs. Fires only when keys are
configured. Refuses to run with empty keys (returns error code 2).

Decision refs: slm-learning-095 (comparator floor: Big Pickle / Llama-3.3-70B / Nemotron-3-Super),
slm-learning-103 (4-row matrix), slm-learning-164 (charter row 8).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]


HUMANEVAL_TEMPLATE = (
    "Complete the following Python function. Output ONLY the function body, "
    "no commentary, no markdown fences.\n\n{prompt}"
)


def load_humaneval_cases(limit: int) -> list[dict]:
    from datasets import load_dataset
    try:
        ds = load_dataset("openai/openai_humaneval", split="test")
    except Exception:
        ds = load_dataset("openai_humaneval", split="test")
    cases = []
    for i, row in enumerate(ds):
        if i >= limit:
            break
        cases.append({
            "id": row.get("task_id"),
            "prompt": HUMANEVAL_TEMPLATE.format(prompt=row["prompt"]),
            "prefix": row["prompt"],
            "test": row["test"] + f"\ncheck({row['entry_point']})",
        })
    return cases


def load_mbpp_cases(limit: int) -> list[dict]:
    from datasets import load_dataset
    ds = load_dataset("google-research-datasets/mbpp", "sanitized", split="test")
    cases = []
    for i, row in enumerate(ds):
        if i >= limit:
            break
        text = row.get("prompt") or row.get("text") or ""
        prompt = (f"Solve this Python problem. Output only the function "
                  f"definition.\n\n{text}\n\nExample test:\n{row['test_list'][0]}")
        test = "\n".join(row["test_list"])
        cases.append({
            "id": f"mbpp-{row.get('task_id', i)}",
            "prompt": prompt,
            "test": test,
        })
    return cases


def call_anthropic(model: str, prompt: str, max_tokens: int = 512) -> str:
    """Call Anthropic Messages API. Requires ANTHROPIC_API_KEY in env."""
    import anthropic  # type: ignore
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if hasattr(block, "text"))


def call_openrouter(model: str, prompt: str, max_tokens: int = 512) -> str:
    """Call OpenRouter chat completion. Requires OPENROUTER_API_KEY in env."""
    import requests  # type: ignore
    api_key = os.environ["OPENROUTER_API_KEY"]
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/slm-learning",
            "X-Title": "slm-learning frontier comparator",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def judge_he_or_mbpp(case: dict, completion: str) -> tuple[bool, str]:
    """Mirror modal_app/eval_adapter.py:_judge() for code execution scoring."""
    import re

    if "<think>" in completion:
        if "</think>" in completion:
            code = re.sub(r"<think>.*?</think>", "", completion, flags=re.DOTALL)
        else:
            code = completion.split("<think>")[0]
    else:
        code = completion
    m = re.search(r"```(?:python)?\s*\n?(.*?)\n?```", code, re.DOTALL)
    if m:
        code = m.group(1).rstrip()
        lines = code.split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        code = "\n".join(lines)

    prefix = case.get("prefix", "")
    imports = (
        "from typing import List, Dict, Tuple, Optional, Any, Set, "
        "FrozenSet, Union, Callable, Iterable, Iterator\n"
        "import math, re, json, collections, itertools, functools\n\n"
    )
    test_block = case["test"]

    if prefix:
        first_nonblank = next((line for line in code.split("\n")
                                if line.strip()), "")
        if first_nonblank and not first_nonblank[0].isspace():
            stripped = first_nonblank.lstrip()
            is_full_def = (stripped.startswith("def ") or
                            stripped.startswith("async def ") or
                            stripped.startswith("from ") or
                            stripped.startswith("import "))
            if not is_full_def:
                code = "\n".join("    " + line if line.strip() else line
                                  for line in code.split("\n"))
        program = imports + prefix + code + "\n\n" + textwrap.dedent(test_block) + "\n"
    else:
        program = imports + textwrap.dedent(code) + "\n\n" + textwrap.dedent(test_block) + "\n"

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                       encoding="utf-8") as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run(["python", path], capture_output=True,
                               text=True, timeout=15)
        if proc.returncode == 0:
            return True, "ok"
        return False, (proc.stderr or proc.stdout or "non-zero exit")[:200]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, repr(e)[:200]


def run_one(model_spec: str, benchmark: str, limit: int, out_dir: Path) -> dict:
    """Run a single (model, benchmark) cell. Persists JSON, returns summary."""
    if model_spec.startswith("anthropic:"):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("[ERROR] ANTHROPIC_API_KEY not set", file=sys.stderr)
            return {"status": "error", "error": "no_api_key"}
        backend = "anthropic"
        model_id = model_spec[len("anthropic:"):]
        caller = lambda p, mt: call_anthropic(model_id, p, mt)
    elif model_spec.startswith("openrouter:"):
        if not os.environ.get("OPENROUTER_API_KEY"):
            print("[ERROR] OPENROUTER_API_KEY not set", file=sys.stderr)
            return {"status": "error", "error": "no_api_key"}
        backend = "openrouter"
        model_id = model_spec[len("openrouter:"):]
        caller = lambda p, mt: call_openrouter(model_id, p, mt)
    else:
        return {"status": "error", "error": f"unknown spec {model_spec!r}"}

    if benchmark == "humaneval":
        cases = load_humaneval_cases(limit)
    elif benchmark == "mbpp":
        cases = load_mbpp_cases(limit)
    else:
        return {"status": "error", "error": f"unknown benchmark {benchmark!r}"}

    print(f"[frontier] {model_spec} × {benchmark} (n={len(cases)})")

    results = []
    passed = 0
    for i, case in enumerate(cases):
        t0 = time.time()
        try:
            completion = caller(case["prompt"], 512)
        except Exception as e:
            completion = ""
            print(f"[warn] case {i} api error: {e!r}", file=sys.stderr)
        ok, why = judge_he_or_mbpp(case, completion)
        if ok:
            passed += 1
        results.append({
            "id": case.get("id", f"case-{i}"),
            "passed": ok,
            "judge_reason": why,
            "elapsed_s": round(time.time() - t0, 2),
            "completion_full": completion,
            "completion_preview": completion[:300],
        })
        if (i + 1) % 25 == 0:
            print(f"[frontier]   {i+1}/{len(cases)} passed={passed}")

    score = round(passed / max(1, len(cases)), 4)
    summary = {
        "schema_v": 2,
        "ts": dt.datetime.utcnow().isoformat() + "Z",
        "adapter_id": f"FRONTIER:{model_spec}",
        "base_model": model_spec,
        "benchmark": benchmark,
        "mode": "chat",
        "n": len(cases),
        "passed": passed,
        "score": score,
        "results": results,
        "decision_refs": ["slm-learning-095", "slm-learning-103",
                          "slm-learning-164"],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    safe_model = model_spec.replace("/", "_").replace(":", "_")
    out_path = out_dir / f"{benchmark}_chat_{safe_model}_n{len(cases)}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[frontier] DONE {benchmark} ({model_spec}): "
          f"{passed}/{len(cases)} = {score:.3f}")
    print(f"[frontier] persisted to {out_path}")
    summary["persisted_path"] = str(out_path)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True,
                    help="anthropic:<model> or openrouter:<vendor/model[:tag]>")
    ap.add_argument("--benchmark", default="humaneval",
                    choices=["humaneval", "mbpp"])
    ap.add_argument("--limit", type=int, default=164)
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "reports" /
                                              "comparators" /
                                              dt.date.today().isoformat()))
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    summary = run_one(args.model, args.benchmark, args.limit, out_dir)
    if summary.get("status") == "error":
        print(f"[ERROR] {summary['error']}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps({k: v for k, v in summary.items() if k != "results"},
                      indent=2))


if __name__ == "__main__":
    main()
