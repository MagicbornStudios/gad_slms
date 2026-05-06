"""Reshape doc-verifier pairs from {input,output,provenance} dict shape
to the trainer's {instruction, command} shape.

The bootstrapped corpus uses the doc-verifier-output schema (claim +
status + evidence). The trainer expects single string instruction +
single string response. This script bridges the two.

Usage:

    .venv/Scripts/python.exe scripts/eval/reshape_doc_verifier_for_train.py \\
        --in data/eval/doc_verifier_train.jsonl \\
        --out data/eval/doc_verifier_train.reshaped.jsonl

    .venv/Scripts/python.exe scripts/eval/reshape_doc_verifier_for_train.py \\
        --in data/eval/doc_verifier_holdout.jsonl \\
        --out data/eval/doc_verifier_holdout.reshaped.jsonl

Reshape format:

    instruction = (
        f"Verify the following claim against the live codebase.\\n"
        f"Doc path: {doc_path}\\n"
        f"Claim category: {claim_category}\\n"
        f"Claim: {claim}\\n"
        f"Respond with: status (verified|refuted|unknown), evidence list, brief reason."
    )
    command = json.dumps({
        "status": ...,
        "evidence": [...],
        "reason": "..."
    })

This keeps the structured-output discipline (which is what the
gad-doc-verifier agent emits) but in single-string JSON form.

Decision refs: slm-learning-051 (candidate-only training),
slm-learning-046 (Dr. Stein output schema discipline).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


SYSTEM_PROMPT = (
    "You are gad-doc-verifier. Verify the claim against the live "
    "codebase and emit a JSON object with status (verified|refuted|"
    "unknown), evidence (list of file:line citations), and a brief "
    "reason. Output only the JSON object on one line."
)


def reshape_one(row: dict) -> dict | None:
    inp = row.get("input")
    out = row.get("output")
    if not isinstance(inp, dict) or not isinstance(out, dict):
        return None
    doc_path = inp.get("doc_path", "")
    claim = inp.get("claim", "")
    cat = inp.get("claim_category", "")
    if not claim:
        return None

    instruction = (
        f"Verify the following claim against the live codebase.\n"
        f"Doc path: {doc_path}\n"
        f"Claim category: {cat}\n"
        f"Claim: {claim}\n"
        f"Respond with the JSON object."
    )
    command = json.dumps({
        "status": out.get("status", "unknown"),
        "evidence": out.get("evidence", []),
        "reason": out.get("reason", ""),
    }, ensure_ascii=False)

    return {
        "instruction": instruction,
        "command": command,
        "system_prompt": SYSTEM_PROMPT,
        "provenance": row.get("provenance", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", "-i", dest="inp", type=Path, required=True)
    parser.add_argument("--out", "-o", dest="out", type=Path, required=True)
    args = parser.parse_args()

    if not args.inp.exists():
        print(f"ERROR: {args.inp} not found")
        return 2

    rows_in = []
    with args.inp.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows_in.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    rows_out = []
    skipped = 0
    for r in rows_in:
        reshaped = reshape_one(r)
        if reshaped is None:
            skipped += 1
            continue
        rows_out.append(reshaped)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r in rows_out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[reshape] {args.inp.name}: {len(rows_in)} -> {len(rows_out)} (skipped {skipped})")
    print(f"[reshape] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
