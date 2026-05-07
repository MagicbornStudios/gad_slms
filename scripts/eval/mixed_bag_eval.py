"""Mixed-bag ensemble eval — does composition beat single-adapter?

Per .planning/concerns/composition-strategy.md, the architecture must
prove itself at $0 cost on our existing 4 specialists before any $5
shot is justified. This eval is the gate.

What it does

1. Curate a 50-task mixed bag from our existing eval sets:
     - 12 GAD-CLI cases (from benchmarks/promptfoo-gad-tools.yaml)
     - 13 GSM8K math cases (random subset)
     - 13 tool-use cases (random holdout from sft_tooluse.jsonl)
     - 12 doc-verifier cases (random subset of 50-pair holdout)

2. Run each task through 4 modes:
     a. Bare base (no adapter)                          — baseline-zero
     b. Single best adapter for everything (cli_v2)     — single-adapter baseline
     c. Single best adapter (math)                      — single-adapter baseline
     d. Router -> specialist (the composition mode)     — what we want to win

3. Score each mode against ground truth.

4. Emit a JSON report: per-specialist accuracy, aggregate, router
   confusion matrix.

Promotion gate

Composition wins if:
   ensemble_aggregate > best_single_adapter_aggregate + 0.10
This is a 10pp delta — strong-enough signal to justify scaling up.

Falsification

If composition LOSES (or ties within 5pp), the architecture has a
bug. Likely candidates: router accuracy, adapter contamination, base
model variance. Fix that BEFORE training new specialists at any size.

Usage

    .venv-gpu/Scripts/python.exe scripts/eval/mixed_bag_eval.py \\
        --base Qwen/Qwen2.5-1.5B-Instruct \\
        --adapter cli_v2=scrubster/dr-stein-stage25-qwen15-instruct-v2 \\
        --adapter math=scrubster/dr-stein-colab-qwen15-math-5k \\
        --adapter tooluse=scrubster/dr-stein-colab-qwen15-tooluse-sanity \\
        --adapter doc_verifier=scrubster/dr-stein-stage25-qwen15-doc-verifier-r16 \\
        --out experiments/runs/mixed_bag_eval_2026-05-07.json \\
        --seed 42

Decision refs: slm-learning-049, 094, 097.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


from router.specialist_router import classify  # noqa: E402


SYS_CLI = (
    "You are an assistant. Translate the user's request into a single "
    "gad CLI command. Output only the command on one line."
)
SYS_DOC_VERIFIER = (
    "You are gad-doc-verifier. Verify the claim against the live "
    "codebase and emit a JSON object with status (verified|refuted|"
    "unknown), evidence (list of file:line citations), and a brief "
    "reason. Output only the JSON object on one line."
)
SYS_MATH = (
    "Solve the problem step by step. End with 'Answer: <number>'."
)
SYS_TOOLUSE = (
    "You are a coding agent. Given the recent tool calls in a session, "
    "choose the next tool call. Output exactly one tool call as "
    "Tool(json_args)."
)
SYS_GENERIC = "You are a helpful assistant."


def _system_prompt_for(label: str) -> str:
    return {
        "cli_v2": SYS_CLI,
        "doc_verifier": SYS_DOC_VERIFIER,
        "math": SYS_MATH,
        "tooluse": SYS_TOOLUSE,
        "generic": SYS_GENERIC,
    }.get(label, SYS_GENERIC)


def load_gad_tools_cases(yaml_path: Path, n: int, rng: random.Random) -> list[dict]:
    try:
        import yaml
    except ImportError:
        raise SystemExit("install pyyaml")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    cases = []
    for t in data.get("tests", []):
        v = t.get("vars", {}) or {}
        # promptfoo case shape: vars.instruction is the natural-language ask
        instr = v.get("instruction") or v.get("input") or t.get("description")
        if not instr:
            continue
        # Extract a passing-token list from asserts
        asserts = t.get("assert", []) or []
        passing_tokens = []
        for a in asserts:
            v = a.get("value")
            if isinstance(v, str):
                passing_tokens.append(v)
            elif isinstance(v, list):
                passing_tokens.extend(s for s in v if isinstance(s, str))
        cases.append({
            "task_class": "gad_tools",
            "true_label": "cli_v2",
            "instruction": instr,
            "expected_tokens": [s.lower() for s in passing_tokens] or ["gad"],
            "scoring": "icontains_any",
        })
    rng.shuffle(cases)
    return cases[:n]


def load_doc_verifier_cases(jsonl_path: Path, n: int, rng: random.Random) -> list[dict]:
    rows = [json.loads(l) for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rng.shuffle(rows)
    cases = []
    for r in rows[:n]:
        try:
            gold = json.loads(r["command"])
            true_status = gold.get("status", "unknown")
        except Exception:
            true_status = "unknown"
        cases.append({
            "task_class": "doc_verifier",
            "true_label": "doc_verifier",
            "instruction": r["instruction"],
            "expected_tokens": [true_status.lower()],
            "scoring": "json_status_match",
            "true_status": true_status,
        })
    return cases


def load_gsm8k_cases(parquet_path: Path, n: int, rng: random.Random) -> list[dict]:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        raise SystemExit("install pyarrow (pip install pyarrow)")
    if not parquet_path.exists():
        return []
    table = pq.read_table(parquet_path)
    rows = table.to_pylist()
    rng.shuffle(rows)
    cases = []
    for r in rows[:n]:
        q = r.get("question", "")
        a = r.get("answer", "")
        # GSM8K answers end with `#### <number>`
        m = re.search(r"####\s*([\-\d.,]+)", a)
        true_num = m.group(1).replace(",", "").strip() if m else ""
        if not q or not true_num:
            continue
        cases.append({
            "task_class": "gsm8k",
            "true_label": "math",
            "instruction": q,
            "expected_tokens": [true_num],
            "scoring": "trailing_number_match",
            "true_number": true_num,
        })
    return cases


def load_tooluse_cases(jsonl_path: Path, n: int, rng: random.Random) -> list[dict]:
    rows = [json.loads(l) for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    # Keep the LAST 10% as holdout (a stable split)
    cut = max(1, int(len(rows) * 0.1))
    holdout = rows[-cut:]
    rng.shuffle(holdout)
    cases = []
    for r in holdout[:n]:
        # The "tool name" is in the gold command first token after Tool(
        gold = r.get("command", "")
        m = re.search(r'"tool":\s*"([^"]+)"', gold)
        tool = m.group(1) if m else None
        if not r.get("instruction") or not tool:
            continue
        cases.append({
            "task_class": "tooluse",
            "true_label": "tooluse",
            "instruction": r["instruction"],
            "expected_tokens": [tool.lower()],
            "scoring": "tool_name_match",
            "true_tool": tool,
        })
    return cases


def score_one(case: dict, output: str) -> bool:
    out = (output or "").strip().lower()
    scoring = case.get("scoring")
    expected = [s.lower() for s in case.get("expected_tokens", [])]
    if scoring == "icontains_any":
        return any(t in out for t in expected)
    if scoring == "json_status_match":
        m = re.search(r'"status"\s*:\s*"([^"]+)"', output or "")
        if not m:
            return False
        return m.group(1).lower() == case["true_status"].lower()
    if scoring == "trailing_number_match":
        nums = re.findall(r"[\-+]?\d[\d,.\-]*", output or "")
        if not nums:
            return False
        last = nums[-1].replace(",", "").rstrip(".-")
        return last == case["true_number"]
    if scoring == "tool_name_match":
        return case["true_tool"].lower() in out
    return False


def build_mixed_bag(
    *,
    seed: int,
    n_per_class: dict[str, int],
) -> list[dict]:
    rng = random.Random(seed)
    cases: list[dict] = []
    # Search a few common locations for the promptfoo file
    yaml_candidates = [
        ROOT / "promptfoo-gad-tools.yaml",
        ROOT / "benchmarks" / "promptfoo-gad-tools.yaml",
        ROOT / "benchmarks" / "gad_tools_v2" / "promptfoo-gad-tools.yaml",
    ]
    yaml_path = next((p for p in yaml_candidates if p.exists()), None)
    if yaml_path:
        cases.extend(load_gad_tools_cases(
            yaml_path, n_per_class.get("cli_v2", 12), rng,
        ))
    cases.extend(load_doc_verifier_cases(
        ROOT / "data" / "eval" / "doc_verifier_holdout.reshaped.jsonl",
        n_per_class.get("doc_verifier", 12), rng,
    ))
    cases.extend(load_gsm8k_cases(
        ROOT / "data" / "external" / "gsm8k" / "test.parquet",
        n_per_class.get("math", 13), rng,
    ))
    cases.extend(load_tooluse_cases(
        ROOT / "data" / "processed" / "gad-telemetry-2026-05-06"
                                       / "sft_tooluse.jsonl",
        n_per_class.get("tooluse", 13), rng,
    ))
    rng.shuffle(cases)
    return cases


def parse_adapter_specs(specs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"adapter spec must be name=path, got {spec!r}")
        n, p = spec.split("=", 1)
        out[n.strip()] = p.strip()
    return out


def run_mode(model, cases: list[dict], *, mode: str,
             max_new_tokens: int = 200) -> dict:
    """mode: 'bare', 'pinned:<adapter>', 'router'."""
    results = []
    correct = 0
    for case in cases:
        if mode == "bare":
            adapter = None
        elif mode.startswith("pinned:"):
            adapter = mode.split(":", 1)[1]
        elif mode == "router":
            adapter = classify(case["instruction"])
            if adapter == "generic":
                adapter = None
        else:
            raise ValueError(f"unknown mode {mode!r}")

        sys_p = _system_prompt_for(adapter or "generic")

        # Pinned mode wants its OWN prompt regardless of task
        if mode.startswith("pinned:"):
            sys_p = _system_prompt_for(mode.split(":", 1)[1])

        try:
            output = model.generate(
                case["instruction"],
                adapter=adapter if adapter else None,
                max_new_tokens=max_new_tokens,
                temperature=0.0,
                system_prompt=sys_p,
            )
        except Exception as e:
            output = f"[GEN_ERROR: {e!r}]"

        ok = score_one(case, output)
        correct += int(ok)
        results.append({
            "task_class": case["task_class"],
            "true_label": case["true_label"],
            "router_pick": classify(case["instruction"]) if mode == "router" else None,
            "adapter_used": adapter,
            "passed": ok,
            "output_preview": (output or "")[:120],
        })

    per_class = defaultdict(lambda: [0, 0])
    for r in results:
        per_class[r["task_class"]][1] += 1
        per_class[r["task_class"]][0] += int(r["passed"])

    return {
        "mode": mode,
        "n_total": len(cases),
        "passed": correct,
        "accuracy": round(correct / max(1, len(cases)), 4),
        "per_class": {k: {"passed": v[0], "total": v[1],
                          "accuracy": round(v[0]/max(1,v[1]),4)}
                      for k, v in per_class.items()},
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--adapter", action="append", default=[],
                        help="adapter spec name=path; can repeat")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-cli", type=int, default=12)
    parser.add_argument("--n-doc", type=int, default=12)
    parser.add_argument("--n-math", type=int, default=13)
    parser.add_argument("--n-tooluse", type=int, default=13)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--include-bare", action="store_true",
                        default=True)
    parser.add_argument("--max-new-tokens", type=int, default=200)
    args = parser.parse_args()

    cases = build_mixed_bag(
        seed=args.seed,
        n_per_class={
            "cli_v2": args.n_cli,
            "doc_verifier": args.n_doc,
            "math": args.n_math,
            "tooluse": args.n_tooluse,
        },
    )
    print(f"[mixed-bag] built {len(cases)} cases")
    case_summary = Counter(c["task_class"] for c in cases)
    print(f"[mixed-bag] class distribution: {dict(case_summary)}")

    # Late import so the script can be smoked offline
    from scripts.serve.multi_adapter_loader import MultiAdapterModel  # noqa
    adapters = parse_adapter_specs(args.adapter)
    print(f"[mixed-bag] loading model + {len(adapters)} adapter(s)...")
    model = MultiAdapterModel.from_pretrained(
        base_model_id=args.base,
        adapters=adapters,
        device=args.device,
        dtype=args.dtype,
    )

    modes = ["router"]
    for name in adapters.keys():
        modes.append(f"pinned:{name}")
    if args.include_bare:
        modes.append("bare")

    all_results = {}
    for mode in modes:
        print(f"[mixed-bag] running mode: {mode}")
        all_results[mode] = run_mode(model, cases, mode=mode,
                                     max_new_tokens=args.max_new_tokens)
        acc = all_results[mode]["accuracy"]
        passed = all_results[mode]["passed"]
        print(f"[mixed-bag]   {mode}: {passed}/{len(cases)} = {acc:.3f}")

    # Composition delta
    pinned_best = max(
        (v["accuracy"] for k, v in all_results.items()
         if k.startswith("pinned:")), default=0.0,
    )
    router_acc = all_results["router"]["accuracy"]
    delta = round(router_acc - pinned_best, 4)
    bare_acc = all_results.get("bare", {}).get("accuracy", 0.0)

    summary = {
        "schema_v": 1,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "base_model": args.base,
        "adapters": adapters,
        "n_cases": len(cases),
        "n_per_class": dict(case_summary),
        "modes": all_results,
        "headline": {
            "router_accuracy": router_acc,
            "best_pinned_accuracy": pinned_best,
            "bare_accuracy": bare_acc,
            "composition_delta_vs_pinned_best": delta,
            "promotion_gate_passes": delta >= 0.10,
            "promotion_gate_threshold": 0.10,
        },
        "decision_refs": ["slm-learning-049", "slm-learning-094",
                          "slm-learning-097"],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                         encoding="utf-8")

    print()
    print("=== HEADLINE ===")
    print(json.dumps(summary["headline"], indent=2))
    print()
    print(f"[mixed-bag] full report -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
