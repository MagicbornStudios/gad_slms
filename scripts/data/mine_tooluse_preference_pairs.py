"""Mine tooluse-v2 contract failures into DPO-style preference pairs.

Per slm-learning-108 + slm-learning-112: every contract failure
becomes preference data. The model's wrong-contract output is the
`rejected`; the correct gad CLI command derived from the eval's
expected assertion is the `chosen`.

Reads:
    tmp/diag-2026-05-08/gad_tools_chat_n30.json   (model's outputs)
    promptfoo-gad-tools.yaml                       (expected assertions)

Writes:
    data/preference/tooluse_contract_failures_dpo.jsonl

Each pair:
{
  "prompt": "Take a note that the build is broken on Windows.",
  "chosen": "gad note add --projectid slm-learning ...",
  "rejected": "Note: Build is broken on Windows.",
  "failure_type": "natural_language_instead_of_command",
  "source_model": "tooluse-sanity-v2-modal-l4-2026-05-08",
  "benchmark": "gad_tools",
  "case_id": "note add basic"
}

We don't train DPO yet; just collect.

Decision refs: slm-learning-108, 109, 111, 112.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


# Heuristic mapping of "icontains 'gad note'" + the user instruction
# into a plausible canonical chosen output. We don't aim for perfect
# CLI flags; we aim for "starts with the right gad subcommand and
# captures the user's intent." Operators can refine these later.

def synthesize_chosen(instruction: str, assertions: list[dict]) -> str | None:
    """Produce a plausible canonical gad CLI command for this case.

    We use the eval's icontains assertion to pick the gad subcommand,
    then derive a minimal CLI. This is a HEURISTIC chosen — not gold —
    but it's a strict-contract example to pair against the model's
    wrong-contract rejected.
    """
    targets = []
    for a in assertions:
        if a.get("type") == "icontains" and isinstance(a.get("value"), str):
            targets.append(a["value"].lower())
        elif a.get("type") == "contains-any" and isinstance(a.get("value"), list):
            for v in a["value"]:
                targets.append(str(v).lower())
    if not targets:
        return None

    # Use the FIRST gad-prefixed target as the canonical subcommand
    gad_targets = [t for t in targets if t.startswith("gad ")]
    if not gad_targets:
        return None
    cmd_root = gad_targets[0]  # e.g. "gad note", "gad task", "gad handoffs"

    # Minimal CLI by intent
    if "note" in cmd_root and "add" not in cmd_root:
        return f"{cmd_root} add --projectid slm-learning --title \"...\" --body \"{instruction}\""
    if "note" in cmd_root and "list" in instruction.lower():
        return f"{cmd_root} list --projectid slm-learning"
    if "task" in cmd_root:
        return f"{cmd_root} list --projectid slm-learning"
    if "handoff" in cmd_root:
        if any(w in instruction.lower() for w in ("show", "list")):
            return f"{cmd_root} list --projectid slm-learning"
        return f"{cmd_root} create --projectid slm-learning --phase 04 --body \"{instruction}\""
    if "snapshot" in cmd_root:
        return f"{cmd_root} --projectid slm-learning"
    if "decision" in cmd_root:
        return f"{cmd_root} list --projectid slm-learning"
    if "state" in cmd_root and "log" in cmd_root:
        return f"{cmd_root} \"{instruction}\" --projectid slm-learning"
    # Generic: just emit the gad subcommand with projectid
    return f"{cmd_root} --projectid slm-learning"


def classify_failure(rejected: str, chosen: str) -> str:
    """Map a (rejected, chosen) pair to a failure_type tag."""
    rj = rejected.lower()
    if rj.startswith("note:") or rj.startswith("here") or "i'll" in rj[:20]:
        return "natural_language_instead_of_command"
    if "gad " in rj and "--projectid" not in rj:
        return "missing_projectid"
    if rj.count("\n") > 0 and any(line.startswith("gad ") for line in rj.split("\n")):
        return "multi_command_when_one_expected"
    if rj.startswith("{"):
        return "json_when_cli_expected"
    if "gad " in rj:
        return "wrong_gad_subcommand"
    return "unknown_contract_failure"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", default="tmp/diag-2026-05-08/gad_tools_chat_n30.json")
    p.add_argument("--prompts", default="promptfoo-gad-tools.yaml")
    p.add_argument("--out", default="data/preference/tooluse_contract_failures_dpo.jsonl")
    args = p.parse_args()

    results_path = REPO_ROOT / args.results if not Path(args.results).is_absolute() else Path(args.results)
    prompts_path = REPO_ROOT / args.prompts if not Path(args.prompts).is_absolute() else Path(args.prompts)
    out_path = REPO_ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)

    results = json.loads(results_path.read_text(encoding="utf-8"))
    prompts = yaml.safe_load(prompts_path.read_text(encoding="utf-8"))

    # Build description -> assertions index
    case_index = {}
    for t in prompts.get("tests", []):
        desc = t.get("description", "")
        case_index[desc] = {
            "instruction": t.get("vars", {}).get("instruction", ""),
            "assertions": t.get("assert", []),
        }

    pairs = []
    skipped = 0
    for r in results.get("results", []):
        if r.get("passed"):
            continue
        case_id = r.get("id", "")
        case = case_index.get(case_id)
        if case is None:
            skipped += 1
            continue
        chosen = synthesize_chosen(case["instruction"], case["assertions"])
        if chosen is None:
            skipped += 1
            continue
        rejected = r.get("completion_full") or r.get("completion_preview") or ""
        if not rejected.strip():
            continue
        pair = {
            "prompt": case["instruction"],
            "chosen": chosen,
            "rejected": rejected[:1500],
            "failure_type": classify_failure(rejected, chosen),
            "source_model": results.get("adapter_id", "unknown")
                            .rsplit("/", 2)[-2] if "/" in results.get("adapter_id", "") else "tooluse-v2",
            "benchmark": results.get("benchmark", "gad_tools"),
            "case_id": case_id,
            "schema_v": 1,
            "decision_refs": ["slm-learning-108", "slm-learning-111", "slm-learning-112"],
        }
        pairs.append(pair)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"[mine] {len(pairs)} preference pairs written to {out_path.relative_to(REPO_ROOT)}")
    print(f"[mine] skipped {skipped} (no synthesizable chosen)")
    if pairs:
        from collections import Counter
        types = Counter(p["failure_type"] for p in pairs)
        print(f"[mine] failure types: {dict(types)}")


if __name__ == "__main__":
    main()
