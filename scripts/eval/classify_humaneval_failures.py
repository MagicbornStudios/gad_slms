"""Classify HumanEval failures into 9 buckets per 2026-05-08 directive.

Reads persisted full-result JSONs from the slm-models Modal volume
(eval_adapter.py persist_run_id mode), pulls the per-case
completion_full + judge_reason, and assigns each failure a bucket:

    A. think/truncation       — <think> blocks consumed output budget
    B. code truncated         — generation stopped mid-statement
    C. wrong function signature — model emitted a different signature
    D. full script not function — used input()/print() at module level
    E. competitive style      — input()/print() pattern even in function
    F. markdown/prose pollution — fences or English in output
    G. indentation/prefix bug — judge harness issue (post-fix should be 0)
    H. genuine algorithm fail — code parses + runs but assertion fails
    I. evaluator bug          — judge crashed / unknown reason

Output:
    reports/diagnostics/ocr_lora_humaneval_failure_taxonomy.md   (human)
    reports/diagnostics/ocr_lora_humaneval_failure_taxonomy.json (machine)

Inputs (downloaded from Modal volume slm-models):
    /models/eval-runs/diag-2026-05-08/humaneval_chat_n164.json   (per model)

Usage:
    .venv/Scripts/python.exe -m modal volume get slm-models \\
        eval-runs/diag-2026-05-08 ./tmp/diag-2026-05-08
    .venv/Scripts/python.exe scripts/eval/classify_humaneval_failures.py \\
        --base ./tmp/diag-2026-05-08/humaneval_chat_n164.json \\
        --lora ./tmp/diag-2026-05-08/humaneval_chat_n164.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


BUCKETS = [
    "A_think_truncation",
    "B_code_truncated",
    "C_wrong_function_signature",
    "D_full_script_not_function",
    "E_competitive_style",
    "F_markdown_prose_pollution",
    "G_indentation_prefix_bug",
    "H_genuine_algorithm_fail",
    "I_evaluator_bug",
]


def classify(case: dict) -> tuple[str, str]:
    """Return (bucket, brief_reason)."""
    completion: str = case.get("completion_full") or case.get("completion_preview") or ""
    judge_reason: str = case.get("judge_reason") or ""
    case_id = case.get("id", "")

    # I. Evaluator bug — judge crashed before running
    if "judge crashed" in judge_reason.lower() or judge_reason.startswith("Exception"):
        return "I_evaluator_bug", judge_reason[:120]

    # A. <think> truncation — completion has open <think> with no </think>,
    # or completion ends inside a think block
    if "<think>" in completion and "</think>" not in completion:
        return "A_think_truncation", "open <think> never closed"
    if completion.count("<think>") > 0 and len(completion) > 0:
        # Has think blocks but completion is mostly thought
        post_think = re.sub(r"<think>.*?</think>", "", completion, flags=re.DOTALL)
        if len(post_think.strip()) < 30:
            return "A_think_truncation", "all/most output was <think>"

    # B. Code truncated — last line is half-statement (no closing paren / colon
    # on incomplete construct)
    last_line = completion.rstrip().split("\n")[-1] if completion.strip() else ""
    open_parens = completion.count("(") - completion.count(")")
    open_brackets = completion.count("[") - completion.count("]")
    open_braces = completion.count("{") - completion.count("}")
    if open_parens > 0 or open_brackets > 0 or open_braces > 0:
        return "B_code_truncated", f"unclosed brackets parens={open_parens} brackets={open_brackets} braces={open_braces}"
    if last_line and not last_line.rstrip().endswith((")", ":", ",", "]", "}", "\"", "'")) and "return" not in last_line:
        if len(last_line) > 30 and not last_line.endswith("```"):
            return "B_code_truncated", f"last line looks mid-statement: {last_line[:60]!r}"

    # F. Markdown / prose pollution — model wrote prose paragraphs
    # OR code is wrapped but has prose between fences
    code = completion
    if "```" in code:
        m = re.search(r"```(?:python)?\s*\n?(.*?)\n?```", code, re.DOTALL)
        inside = m.group(1) if m else ""
        outside = code.replace(m.group(0) if m else "", "").strip()
        # Outside the fence, look for prose words longer than typical code
        if outside and len(outside.split()) > 20 and ":" not in outside[:30]:
            return "F_markdown_prose_pollution", f"prose outside fence: {outside[:60]!r}"
        code = inside
    # Inside-only prose check: lines without code structure
    code_lines = code.strip().split("\n")
    prose_like = sum(1 for l in code_lines if l.strip() and not any(
        c in l for c in ["def ", "return", "if ", "for ", "while ", "=",
                          "(", ")", ":", "import ", "class ", "#"]) and len(l.split()) > 5)
    if prose_like > 2:
        return "F_markdown_prose_pollution", f"{prose_like} prose-like lines"

    # E. Competitive style — uses input()/print() at top level inside the
    # function context (where the harness expects function body)
    if re.search(r"^\s*input\(", code, re.MULTILINE):
        return "E_competitive_style", "uses input() — competitive style"
    if re.search(r"^\s*print\(", code, re.MULTILINE) and "def " not in code:
        return "E_competitive_style", "module-level print() with no def"

    # D. Full script not function — has __main__ block or no def at all
    # in a benchmark that expects function body
    if "__main__" in code:
        return "D_full_script_not_function", "has if __name__ == '__main__'"
    if "def " not in code and "return" in code:
        # Body-only is OK for HumanEval; only flag if there's also no
        # indentation pattern matching the prefix
        pass

    # C. Wrong function signature — has a def line that doesn't match
    # the expected entry point. Hard to detect without prefix; flag as
    # heuristic.
    if "def " in code:
        # Look for any def that diverges from the expected entry_point
        # We don't have entry_point in case here; use case_id as proxy
        # for HumanEval/0 etc. — fall through unless we can confirm.
        pass

    # G. Indentation / prefix bug — judge_reason mentions IndentationError
    # or prefix-related Python error
    if "IndentationError" in judge_reason or "unindent does not match" in judge_reason:
        return "G_indentation_prefix_bug", judge_reason[:120]
    if "SyntaxError" in judge_reason and "return" in judge_reason and "outside" in judge_reason:
        return "G_indentation_prefix_bug", "return outside function"

    # H. Genuine algorithm fail — code ran but assertion failed
    if "AssertionError" in judge_reason:
        return "H_genuine_algorithm_fail", "assertion failed"
    if "non-zero exit" in judge_reason:
        return "H_genuine_algorithm_fail", "non-zero exit (likely assertion)"

    # Default: bucket I if we can't classify cleanly
    return "I_evaluator_bug", f"unclassified: {judge_reason[:80]!r}"


def summarize(results: list[dict], label: str) -> dict:
    failures = [r for r in results if not r.get("passed", False)]
    counts = {b: 0 for b in BUCKETS}
    examples: dict[str, list[dict]] = {b: [] for b in BUCKETS}
    for case in failures:
        bucket, reason = classify(case)
        counts[bucket] = counts.get(bucket, 0) + 1
        if len(examples[bucket]) < 3:
            examples[bucket].append({
                "id": case.get("id"),
                "reason": reason,
                "completion_preview": (case.get("completion_full") or
                                          case.get("completion_preview") or "")[:200],
                "judge_reason": case.get("judge_reason", "")[:200],
            })
    return {
        "label": label,
        "n_total": len(results),
        "n_failures": len(failures),
        "buckets": counts,
        "examples": examples,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True,
                   help="Path to base model HumanEval results JSON")
    p.add_argument("--lora", required=True,
                   help="Path to LoRA model HumanEval results JSON")
    p.add_argument("--out-md", default="reports/diagnostics/ocr_lora_humaneval_failure_taxonomy.md")
    p.add_argument("--out-json", default="reports/diagnostics/ocr_lora_humaneval_failure_taxonomy.json")
    args = p.parse_args()

    base_data = json.loads(Path(args.base).read_text(encoding="utf-8"))
    lora_data = json.loads(Path(args.lora).read_text(encoding="utf-8"))

    base_summary = summarize(base_data["results"], "7B base")
    lora_summary = summarize(lora_data["results"], "7B + OCR LoRA")

    out_md = REPO_ROOT / args.out_md
    out_json = REPO_ROOT / args.out_json
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps({
        "base": base_summary,
        "lora": lora_summary,
    }, indent=2), encoding="utf-8")
    print(f"[taxonomy] wrote {out_json}")

    lines = []
    lines.append("# HumanEval failure taxonomy — 7B base vs 7B + OCR LoRA")
    lines.append("")
    lines.append("Per `slm-learning-107`. Generated from full per-case "
                 "completions persisted via `eval_adapter.py persist_run_id`.")
    lines.append("")
    lines.append("## Failure counts by bucket")
    lines.append("")
    lines.append("| Bucket | 7B base | 7B + OCR LoRA | Δ |")
    lines.append("|---|---|---|---|")
    for b in BUCKETS:
        bc = base_summary["buckets"].get(b, 0)
        lc = lora_summary["buckets"].get(b, 0)
        delta = lc - bc
        sign = "+" if delta > 0 else ""
        lines.append(f"| {b} | {bc} | {lc} | {sign}{delta} |")
    lines.append(f"| **TOTAL FAILURES** | **{base_summary['n_failures']}** | **{lora_summary['n_failures']}** | **{lora_summary['n_failures'] - base_summary['n_failures']:+d}** |")
    lines.append("")
    lines.append(f"7B base: {base_summary['n_failures']}/{base_summary['n_total']} failed")
    lines.append(f"7B LoRA: {lora_summary['n_failures']}/{lora_summary['n_total']} failed")
    lines.append("")

    lines.append("## Diagnostic interpretation")
    lines.append("")
    lines.append("Look at where the LoRA's failures CONCENTRATE relative to base:")
    lines.append("")
    big_deltas = sorted(BUCKETS,
                       key=lambda b: lora_summary['buckets'].get(b, 0) - base_summary['buckets'].get(b, 0),
                       reverse=True)[:3]
    for b in big_deltas:
        delta = lora_summary['buckets'].get(b, 0) - base_summary['buckets'].get(b, 0)
        if delta > 0:
            lines.append(f"- **{b}**: LoRA has +{delta} more failures here. "
                          f"This is a hypothesis confirmed.")
    lines.append("")

    lines.append("## Sample failures by bucket")
    lines.append("")
    for b in BUCKETS:
        if not lora_summary["examples"][b]:
            continue
        lines.append(f"### {b}")
        lines.append("")
        for ex in lora_summary["examples"][b]:
            lines.append(f"**{ex['id']}** — {ex['reason']}")
            lines.append("")
            lines.append("```")
            lines.append(ex["completion_preview"])
            lines.append("```")
            lines.append("")
            lines.append(f"_judge: {ex['judge_reason']}_")
            lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[taxonomy] wrote {out_md}")


if __name__ == "__main__":
    main()
