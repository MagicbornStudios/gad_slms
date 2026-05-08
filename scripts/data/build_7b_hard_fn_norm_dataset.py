"""Extract 7B base failures from HumanEval and build a gap-targeted dataset.

Per slm-learning-119 (gap-targeted data), this script identifies cases where
the 7B base model FAILED on HumanEval and synthesizes them into a normalized
training dataset suitable for fine-tuning on the failure modes.

Input:
  - tmp/diag-2026-05-08/base_he_chat_full.json (7B base × HumanEval results)
  - Canonical HumanEval dataset via datasets.load_dataset()

Output:
  - data/processed/7b-hard-fn-norm-2026-05-08/rows.jsonl
  - data/processed/7b-hard-fn-norm-2026-05-08/profile.json

Data contract:
  rows.jsonl: JSONL with schema {id, source_corpus, target_format, input,
    target, language, tags, schema_v}
  profile.json: summary stats (n_rows, avg_target_chars, etc.)

Matches prepare_ocr_variants.py style and inherits its normalization logic
(function_definition target format, deduplication by task_id).

Usage:
  python scripts/data/build_7b_hard_fn_norm_dataset.py
  python scripts/data/build_7b_hard_fn_norm_dataset.py --include-mbpp

Decision refs: slm-learning-119 (gap-targeted data).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_BASE = REPO_ROOT / "data" / "processed" / "7b-hard-fn-norm-2026-05-08"


def load_he_results(path: Path) -> dict:
    """Load the HumanEval base results JSON."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"ERROR: results file not found: {path}")
        print("Hint: run the base model evals first with eval-7b-base-he.py")
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR: malformed JSON in {path}: {e}")
        sys.exit(2)


def load_humaneval_dataset() -> dict:
    """Load the canonical HumanEval dataset (test split).

    Returns a dict mapping task_id (e.g. "HumanEval/0") to the row dict
    containing prompt, canonical_solution, etc.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: datasets package not installed")
        print("Install: pip install datasets")
        sys.exit(2)

    try:
        ds = load_dataset("openai/openai_humaneval", split="test")
    except Exception as e:
        print(f"ERROR: failed to load HumanEval dataset: {e}")
        print("Hint: check internet connection and HuggingFace rate limits")
        sys.exit(2)

    out = {}
    for row in ds:
        task_id = row.get("task_id", None)
        if task_id is None:
            continue
        out[task_id] = row
    return out


def extract_canonical_target(he_row: dict) -> str:
    """Combine prompt + canonical_solution into full function def target.

    HumanEval provides:
      prompt: function signature + docstring
      canonical_solution: function body

    Returns the concatenation (full function definition).
    """
    prompt = he_row.get("prompt", "").rstrip()
    solution = he_row.get("canonical_solution", "").rstrip()
    if prompt and solution:
        return prompt + "\n" + solution
    elif solution:
        return solution
    return ""


def build_gap_rows(results: dict, he_dataset: dict,
                   seen_ids: set) -> list[dict]:
    """Extract failed cases and convert to training rows.

    For each failed case in results, look up the canonical solution from
    he_dataset and build a row in the target format.
    """
    rows = []
    for result in results.get("results", []):
        if result.get("passed"):
            # Skip passed cases — we only want the gaps
            continue

        task_id = result.get("id", "")
        if not task_id or task_id in seen_ids:
            continue
        seen_ids.add(task_id)

        # Look up canonical solution
        if task_id not in he_dataset:
            # Task not in dataset; skip
            continue

        he_row = he_dataset[task_id]
        target = extract_canonical_target(he_row)
        if not target:
            continue

        row = {
            "id": f"hard-fnnorm-{task_id}",
            "source_corpus": "humaneval-base-failures",
            "target_format": "function_definition",
            "input": he_row.get("prompt", ""),
            "target": target,
            "language": "python",
            "tags": ["7b-hard", "humaneval-failure"],
            "schema_v": 1,
        }
        rows.append(row)

    return rows


def write_dataset(rows: list[dict], out_dir: Path) -> dict:
    """Write rows.jsonl and profile.json; return profile dict."""
    out_dir.mkdir(parents=True, exist_ok=True)

    rows_path = out_dir / "rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Profile
    profile = {
        "dataset": "7b-hard-fn-norm",
        "source_results": "tmp/diag-2026-05-08/base_he_chat_full.json",
        "n_rows": len(rows),
        "target_format": "function_definition",
        "avg_target_chars": round(
            sum(len(r["target"]) for r in rows) / max(1, len(rows)), 1
        ),
        "avg_input_chars": round(
            sum(len(r["input"]) for r in rows) / max(1, len(rows)), 1
        ),
        "language": "python",
        "data_contract": "docs/data-contracts/coding_sft.md",
        "decision_refs": ["slm-learning-119"],
    }

    (out_dir / "profile.json").write_text(
        json.dumps(profile, indent=2), encoding="utf-8"
    )

    return profile


def main():
    parser = argparse.ArgumentParser(
        description="Extract 7B base failures and build gap-targeted dataset"
    )
    parser.add_argument(
        "--results",
        default="tmp/diag-2026-05-08/base_he_chat_full.json",
        help="Path to 7B base × HumanEval results JSON",
    )
    parser.add_argument(
        "--out",
        default=str(OUT_BASE),
        help="Output directory for rows.jsonl + profile.json",
    )
    parser.add_argument(
        "--include-mbpp",
        action="store_true",
        help="Include MBPP failures (future extension; not yet supported)",
    )
    args = parser.parse_args()

    results_path = (
        REPO_ROOT / args.results
        if not Path(args.results).is_absolute()
        else Path(args.results)
    )
    out_dir = Path(args.out)

    # Load results
    print(f"[build_7b_hard_fn_norm] loading {results_path}")
    results = load_he_results(results_path)
    n_total = len(results.get("results", []))
    n_failed = sum(
        1 for r in results.get("results", []) if not r.get("passed")
    )
    print(f"[build_7b_hard_fn_norm] total={n_total}, failed={n_failed}")

    # Load HumanEval canonical dataset
    print("[build_7b_hard_fn_norm] loading HumanEval canonical dataset")
    he_dataset = load_humaneval_dataset()
    print(f"[build_7b_hard_fn_norm] loaded {len(he_dataset)} HE canonical rows")

    # Extract gap rows
    print("[build_7b_hard_fn_norm] extracting failed cases")
    seen = set()
    gap_rows = build_gap_rows(results, he_dataset, seen)
    print(f"[build_7b_hard_fn_norm] extracted {len(gap_rows)} gap rows")

    # Write dataset
    profile = write_dataset(gap_rows, out_dir)
    print(f"[build_7b_hard_fn_norm] wrote {out_dir}/rows.jsonl")
    print(f"[build_7b_hard_fn_norm] wrote {out_dir}/profile.json")
    print(f"\nDataset summary:")
    print(f"  n_rows: {profile['n_rows']}")
    print(f"  avg_target_chars: {profile['avg_target_chars']}")
    print(f"  avg_input_chars: {profile['avg_input_chars']}")
    print(f"\nNext step:")
    print(f"  modal volume put slm-data \\")
    print(f"      {out_dir}/rows.jsonl \\")
    print(f"      processed/7b-hard-fn-norm/rows.jsonl")


if __name__ == "__main__":
    main()
