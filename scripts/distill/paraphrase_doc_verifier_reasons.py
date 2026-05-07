"""Second-stage paraphrase augmentation for the doc-verifier corpus.

Why
---
Stage 1 (`augment_doc_verifier_unknown.py`) deterministically synthesizes
unknown-class examples by mutating verified rows' claim paths. Stage 1
is fast, free, and grounded in the real codebase — but every synthesized
row reuses the SAME reason string template:

    "basename {base!r} matches elsewhere; literal path {claim!r} not found"

The model can memorize that exact string and call it a day, which won't
generalize to real unknown reasons that show up in inference.

Stage 2 (this script) varies the surface form of the reason field by
asking a Claude subagent (haiku-4-5 default per slm-learning-019) to
paraphrase the reason text 3-5 different ways per row. Status, claim,
and evidence stay locked — only the reason changes.

Two-step orchestration
----------------------

Step A. Emit a paraphrase-prompts manifest (JSONL, one prompt per row):

    .venv/Scripts/python.exe scripts/distill/paraphrase_doc_verifier_reasons.py \\
        emit \\
        --in data/eval/doc_verifier_train.augmented.jsonl \\
        --out data/distilled/doc_verifier_paraphrase_prompts.jsonl \\
        --variants 3 \\
        --filter-status unknown

Step B. The orchestrating Claude session (you, reading this) walks the
manifest, calls the Agent tool with subagent_type=general-purpose and
model=claude-haiku-4-5 for each prompt, captures the response, and
writes back the responses to a sibling responses.jsonl.

Step C. Materialize the augmented corpus from the responses:

    .venv/Scripts/python.exe scripts/distill/paraphrase_doc_verifier_reasons.py \\
        materialize \\
        --in data/eval/doc_verifier_train.augmented.jsonl \\
        --responses data/distilled/doc_verifier_paraphrase_responses.jsonl \\
        --out data/eval/doc_verifier_train.augmented.paraphrased.jsonl

This split lets the Claude session (which has the Agent tool) drive
the LLM calls while keeping the data plumbing in a single Python file.

Decision refs: slm-learning-019 (subagent dispatch, not API),
slm-learning-090 (doc-verifier r=16), slm-learning-091 (scaling
decisions framework).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

PARAPHRASE_PROMPT_TEMPLATE = """You are helping augment training data for a documentation-verification \
classifier. The classifier outputs status=unknown when a literal path doesn't \
exist but the basename matches elsewhere in the codebase.

Original reason text:
  "{reason}"

Rewrite this reason in {n_variants} DIFFERENT phrasings. Each variant must:
  1. Convey the same meaning (basename matches, literal path missing)
  2. Be a single line of plain text (no JSON, no markdown)
  3. Vary surface form: word order, vocabulary, punctuation
  4. Stay under 200 characters
  5. Reference the basename {basename!r} where natural

Output ONE variant per line. Do not number them. Do not add commentary."""


def load_pairs(path: Path) -> list[dict]:
    rows: list[dict] = []
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


def basename(claim: str) -> str:
    return claim.replace("\\", "/").rstrip("/").split("/")[-1]


def cmd_emit(args: argparse.Namespace) -> int:
    rows = load_pairs(args.inp)
    candidates: list[dict] = []
    for i, r in enumerate(rows):
        out = r.get("output", {})
        if args.filter_status and out.get("status") != args.filter_status:
            continue
        if not out.get("reason"):
            continue
        candidates.append({"row_index": i, "row": r})

    if args.limit:
        candidates = candidates[:args.limit]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for c in candidates:
            r = c["row"]
            inp_dict = r.get("input", {})
            out_dict = r.get("output", {})
            claim = inp_dict.get("claim", "")
            reason = out_dict.get("reason", "")
            prompt = PARAPHRASE_PROMPT_TEMPLATE.format(
                reason=reason,
                n_variants=args.variants,
                basename=basename(claim),
            )
            envelope = {
                "row_index": c["row_index"],
                "claim": claim,
                "status": out_dict.get("status"),
                "original_reason": reason,
                "n_variants_requested": args.variants,
                "agent_subtype": "general-purpose",
                "model_hint": "claude-haiku-4-5",
                "prompt": prompt,
            }
            f.write(json.dumps(envelope, ensure_ascii=False) + "\n")

    print(json.dumps({
        "status": "ok",
        "step": "emit",
        "rows_in": len(rows),
        "rows_to_paraphrase": len(candidates),
        "out": str(args.out),
        "variants_per_row": args.variants,
    }, indent=2))
    return 0


def parse_response_variants(response_text: str) -> list[str]:
    """Each variant is one line. Strip empty + commentary lines."""
    lines = []
    for line in response_text.splitlines():
        s = line.strip()
        if not s:
            continue
        # Skip lines that look like meta-commentary
        if s.lower().startswith(("here are", "here's", "below are",
                                  "rewritten", "variant ")):
            continue
        # Strip optional leading "1. ", "- ", "* " etc.
        s = s.lstrip("0123456789.-* )")
        s = s.strip().strip('"').strip("'")
        if s:
            lines.append(s)
    return lines


def cmd_materialize(args: argparse.Namespace) -> int:
    rows = load_pairs(args.inp)
    responses = load_pairs(args.responses)
    by_index: dict[int, list[str]] = {}

    for resp in responses:
        idx = resp.get("row_index")
        text = resp.get("response_text") or resp.get("response", "")
        variants = parse_response_variants(text)
        if not variants:
            continue
        by_index.setdefault(idx, []).extend(variants)

    augmented = list(rows)  # keep originals
    new_rows: list[dict] = []

    for idx, variants in by_index.items():
        if idx >= len(rows):
            continue
        base_row = rows[idx]
        for v in variants:
            new_row = json.loads(json.dumps(base_row))  # deep copy
            new_row["output"]["reason"] = v
            prov = new_row.setdefault("provenance", {})
            prov["data_tier"] = "synthetic_paraphrased"
            prov.setdefault("synthesis", {})["paraphrase_via"] = (
                "claude-haiku-4-5"
            )
            prov["synthesis"]["source_row_index"] = idx
            prov["timestamp"] = dt.datetime.now(dt.timezone.utc).isoformat()
            new_rows.append(new_row)

    augmented.extend(new_rows)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r in augmented:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(json.dumps({
        "status": "ok",
        "step": "materialize",
        "rows_in": len(rows),
        "responses_processed": len(responses),
        "new_paraphrased_rows": len(new_rows),
        "ending_total": len(augmented),
        "out": str(args.out),
    }, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="step", required=True)

    p_emit = sub.add_parser("emit", help="Emit prompts JSONL for Claude "
                                          "session to ingest")
    p_emit.add_argument("--in", "-i", dest="inp", type=Path, required=True)
    p_emit.add_argument("--out", "-o", type=Path, required=True)
    p_emit.add_argument("--variants", type=int, default=3,
                        help="Variants per row (default 3)")
    p_emit.add_argument("--filter-status", type=str, default="unknown",
                        help="Only paraphrase rows with this status. "
                             "Default unknown (the underrepresented class).")
    p_emit.add_argument("--limit", type=int, default=None,
                        help="Cap rows for cost-control smoke runs")
    p_emit.set_defaults(func=cmd_emit)

    p_mat = sub.add_parser("materialize", help="Ingest responses and "
                                                "produce paraphrased corpus")
    p_mat.add_argument("--in", "-i", dest="inp", type=Path, required=True,
                       help="Same as --in passed to emit step")
    p_mat.add_argument("--responses", type=Path, required=True,
                       help="JSONL: {row_index, response_text}")
    p_mat.add_argument("--out", "-o", type=Path, required=True)
    p_mat.set_defaults(func=cmd_materialize)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
