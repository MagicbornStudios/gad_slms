"""Classify tooluse-eval failures into a tooluse-specific taxonomy.

Per slm-learning-108 + slm-learning-111. Different from
classify_humaneval_failures.py — this one targets gad_tools eval
output where the contract is gad_cli_command or tool_action_json.

Buckets:
  natural_language_instead_of_command
  wrong_projectid
  wrong_gad_subcommand
  missing_required_arg
  invalid_json
  unrenderable_tool_action
  unsafe_action
  multi_action_not_supported
  ambiguous_passes_a_check_but_wrong
  unknown

Usage:
    .venv/Scripts/python.exe scripts/eval/classify_tooluse_failures.py \\
        --results tmp/diag-2026-05-08/gad_tools_chat_n30.json \\
        --out reports/diagnostics/tooluse_v2_failure_taxonomy.md
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


BUCKETS = [
    "natural_language_instead_of_command",
    "wrong_projectid",
    "wrong_gad_subcommand",
    "missing_required_arg",
    "invalid_json",
    "unrenderable_tool_action",
    "unsafe_action",
    "multi_action_not_supported",
    "ambiguous_passes_check_but_wrong",
    "unknown",
]


def classify(case: dict) -> tuple[str, str]:
    output: str = case.get("completion_full") or case.get("completion_preview") or ""
    judge: str = case.get("judge_reason") or ""
    out_lc = output.lower().strip()

    # natural_language_instead_of_command: starts with prose markers
    if out_lc.startswith(("note:", "i'll", "here", "the user", "to ", "you can",
                            "first,", "let me", "okay", "sure")):
        if "gad " not in out_lc[:80]:
            return "natural_language_instead_of_command", out_lc[:80]

    # invalid_json: starts with `{` but doesn't parse
    if out_lc.startswith("{"):
        try:
            json.loads(output)
        except json.JSONDecodeError as e:
            return "invalid_json", str(e)[:80]
        # JSON parsed; could be unrenderable tool_action
        try:
            obj = json.loads(output)
            if isinstance(obj, dict):
                if "tool" not in obj or "args" not in obj:
                    return "unrenderable_tool_action", "missing tool/args"

        except Exception:
            pass

    # multi_action: multiple gad commands
    gad_lines = [l for l in output.split("\n") if l.strip().startswith("gad ")]
    if len(gad_lines) > 1:
        return "multi_action_not_supported", f"{len(gad_lines)} gad commands"

    # If output starts with `gad ` we can sub-classify:
    if out_lc.startswith("gad "):
        # missing projectid? (check if user instruction implied a project)
        if "--projectid" not in output:
            return "missing_required_arg", "no --projectid"
        # wrong subcommand: would need ground-truth comparison; flag if
        # the icontains assertion fails despite starting with `gad `
        if "icontains" in judge and "miss" in judge:
            return "wrong_gad_subcommand", judge[:120]
        # If the judge passed but we know the answer is incomplete:
        if "ok" in judge.lower():
            return "ambiguous_passes_check_but_wrong", "passed icontains but content may be wrong"
        return "wrong_gad_subcommand", "judge failed despite gad prefix"

    return "unknown", judge[:120]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True)
    p.add_argument("--out", default="reports/diagnostics/tooluse_failure_taxonomy.md")
    args = p.parse_args()

    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    fails = [r for r in data["results"] if not r.get("passed", False)]
    passes = [r for r in data["results"] if r.get("passed", False)]

    counts = Counter()
    examples: dict[str, list[dict]] = {}
    for case in fails:
        bucket, reason = classify(case)
        counts[bucket] += 1
        examples.setdefault(bucket, []).append({
            "id": case.get("id"),
            "reason": reason,
            "completion_preview": (case.get("completion_full") or
                                      case.get("completion_preview") or "")[:200],
        })

    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(f"# Tooluse failure taxonomy")
    lines.append("")
    lines.append(f"Source: `{args.results}`")
    lines.append(f"Adapter: `{data.get('adapter_id', 'unknown')}`")
    lines.append(f"Score: {data.get('passed')}/{data.get('n')} ({data.get('score', 0):.1%})")
    lines.append(f"Failures: {len(fails)}, Passes: {len(passes)}")
    lines.append("")
    lines.append("## Failure counts by bucket")
    lines.append("")
    lines.append("| Bucket | Count |")
    lines.append("|---|---|")
    for b in BUCKETS:
        lines.append(f"| {b} | {counts.get(b, 0)} |")
    lines.append(f"| **TOTAL** | **{len(fails)}** |")
    lines.append("")
    lines.append("## Sample failures")
    lines.append("")
    for b in BUCKETS:
        if not examples.get(b):
            continue
        lines.append(f"### {b}")
        lines.append("")
        for ex in examples[b][:3]:
            lines.append(f"**{ex['id']}** — {ex['reason']}")
            lines.append("")
            lines.append("```")
            lines.append(ex["completion_preview"])
            lines.append("```")
            lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[tooluse-taxonomy] wrote {out.relative_to(REPO_ROOT)}")
    print(f"[tooluse-taxonomy] counts: {dict(counts)}")


if __name__ == "__main__":
    main()
