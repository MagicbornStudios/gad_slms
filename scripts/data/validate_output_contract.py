"""Validate that a dataset's targets match their declared output contract.

Per slm-learning-108: every dataset row carries a `target_contract`
(or `target_format`, treated as alias). Strict contracts must
schema-validate; loose contracts get heuristic checks.

Blocks training (exit 2) if strict_contract_match < threshold.

Usage:
    .venv/Scripts/python.exe scripts/data/validate_output_contract.py \\
        --dataset data/processed/ocr-variants-2026-05-08/ocr_function_normalized/rows.jsonl \\
        --strict-min 0.95

    # infer mode for legacy datasets without `target_contract`:
    .venv/Scripts/python.exe scripts/data/validate_output_contract.py \\
        --dataset data/tool_use_pairs.jsonl --infer

Reports:
    reports/data_contracts/<dataset>_contract_report.json

Decision refs: slm-learning-108, 111.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


# Strict contracts must schema-validate.
STRICT_CONTRACTS = {
    "gad_cli_command",
    "tool_action_json",
    "code_completion",
    "function_definition",
    "full_function_definition",  # alias from coding_sft.md
    "patch_diff",
    "classification_label",
    "full_script",
    "competitive_program",  # alias from coding_sft.md
}

LOOSE_CONTRACTS = {
    "natural_language",
    "email_draft",
}


# --- per-contract validators ----------------------------------------

GAD_CLI_RE = re.compile(r"^\s*gad\s+\w[\w-]*", re.MULTILINE)


def validate_gad_cli_command(target: str) -> tuple[bool, str]:
    if not target.strip().startswith("gad "):
        return False, "doesn't start with 'gad '"
    if "\n" in target.strip():
        # multiline — could still be valid if it's `gad cmd \\\n  --flag`
        if not target.strip().endswith("\\"):
            # not a multi-line continuation
            lines = [l for l in target.split("\n") if l.strip()]
            if len(lines) > 1 and not all(l.strip().startswith("gad ") or l.lstrip().startswith("--") for l in lines):
                return False, "looks like multiple commands"
    return True, "ok"


def validate_tool_action_json(target: str) -> tuple[bool, str]:
    try:
        obj = json.loads(target)
    except json.JSONDecodeError as e:
        return False, f"json parse failed: {e}"
    if not isinstance(obj, dict):
        return False, "not a dict"
    if "tool" not in obj or not isinstance(obj.get("tool"), str):
        return False, "missing 'tool' string"
    if "args" not in obj or not isinstance(obj.get("args"), dict):
        return False, "missing 'args' dict"
    return True, "ok"


def validate_function_definition(target: str) -> tuple[bool, str]:
    code = target.strip()
    if not code:
        return False, "empty"
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"syntax error: {e.msg}"
    has_def = any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  for n in ast.walk(tree))
    if not has_def:
        return False, "no def found"
    return True, "ok"


def validate_code_completion(target: str) -> tuple[bool, str]:
    # Body-only — should NOT have a def at column 0; should have
    # SOME indentation.
    code = target.rstrip("\n")
    if not code.strip():
        return False, "empty"
    first_line = next((l for l in code.split("\n") if l.strip()), "")
    if first_line.lstrip() != first_line and first_line.lstrip().startswith("def "):
        # def is indented = nested def OK
        return True, "ok (nested def)"
    if first_line.startswith("def "):
        return False, "starts with def (use function_definition contract)"
    if not first_line.startswith((" ", "\t")):
        return False, "first line at column 0 (use function_definition or full_script)"
    return True, "ok"


def validate_full_script(target: str) -> tuple[bool, str]:
    try:
        ast.parse(target)
        return True, "ok"
    except SyntaxError as e:
        return False, f"syntax error: {e.msg}"


def validate_patch_diff(target: str) -> tuple[bool, str]:
    if not re.search(r"^---\s+", target, re.MULTILINE):
        return False, "missing '--- ' line"
    if not re.search(r"^\+\+\+\s+", target, re.MULTILINE):
        return False, "missing '+++ ' line"
    if not re.search(r"^@@\s+", target, re.MULTILINE):
        return False, "missing '@@ ' hunk header"
    return True, "ok"


def validate_classification_label(target: str) -> tuple[bool, str]:
    s = target.strip()
    if not s:
        return False, "empty"
    if "\n" in s:
        return False, "multi-line label"
    if len(s) > 100:
        return False, "label too long (>100 chars)"
    return True, "ok"


VALIDATORS = {
    "gad_cli_command": validate_gad_cli_command,
    "tool_action_json": validate_tool_action_json,
    "function_definition": validate_function_definition,
    "full_function_definition": validate_function_definition,  # alias from coding_sft.md
    "code_completion": validate_code_completion,
    "full_script": validate_full_script,
    "competitive_program": validate_full_script,  # alias from coding_sft.md
    "patch_diff": validate_patch_diff,
    "classification_label": validate_classification_label,
}


# --- contract inference (for legacy datasets) -----------------------

def infer_contract(target: str) -> str:
    """Best-effort contract guess for a target string."""
    s = target.strip()
    if not s:
        return "unknown"
    if s.startswith("gad ") or re.match(r"^gad\s", s):
        return "gad_cli_command"
    if (s.startswith("{") and s.rstrip().endswith("}")):
        try:
            obj = json.loads(s)
            if isinstance(obj, dict) and "tool" in obj:
                return "tool_action_json"
        except Exception:
            pass
    if s.startswith("```"):
        # Could be markdown-wrapped code; peek inside
        m = re.search(r"```(?:python)?\s*\n?(.*?)\n?```", s, re.DOTALL)
        if m:
            s = m.group(1).strip()
    if s.startswith("def ") or s.startswith("async def "):
        return "function_definition"
    if re.match(r"^---\s+.*\n\+\+\+\s+", s, re.MULTILINE):
        return "patch_diff"
    if "input(" in s and "print(" in s:
        return "full_script"
    if s.startswith((" ", "\t")) and "return" in s:
        return "code_completion"
    if "\n" not in s and len(s) < 100:
        return "classification_label"
    return "natural_language"


# --- main driver ----------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True, help="JSONL dataset path")
    p.add_argument("--strict-min", type=float, default=0.95,
                   help="Strict-contract match threshold (block training if below)")
    p.add_argument("--sample", type=int, default=200,
                   help="Sample N rows; 0 = all")
    p.add_argument("--infer", action="store_true",
                   help="Infer contract per row when not declared")
    p.add_argument("--out-json", default=None,
                   help="Override output report path")
    p.add_argument("--force-train", action="store_true",
                   help="Override block; logs exception")
    args = p.parse_args()

    ds_path = Path(args.dataset)
    if not ds_path.is_absolute():
        ds_path = REPO_ROOT / ds_path
    if not ds_path.exists():
        print(f"ERROR: dataset not found: {ds_path}", file=sys.stderr)
        sys.exit(2)

    rows = []
    with ds_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    print(f"[validate] loaded {len(rows)} rows from {ds_path.name}")

    if args.sample and args.sample < len(rows):
        rows = rows[:args.sample]
        print(f"[validate] sampled {len(rows)} rows")

    declared_count = Counter()
    inferred_count = Counter()
    pass_count = Counter()
    fail_count = Counter()
    fail_examples: dict[str, list[dict]] = {}

    for r in rows:
        target = r.get("target") or r.get("output") or r.get("response") or r.get("command") or ""
        if not isinstance(target, str):
            target = json.dumps(target) if target is not None else ""
        contract = (r.get("target_contract") or
                    r.get("target_format") or
                    None)
        if contract is None and args.infer:
            contract = infer_contract(target)
            inferred_count[contract] += 1
        elif contract is None:
            inferred_count["unknown"] += 1
            continue
        else:
            declared_count[contract] += 1

        if contract in VALIDATORS:
            ok, reason = VALIDATORS[contract](target)
        elif contract in LOOSE_CONTRACTS:
            ok, reason = bool(target.strip()), "loose contract: not empty"
        else:
            ok, reason = False, f"unknown contract {contract!r}"

        if ok:
            pass_count[contract] += 1
        else:
            fail_count[contract] += 1
            fail_examples.setdefault(contract, []).append({
                "id": r.get("id"),
                "target_preview": target[:200],
                "reason": reason,
            })

    strict_pass = sum(pass_count[c] for c in STRICT_CONTRACTS)
    strict_total = sum(pass_count[c] + fail_count[c]
                       for c in STRICT_CONTRACTS)
    strict_rate = strict_pass / max(1, strict_total)

    report = {
        "dataset": str(ds_path.relative_to(REPO_ROOT)),
        "n_sampled": len(rows),
        "declared_contracts": dict(declared_count),
        "inferred_contracts": dict(inferred_count),
        "pass_by_contract": dict(pass_count),
        "fail_by_contract": dict(fail_count),
        "strict_pass": strict_pass,
        "strict_total": strict_total,
        "strict_match_rate": round(strict_rate, 4),
        "strict_min_threshold": args.strict_min,
        "blocks_training": strict_rate < args.strict_min,
        "examples": {c: ex[:5] for c, ex in fail_examples.items()},
        "force_train": args.force_train,
        "decision_refs": ["slm-learning-108", "slm-learning-111"],
    }

    out_path = (Path(args.out_json) if args.out_json
                else REPO_ROOT / "reports" / "data_contracts" /
                     f"{ds_path.stem}_contract_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[validate] wrote {out_path.relative_to(REPO_ROOT)}")
    print(f"[validate] strict-contract match: {strict_rate:.1%} "
          f"({strict_pass}/{strict_total})")

    if report["blocks_training"] and not args.force_train:
        print(f"[validate] BLOCKS TRAINING — strict rate {strict_rate:.1%} "
              f"< {args.strict_min:.0%}")
        sys.exit(2)
    if args.force_train and report["blocks_training"]:
        print("[validate] force-train override active; logging exception")

    print(f"[validate] PASS")


if __name__ == "__main__":
    main()
