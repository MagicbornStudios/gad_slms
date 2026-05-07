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
    timeout=3600,
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

    print(f"[eval] adapter={adapter_id} base={base_model} benchmark={benchmark}")

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
        cases = _load_humaneval(limit)
    elif benchmark == "mbpp":
        cases = _load_mbpp(limit)
    else:
        return {"status": "error", "error": f"unknown benchmark {benchmark!r}"}

    results = []
    passed = 0
    for i, case in enumerate(cases):
        case_t0 = time.time()
        prompt_text = case["prompt"]
        msgs = [{"role": "user", "content": prompt_text}]
        try:
            text_in = tok.apply_chat_template(msgs, tokenize=False,
                                              add_generation_prompt=True)
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
            "completion_preview": completion[:300],
        })

    score = round(passed / max(1, len(cases)), 4)
    summary = {
        "schema_v": 1,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "adapter_id": adapter_id,
        "base_model": base_model,
        "benchmark": benchmark,
        "n": len(cases),
        "passed": passed,
        "score": score,
        "results": results,
        "decision_refs": ["slm-learning-094", "slm-learning-097",
                          "slm-learning-103"],
    }
    print(f"[eval] DONE {benchmark}: {passed}/{len(cases)} = {score:.3f}")
    return summary


def _judge(case: dict, completion: str) -> tuple[bool, str]:
    """Run the case's test against the completion. Return (passed, reason)."""
    import re
    import subprocess
    import textwrap
    import tempfile

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
    # Strip code fences if present
    m = re.search(r"```(?:python)?\s*\n?(.*?)\n?```", code, re.DOTALL)
    if m:
        code = m.group(1).strip()

    # Compose the test program
    test_block = case["test"]
    program = textwrap.dedent(code) + "\n\n" + textwrap.dedent(test_block) + "\n"

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


def _load_humaneval(limit: int) -> list[dict]:
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
            "test": row["test"] + f"\ncheck({row['entry_point']})",
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
         max_new_tokens: int = 384) -> None:
    args = {
        "adapter_id": adapter_id,
        "base_model": base_model,
        "benchmark": benchmark,
        "limit": limit,
        "max_new_tokens": max_new_tokens,
    }
    fn = {"L4": score_l4, "A10G": score_a10g, "A100": score_a100}.get(
        gpu, score_l4)
    print(f"[main] firing eval on Modal {gpu} for {adapter_id} on {benchmark} (n={limit})")
    result = fn.remote(args)
    print()
    print(json.dumps(result, indent=2)[:3000])
