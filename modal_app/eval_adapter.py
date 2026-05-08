"""Modal eval app — score a trained adapter on HumanEval / MBPP / a mixed bag.

Pulls the adapter from HF Hub OR slm-models volume, runs N benchmark
problems through it, returns scored JSON. The companion to
modal_app/train_lora.py — every adapter we train can be eval'd via:

    modal run modal_app/eval_adapter.py::main \\
        --adapter-id scrubster/dr-stein-ladder-7b-coder-smoke \\
        --base-model Qwen/Qwen2.5-Coder-7B-Instruct \\
        --benchmark humaneval \\
        --limit 20 --gpu A10G

Per slm-learning-103 (compare-and-compete): every candidate produces
a row with score + cost + lineage. This script is the per-candidate
scorer; the matrix runner aggregates many such rows.

Benchmarks supported:
- humaneval — 164 Python function-completion tasks (subset via --limit)
- mbpp — 974 basic Python problems (subset via --limit)
- code_smoke — 5-task hand-curated smoke for "did it learn anything"

Decision refs: slm-learning-094, 097, 103, 105.
"""
from __future__ import annotations

import json
from pathlib import Path

import modal


app = modal.App("slm-learning-eval-adapter")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.9.1",
        "transformers>=4.50",
        "peft>=0.15",
        "datasets>=3.0",
        "accelerate>=1.0",
        "huggingface_hub>=0.30",
        "pyarrow",
    )
)

data_volume = modal.Volume.from_name("slm-data", create_if_missing=True)
models_volume = modal.Volume.from_name("slm-models", create_if_missing=True)


HUMANEVAL_TEMPLATE = """Complete the following Python function. Output ONLY the function body, no commentary, no markdown fences.

{prompt}"""


CODE_SMOKE_TASKS = [
    {
        "id": "smoke_sum",
        "prompt": "Write a Python function add(a, b) that returns the sum of two numbers.",
        "test": "assert add(2, 3) == 5\nassert add(-1, 1) == 0\nassert add(0, 0) == 0",
    },
    {
        "id": "smoke_reverse",
        "prompt": "Write a Python function reverse_string(s) that returns the reversed string.",
        "test": "assert reverse_string('hello') == 'olleh'\nassert reverse_string('') == ''\nassert reverse_string('a') == 'a'",
    },
    {
        "id": "smoke_fibonacci",
        "prompt": "Write a Python function fib(n) that returns the n-th Fibonacci number where fib(0)=0 fib(1)=1.",
        "test": "assert fib(0) == 0\nassert fib(1) == 1\nassert fib(10) == 55",
    },
    {
        "id": "smoke_count_vowels",
        "prompt": "Write a Python function count_vowels(s) that counts a, e, i, o, u (case-insensitive) in a string.",
        "test": "assert count_vowels('hello') == 2\nassert count_vowels('AEIOU') == 5\nassert count_vowels('xyz') == 0",
    },
    {
        "id": "smoke_is_prime",
        "prompt": "Write a Python function is_prime(n) that returns True if n is prime, False otherwise.",
        "test": "assert is_prime(2) == True\nassert is_prime(7) == True\nassert is_prime(1) == False\nassert is_prime(9) == False",
    },
]


@app.function(
    image=image,
    gpu="L4",
    volumes={"/data": data_volume, "/models": models_volume},
    timeout=5400,
    cpu=4,
    memory=24576,
)
def score_l4(args: dict) -> dict:
    return _score_inner(args)


@app.function(
    image=image,
    gpu="A10G",
    volumes={"/data": data_volume, "/models": models_volume},
    timeout=5400,
    cpu=4,
    memory=24576,
)
def score_a10g(args: dict) -> dict:
    return _score_inner(args)


@app.function(
    image=image,
    gpu="A100",
    volumes={"/data": data_volume, "/models": models_volume},
    timeout=7200,
    cpu=4,
    memory=49152,
)
def score_a100(args: dict) -> dict:
    return _score_inner(args)


def _score_inner(args: dict) -> dict:
    import datetime as dt
    import time

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    adapter_id = args["adapter_id"]
    base_model = args["base_model"]
    benchmark = args["benchmark"]
    limit = args.get("limit", 20)
    max_new_tokens = args.get("max_new_tokens", 384)
    # mode = "chat" (apply_chat_template, default) or "completion"
    # (raw prompt, matches the standard HumanEval harness for an apples-
    # to-apples leaderboard comparison). Per slm-learning-107.
    mode = args.get("mode", "chat")
    persist_run_id = args.get("persist_run_id")

    print(f"[eval] adapter={adapter_id} base={base_model} "
          f"benchmark={benchmark} mode={mode}")

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(base_model)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model, dtype=torch.bfloat16, device_map="auto",
    )
    if adapter_id and adapter_id != "BASE":
        model = PeftModel.from_pretrained(model, adapter_id)
    model.eval()
    print(f"[eval] model loaded in {time.time()-t0:.1f}s")

    if benchmark == "code_smoke":
        cases = CODE_SMOKE_TASKS[:limit]
    elif benchmark == "humaneval":
        cases = _load_humaneval(limit, mode=mode)
    elif benchmark == "mbpp":
        cases = _load_mbpp(limit)
    elif benchmark == "gad_tools":
        cases = _load_gad_tools(limit)
    else:
        return {"status": "error", "error": f"unknown benchmark {benchmark!r}"}

    results = []
    passed = 0
    for i, case in enumerate(cases):
        case_t0 = time.time()
        prompt_text = case["prompt"]

        if mode == "completion":
            # Raw completion mode — no chat template, no instruction wrapper.
            # The model continues from the prompt verbatim, matching the
            # standard HumanEval/MBPP completion harnesses.
            text_in = prompt_text
        else:
            msgs = [{"role": "user", "content": prompt_text}]
            try:
                text_in = tok.apply_chat_template(
                    msgs, tokenize=False, add_generation_prompt=True
                )
            except Exception:
                text_in = prompt_text + "\n"

        inputs = tok(text_in, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tok.pad_token_id,
            )
        new = out[0][inputs["input_ids"].shape[1]:]
        completion = tok.decode(new, skip_special_tokens=True)
        elapsed = time.time() - case_t0

        ok, why = _judge(case, completion)
        if ok:
            passed += 1
        results.append({
            "id": case.get("id", f"case-{i}"),
            "passed": ok,
            "judge_reason": why,
            "elapsed_s": round(elapsed, 2),
            "completion_full": completion,
            "completion_preview": completion[:300],
        })

    score = round(passed / max(1, len(cases)), 4)
    summary = {
        "schema_v": 2,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "adapter_id": adapter_id,
        "base_model": base_model,
        "benchmark": benchmark,
        "mode": mode,
        "n": len(cases),
        "passed": passed,
        "score": score,
        "results": results,
        "decision_refs": ["slm-learning-094", "slm-learning-097",
                          "slm-learning-103", "slm-learning-107"],
    }

    # Persist FULL results to slm-models volume for offline analysis
    # (the [:3000] truncation on the local print is for log readability;
    # downstream taxonomy work needs the full per-case data).
    if persist_run_id:
        import json as _json
        out_dir = Path(f"/models/eval-runs/{persist_run_id}")
        out_dir.mkdir(parents=True, exist_ok=True)
        # Slug the adapter so multiple adapters don't overwrite each other.
        # BASE → "base"; "/models/runs/foo/adapter" → "foo"; HF id → last segment.
        if not adapter_id or adapter_id == "BASE":
            slug = "base"
        else:
            parts = [p for p in adapter_id.replace("\\", "/").split("/") if p]
            # Strip trailing "adapter" if present
            if parts and parts[-1] == "adapter":
                parts = parts[:-1]
            slug = parts[-1] if parts else "unknown"
        out_path = out_dir / f"{benchmark}_{mode}_{slug}_n{len(cases)}.json"
        out_path.write_text(_json.dumps(summary, indent=2), encoding="utf-8")
        models_volume.commit()
        print(f"[eval] persisted full results to {out_path}")
        summary["persisted_path"] = str(out_path)

    print(f"[eval] DONE {benchmark} ({mode}): {passed}/{len(cases)} = {score:.3f}")
    return summary


def _strip_post_answer_pollution(code: str) -> str:
    """Strip trailing test/check definitions and markdown noise after the answer.

    HumanEval models sometimes append:
    - '# Check function to verify...'
    - 'def check_*(...)'
    - 'def test_*(...)'
    - 'if __name__ == "__main__":'
    - Stray markdown fences like '```'

    Remove everything from the first such line onwards.
    """
    import re
    lines = code.split("\n")
    kept = []
    for line in lines:
        stripped = line.lstrip()
        # Stop at common post-answer patterns
        if any(stripped.startswith(p) for p in [
            "# Check function",
            "# Test function",
            "# Verify",
            "def check_",
            "def test_",
            "if __name__",
            "```",
        ]):
            break
        kept.append(line)
    return "\n".join(kept).rstrip()


def _judge(case: dict, completion: str) -> tuple[bool, str]:
    """Run the case's test against the completion. Return (passed, reason)."""
    import re
    import subprocess
    import textwrap
    import tempfile

    # gad_tools uses assertion-based scoring (icontains/contains-any/
    # is-json), not code execution. See _load_gad_tools.
    if case.get("judge_kind") == "assertion":
        out_lc = completion.lower()
        for a in case.get("assertions", []):
            atype = a.get("type", "")
            value = a.get("value")
            if atype == "icontains":
                if not isinstance(value, str) or value.lower() not in out_lc:
                    return False, f"icontains {value!r} miss"
            elif atype == "contains-any":
                if not isinstance(value, list):
                    return False, f"contains-any needs list"
                if not any(str(v).lower() in out_lc for v in value):
                    return False, f"contains-any none of {value}"
            elif atype == "is-json":
                import json as _json
                try:
                    _json.loads(completion)
                except Exception as e:
                    return False, f"is-json failed: {e}"
            else:
                return False, f"unknown assertion type {atype!r}"
        return True, "ok"

    # Strip <think>...</think> reasoning blocks (OpenCodeReasoning style).
    # If the closing </think> is missing (truncation), drop everything
    # from <think> onwards — that means no code emerged, judge fails.
    if "<think>" in completion:
        if "</think>" in completion:
            code = re.sub(r"<think>.*?</think>", "", completion,
                           flags=re.DOTALL)
        else:
            code = completion.split("<think>")[0]
    else:
        code = completion
    # Strip code fences if present. Use rstrip-only — .strip() kills the
    # leading body indent which breaks prefix-merge for HumanEval body-
    # only completions like `    for i in range(...):`.
    m = re.search(r"```(?:python)?\s*\n?(.*?)\n?```", code, re.DOTALL)
    if m:
        code = m.group(1).rstrip()
        # Also drop any all-whitespace leading lines but preserve the
        # indent of the first non-blank line.
        lines = code.split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        code = "\n".join(lines)

    # If the case provides a `prefix` (HumanEval signature + imports),
    # prepend it. This lets a model emit "function body only" and still
    # run as a complete program. Otherwise the completion stands alone.
    prefix = case.get("prefix", "")

    # Always inject standard typing imports — many HumanEval tasks
    # reference List/Dict/etc. without an `import` line.
    imports = (
        "from typing import List, Dict, Tuple, Optional, Any, Set, "
        "FrozenSet, Union, Callable, Iterable, Iterator\n"
        "import math, re, json, collections, itertools, functools\n\n"
    )

    # Compose the test program
    test_block = case["test"]
    if prefix:
        # When prefix is provided (HumanEval), the body is expected to be
        # indented under the prefix's def signature — DO NOT dedent the
        # body or it ends up at module level.
        # First strip trailing test/check noise.
        code = _strip_post_answer_pollution(code)

        # If code starts at column 0, distinguish two cases:
        #   1. Full function definition (`def name(...):`) — leave alone;
        #      Python takes the second def (model's) over the prefix's.
        #   2. Body-only (`return x`, `for i in...`, etc.) — indent every
        #      line by 4 spaces so it falls under the prefix's def.
        first_nonblank = next((line for line in code.split("\n")
                               if line.strip()), "")
        if first_nonblank and not first_nonblank[0].isspace():
            stripped = first_nonblank.lstrip()
            is_full_def = (stripped.startswith("def ") or
                           stripped.startswith("async def ") or
                           stripped.startswith("from ") or
                           stripped.startswith("import "))
            if not is_full_def:
                # Column 0 + body-only: indent under prefix's def
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
        proc = subprocess.run(
            ["python", path],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode == 0:
            return True, "ok"
        return False, (proc.stderr or proc.stdout or "non-zero exit")[:200]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, repr(e)[:200]


def _load_humaneval(limit: int, mode: str = "chat") -> list[dict]:
    from datasets import load_dataset
    try:
        ds = load_dataset("openai/openai_humaneval", split="test")
    except Exception:
        ds = load_dataset("openai_humaneval", split="test")
    cases = []
    for i, row in enumerate(ds):
        if i >= limit:
            break
        if mode == "completion":
            # Standard completion-mode harness: feed the model the raw
            # HumanEval prompt and let it continue from there. No prefix
            # in the case (the prompt IS the prefix); the model's output
            # is the function body. The judge concatenates prompt +
            # completion + test.
            prompt_for_model = row["prompt"]
            prefix_for_judge = ""
            # In completion mode the model's output is appended to
            # prompt directly; signal to judge by prepending the prompt
            # in the prefix.
            prefix_for_judge = row["prompt"]
        else:
            prompt_for_model = HUMANEVAL_TEMPLATE.format(prompt=row["prompt"])
            prefix_for_judge = row["prompt"]
        cases.append({
            "id": row.get("task_id"),
            "prompt": prompt_for_model,
            # The full original HumanEval prompt — `def signature():\n
            # """docstring"""\n` — prepended to the model's completion
            # by _judge so a "body-only" answer is still runnable. See
            # slm-learning-103, slm-learning-107.
            "prefix": prefix_for_judge,
            "test": row["test"] + f"\ncheck({row['entry_point']})",
        })
    return cases


def _load_gad_tools(limit: int) -> list[dict]:
    """Load GAD-tool prompts from /data/eval/promptfoo-gad-tools.yaml.

    The yaml is uploaded to the slm-data volume by:
        modal volume put slm-data \\
            promptfoo-gad-tools.yaml \\
            /eval/promptfoo-gad-tools.yaml

    Each test in the YAML has:
        vars.instruction (str) — natural-language ask
        assert[].type, .value — icontains / contains-any / is-json

    We translate that into eval_adapter case format. The judge for
    gad_tools uses the same icontains/contains-any/is-json subset
    inline (no subprocess; assertion-based judging instead of
    code-execution).
    """
    import yaml
    yaml_path = Path("/data/eval/promptfoo-gad-tools.yaml")
    if not yaml_path.exists():
        # Fallback: try the slm-data volume root
        yaml_path = Path("/data/promptfoo-gad-tools.yaml")
    spec = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    cases = []
    for i, t in enumerate(spec.get("tests", [])):
        if i >= limit:
            break
        instruction = t.get("vars", {}).get("instruction", "")
        cases.append({
            "id": t.get("description", f"gad-tools-{i}"),
            "prompt": instruction,
            "assertions": t.get("assert", []),
            # Tag so the judge uses assertion-based scoring, not code exec.
            "judge_kind": "assertion",
        })
    return cases


def _load_mbpp(limit: int) -> list[dict]:
    from datasets import load_dataset
    ds = load_dataset("google-research-datasets/mbpp", "sanitized",
                      split="test")
    cases = []
    for i, row in enumerate(ds):
        if i >= limit:
            break
        # MBPP sanitized config renamed 'text' -> 'prompt' on HF Hub.
        # Fall back to 'text' for older snapshots.
        text = row.get("prompt") or row.get("text") or ""
        prompt = (
            f"Solve this Python problem. Output only the function definition.\n\n"
            f"{text}\n\nExample test:\n{row['test_list'][0]}"
        )
        test = "\n".join(row["test_list"])
        cases.append({
            "id": f"mbpp-{row.get('task_id', i)}",
            "prompt": prompt,
            "test": test,
        })
    return cases


@app.local_entrypoint()
def main(adapter_id: str, base_model: str, benchmark: str = "code_smoke",
         limit: int = 5, gpu: str = "L4",
         max_new_tokens: int = 384, mode: str = "chat",
         persist_run_id: str = "") -> None:
    args = {
        "adapter_id": adapter_id,
        "base_model": base_model,
        "benchmark": benchmark,
        "limit": limit,
        "max_new_tokens": max_new_tokens,
        "mode": mode,
        "persist_run_id": persist_run_id or None,
    }
    fn = {"L4": score_l4, "A10G": score_a10g, "A100": score_a100}.get(
        gpu, score_l4)
    print(f"[main] firing eval on Modal {gpu} for {adapter_id} "
          f"on {benchmark} (n={limit}, mode={mode})")
    result = fn.remote(args)
    print()
    print(json.dumps(result, indent=2)[:3000])
