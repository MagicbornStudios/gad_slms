"""Constitution-impact arm C eval — does the soul prompt move a measurable needle?

Per decision `slm-learning-060`. Take the existing v2 CLI checkpoint
and evaluate it on `promptfoo-gad-tools.yaml` (the 30-case GAD-tools
suite) with vs without a Dr. Stein soul-injected system prompt at
INFERENCE time. No retraining.

If C delta ≥ 5pp: promote arm B (training with soul prompt) to a real
phase 05 candidate.
If C delta < 2pp: keep soul as prompt-only forever (consistent with
`slm-learning-047`).
Between 2 and 5: inconclusive at this n; widen the eval set first.

Usage:

    .venv-gpu/Scripts/python.exe scripts/eval/constitution_arm_c.py \\
        --candidate scrubster/dr-stein-stage25-qwen15-instruct-v2 \\
        --base Qwen/Qwen2.5-1.5B-Instruct \\
        --eval-set promptfoo-gad-tools.yaml \\
        --out experiments/runs/stage25_qwen15_instruct_v2/eval/constitution_arm_c.json

Decision refs: slm-learning-047, slm-learning-060, slm-learning-071.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


# Two system prompts: bare (no soul) vs soul-aligned (Dr. Stein constitution
# excerpt — short enough to fit alongside the user instruction).
BARE_SYSTEM = (
    "You are an assistant. Translate the user's request into a single gad "
    "CLI command. Output only the command on one line."
)

SOUL_SYSTEM = (
    "You are Dr. Stein, the GAD model-improvement scientist. You inherit "
    "the common dream: improve the GAD ecosystem through evidence, never "
    "self-flattery. Translate the user's request into a single gad CLI "
    "command. Output only the command on one line. If the command is "
    "uncertain, prefer the smallest reversible action."
)


def load_promptfoo_cases(yaml_path: Path) -> list[dict]:
    """Light yaml read to extract the (input, expected) pairs."""
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml not installed; pip install pyyaml")
        sys.exit(2)
    if not yaml_path.exists():
        print(f"ERROR: {yaml_path} not found")
        sys.exit(2)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    cases: list[dict] = []
    # promptfoo schema: tests: [{vars: {input: "..."}, assert: [{value: "..."}]}]
    for t in data.get("tests", []):
        vars_ = t.get("vars", {})
        instruction = vars_.get("input") or vars_.get("instruction") or ""
        asserts = t.get("assert", [])
        expected = ""
        for a in asserts:
            if a.get("type") == "contains":
                expected = a.get("value", "")
                break
        cases.append({"instruction": instruction, "expected_contains": expected})
    return cases


def run_arm(cases: list[dict], system_prompt: str, base: str,
            candidate: str | None, device: str = "cuda") -> list[dict]:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    print(f"[arm] loading base {base} (system_prompt[:40] = {system_prompt[:40]!r}...) ...")
    tokenizer = AutoTokenizer.from_pretrained(base)
    model = AutoModelForCausalLM.from_pretrained(
        base, torch_dtype=torch.bfloat16,
        device_map=device if device != "cpu" else "cpu",
    )
    if candidate:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, candidate)

    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    results = []
    for i, c in enumerate(cases):
        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": c["instruction"]},
        ]
        prompt = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(
                **inputs, max_new_tokens=80, do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        gen = tokenizer.decode(output[0][inputs.input_ids.shape[1]:],
                                skip_special_tokens=True).strip()
        passed = c["expected_contains"] in gen if c["expected_contains"] else False
        results.append({
            "i": i,
            "instruction": c["instruction"],
            "expected_contains": c["expected_contains"],
            "response": gen,
            "passed": passed,
        })
        if (i + 1) % 5 == 0:
            print(f"[arm] {i+1}/{len(cases)}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=str,
                        default="scrubster/dr-stein-stage25-qwen15-instruct-v2")
    parser.add_argument("--base", type=str, default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--eval-set", type=Path,
                        default=ROOT / "promptfoo-gad-tools.yaml")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    cases = load_promptfoo_cases(args.eval_set)
    print(f"[arm-c] loaded {len(cases)} cases from {args.eval_set.name}")

    results_bare = run_arm(cases, BARE_SYSTEM, args.base, args.candidate, args.device)
    results_soul = run_arm(cases, SOUL_SYSTEM, args.base, args.candidate, args.device)

    bare_passed = sum(1 for r in results_bare if r["passed"])
    soul_passed = sum(1 for r in results_soul if r["passed"])
    delta_pp = round(((soul_passed - bare_passed) / len(cases)) * 100, 1) if cases else 0.0

    if delta_pp >= 5:
        verdict = "promote_arm_b"
    elif delta_pp <= -5:
        verdict = "soul_hurts"
    elif abs(delta_pp) < 2:
        verdict = "no_signal_keep_prompt_only"
    else:
        verdict = "inconclusive_widen_eval"

    summary = {
        "schema_v": 1,
        "benchmark": "constitution_arm_c",
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "candidate": args.candidate,
        "base": args.base,
        "n_cases": len(cases),
        "bare_score": f"{bare_passed}/{len(cases)}",
        "soul_score": f"{soul_passed}/{len(cases)}",
        "delta_pp": delta_pp,
        "verdict": verdict,
        "evidence_tier": "T1",
        "decision_refs": ["slm-learning-047", "slm-learning-060", "slm-learning-071"],
        "next_step": {
            "promote_arm_b": "Worth running arm B (full SFT with soul-injected prompt). ~1 GPU-day.",
            "soul_hurts": "Soul prompt regresses output. Investigate which cases fail. Soul stays as concern doc, not training signal.",
            "no_signal_keep_prompt_only": "Soul stays prompt-only forever per slm-learning-047.",
            "inconclusive_widen_eval": "Run on a 200-case eval set before deciding.",
        }[verdict],
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
