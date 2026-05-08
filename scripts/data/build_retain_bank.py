"""Build a per-base retain bank from the base's eval results.

For each base model we evaluate, the rows the base PASSES become its
retain-bank entries. Future consolidation runs sample from this bank
to keep "do not forget what already works" in the training mix.

Per slm-learning-178 (proposed). Companion to build_consolidation_mix.py.

Inputs:
  --base-results <path>  — eval_adapter persist JSON for the base
                            (must include per-case `passed` field)
  --benchmark <name>     — humaneval / mbpp / gad_tools
  --base-model-slug <s>  — short label like '1p5b' or '0p5b' or '7b'
  --out <dir>            — destination dir; default
                            data/retain-banks/<base>/<benchmark>/<date>/

Outputs:
  <out>/passed.jsonl     — one row per base-passed case, function-definition format
  <out>/profile.json     — n_passed, n_failed, source_results path, ts

Schema mirrors build_0p5b_hard_fn_norm_dataset rows + adds
`row_kind: "retain"` and `base_passed: true` for downstream filtering.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_he_results(path: Path) -> dict:
    if not path.is_file():
        print(f"ERROR: {path}", file=sys.stderr)
        sys.exit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def load_humaneval_dataset() -> dict:
    from datasets import load_dataset
    try:
        ds = load_dataset("openai/openai_humaneval", split="test")
    except Exception:
        ds = load_dataset("openai_humaneval", split="test")
    return {row["task_id"]: row for row in ds if row.get("task_id")}


def load_mbpp_dataset() -> dict:
    from datasets import load_dataset
    ds = load_dataset("google-research-datasets/mbpp", "sanitized",
                       split="test")
    return {f"mbpp-{row.get('task_id', i)}": row for i, row in enumerate(ds)}


def extract_he_target(he_row: dict) -> str:
    prompt = he_row.get("prompt", "").rstrip()
    sol = he_row.get("canonical_solution", "").rstrip()
    return (prompt + "\n" + sol) if (prompt and sol) else (sol or "")


def extract_mbpp_target(row: dict) -> str:
    code = row.get("code", "") or ""
    return code.rstrip()


def extract_mbpp_input(row: dict) -> str:
    text = row.get("prompt") or row.get("text") or ""
    test_list = row.get("test_list", [])
    test_example = test_list[0] if test_list else ""
    return (f"Solve this Python problem. Output only the function definition.\n\n"
            f"{text}\n\nExample test:\n{test_example}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-results", required=True)
    ap.add_argument("--benchmark", default="humaneval",
                    choices=["humaneval", "mbpp"])
    ap.add_argument("--base-model-slug", required=True,
                    help="short slug like '1p5b' or '7b'")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    date = dt.date.today().isoformat()
    out_dir = (Path(args.out) if args.out else
               REPO_ROOT / "data" / "retain-banks" / args.base_model_slug
               / args.benchmark / date)

    print(f"[retain-bank] loading {args.base_results}")
    results = load_he_results(Path(args.base_results))
    source_model = results.get("base_model", "unknown")

    if args.benchmark == "humaneval":
        cases_ds = load_humaneval_dataset()
    else:
        cases_ds = load_mbpp_dataset()

    rows = []
    n_passed = 0
    n_failed = 0
    for r in results.get("results", []):
        tid = r.get("id", "")
        if r.get("passed"):
            n_passed += 1
            if tid not in cases_ds:
                continue
            ds_row = cases_ds[tid]
            if args.benchmark == "humaneval":
                input_str = ds_row.get("prompt", "")
                target_str = extract_he_target(ds_row)
            else:
                input_str = extract_mbpp_input(ds_row)
                target_str = extract_mbpp_target(ds_row)
            if not target_str:
                continue
            rows.append({
                "id": f"retain-{args.base_model_slug}-{args.benchmark}-{tid}",
                "source_corpus": f"{args.benchmark}-base-passes",
                "source_model": source_model,
                "source_eval": args.benchmark,
                "target_format": "function_definition",
                "input": input_str,
                "target": target_str,
                "language": "python",
                "tags": [f"{args.base_model_slug}-retain", f"{args.benchmark}-pass"],
                "row_kind": "retain",
                "base_passed": True,
                "schema_v": 1,
            })
        else:
            n_failed += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "passed.jsonl"
    with rows_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    profile = {
        "retain_bank_id": f"{args.base_model_slug}-{args.benchmark}-{date}",
        "ts": dt.datetime.utcnow().isoformat() + "Z",
        "source_results": args.base_results,
        "source_model": source_model,
        "source_eval": args.benchmark,
        "n_passed_total": n_passed,
        "n_failed_total": n_failed,
        "n_retain_rows": len(rows),
        "decision_refs": ["slm-learning-172", "slm-learning-173",
                           "slm-learning-178"],
    }
    (out_dir / "profile.json").write_text(
        json.dumps(profile, indent=2), encoding="utf-8"
    )
    print(f"[retain-bank] wrote {rows_path}")
    print(f"[retain-bank] n_retain_rows={len(rows)} (passed={n_passed}, failed={n_failed})")


if __name__ == "__main__":
    main()
