"""Doc-verifier eval — F1 + JSON validity on the held-out 50.

Runs a candidate adapter against `data/eval/doc_verifier_holdout.reshaped.jsonl`
and emits scores.

Usage:

    .venv-gpu/Scripts/python.exe scripts/eval/eval_doc_verifier.py \\
        --candidate scrubster/dr-stein-stage25-qwen15-doc-verifier-r8 \\
        --base Qwen/Qwen2.5-1.5B-Instruct \\
        --holdout data/eval/doc_verifier_holdout.reshaped.jsonl \\
        --out experiments/runs/stage25_qwen15_doc_verifier_r8/eval/doc_verifier.json

Metrics:
- f1_macro (verified / refuted / unknown — 3-class)
- accuracy
- json_validity_rate (does the model emit a parseable JSON object?)
- per-class precision/recall
- confusion matrix
- evidence_tier (T1 with sample size declared per slm-learning-071)

Promotion threshold per benchmarks/README.md:
    f1_macro >= 0.85, json_validity_rate >= 0.90 — staging eligible

Decision refs: slm-learning-051 (candidate-only), slm-learning-071
(evidence tier).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def parse_json_response(text: str) -> dict | None:
    """Extract the first JSON object from a response. Tolerates leading/
    trailing prose."""
    if not text:
        return None
    s = text.strip()
    # Strip code fences if present
    s = re.sub(r"^```(?:json)?\s*\n?", "", s)
    s = re.sub(r"\n?```\s*$", "", s)
    # Find first {...} block
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return None


def load_holdout(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def gold_label(row: dict) -> str | None:
    """Extract gold status from the trainer-reshaped row."""
    cmd = row.get("command", "")
    if not isinstance(cmd, str):
        return None
    parsed = parse_json_response(cmd)
    if not parsed:
        return None
    s = parsed.get("status")
    return s if s in {"verified", "refuted", "unknown"} else None


def run_inference(rows: list[dict], base_model: str, candidate: str | None,
                  device: str = "cuda", max_new_tokens: int = 200,
                  temperature: float = 0.0) -> list[dict]:
    """Heavy import inside this function so --help is fast."""
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    print(f"[eval] loading base {base_model} ...")
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.bfloat16,
        device_map=device if device != "cpu" else "cpu",
    )

    if candidate:
        from peft import PeftModel
        print(f"[eval] loading adapter {candidate} ...")
        model = PeftModel.from_pretrained(model, candidate)

    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    results = []
    for i, row in enumerate(rows):
        instr = row.get("instruction", "")
        sys_prompt = row.get("system_prompt", "")
        msgs = []
        if sys_prompt:
            msgs.append({"role": "system", "content": sys_prompt})
        msgs.append({"role": "user", "content": instr})
        prompt = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0.0,
                pad_token_id=tokenizer.pad_token_id,
            )
        gen = tokenizer.decode(output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        results.append({"row_index": i, "response": gen.strip()})
        if (i + 1) % 10 == 0:
            print(f"[eval] {i+1}/{len(rows)} done")
    return results


def score(holdout: list[dict], inferences: list[dict]) -> dict:
    classes = ["verified", "refuted", "unknown"]
    by_class_correct: Counter[str] = Counter()
    by_class_total: Counter[str] = Counter()
    by_pred_class: Counter[str] = Counter()
    confusion: dict[str, Counter[str]] = defaultdict(Counter)

    json_valid = 0
    n_with_gold = 0
    n_correct = 0

    for row, inf in zip(holdout, inferences):
        gold = gold_label(row)
        if gold is None:
            continue
        n_with_gold += 1
        by_class_total[gold] += 1

        parsed = parse_json_response(inf.get("response", ""))
        if parsed is not None:
            json_valid += 1
            pred = parsed.get("status", "")
            if pred not in classes:
                pred = "unknown"
        else:
            pred = "unknown"

        by_pred_class[pred] += 1
        confusion[gold][pred] += 1
        if pred == gold:
            n_correct += 1
            by_class_correct[gold] += 1

    # Per-class precision/recall, then macro F1.
    precisions: dict[str, float] = {}
    recalls: dict[str, float] = {}
    f1s: dict[str, float] = {}
    for c in classes:
        tp = by_class_correct[c]
        fp = by_pred_class[c] - tp
        fn = by_class_total[c] - tp
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        precisions[c] = round(prec, 3)
        recalls[c] = round(rec, 3)
        f1s[c] = round(f1, 3)

    f1_macro = round(sum(f1s.values()) / len(classes), 3)
    accuracy = round(n_correct / n_with_gold, 3) if n_with_gold else 0.0
    json_validity_rate = round(json_valid / len(holdout), 3) if holdout else 0.0

    return {
        "n_holdout": len(holdout),
        "n_with_gold": n_with_gold,
        "f1_macro": f1_macro,
        "accuracy": accuracy,
        "json_validity_rate": json_validity_rate,
        "per_class_precision": precisions,
        "per_class_recall": recalls,
        "per_class_f1": f1s,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=str, default=None,
                        help="HF Hub adapter id or local path; None = bare base")
    parser.add_argument("--base", type=str, default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--holdout", type=Path,
                        default=ROOT / "data" / "eval" / "doc_verifier_holdout.reshaped.jsonl")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-new-tokens", type=int, default=200)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=None,
                        help="Run only the first N rows (for smoke test)")
    args = parser.parse_args()

    if not args.holdout.exists():
        print(f"ERROR: holdout {args.holdout} not found")
        return 2

    rows = load_holdout(args.holdout)
    if args.limit:
        rows = rows[:args.limit]
    print(f"[eval] {len(rows)} holdout rows; candidate={args.candidate or '(bare base)'}")

    inferences = run_inference(rows, args.base, args.candidate,
                               device=args.device,
                               max_new_tokens=args.max_new_tokens,
                               temperature=args.temperature)
    metrics = score(rows, inferences)

    summary = {
        "schema_v": 1,
        "benchmark": "doc_verifier",
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "candidate": args.candidate or "(bare base)",
        "base": args.base,
        "holdout_path": str(args.holdout),
        "metrics": metrics,
        "evidence_tier": "T1",
        "decision_refs": ["slm-learning-051", "slm-learning-071"],
        "promotion_threshold": {"f1_macro": 0.85, "json_validity_rate": 0.90},
        "promotion_eligible": (
            metrics["f1_macro"] >= 0.85 and metrics["json_validity_rate"] >= 0.90
        ),
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"[eval] wrote {args.out}")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
