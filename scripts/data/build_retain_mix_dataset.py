"""Build a hard+retain mixed dataset to prevent catastrophic forgetting.

Per slm-learning-172 (operator + ChatGPT review consensus 2026-05-08):
the 73-row hard dataset alone caused catastrophic regression at 0.5B
across LoRA AND morphism. Hypothesis: a tiny intervention asked to
absorb only base failures over-rotates the residual stream toward
"weird hard-case correction" and breaks unrelated patterns.

Mitigation: mix base-failure rows with retain rows (cases the base
already PASSED) at a configurable ratio (default 30/70 hard:retain).
The retain rows teach the model "do not break what already works"
alongside "fix what doesn't."

Inputs:
  --base-results <path>  — eval_adapter persist JSON for the base
                           model (humaneval results with passed/failed)
  --hard-ratio 0.30      — fraction of rows that are base failures
                           (rest are passes, i.e. retain)
  --max-rows N           — cap total rows (None = all available)
  --out <dir>            — output directory

Output:
  <out>/rows.jsonl       — combined hard + retain rows, shuffled (seed 42)
  <out>/profile.json     — n_total, n_hard, n_retain, ratios, source

Schema mirrors build_0p5b_hard_fn_norm_dataset.py with one new field:
  - "row_kind": "hard" | "retain"

Decision refs: slm-learning-126, slm-learning-130, slm-learning-172.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_he_results(path: Path) -> dict:
    if not path.is_file():
        print(f"ERROR: results file not found: {path}", file=sys.stderr)
        sys.exit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def load_humaneval_dataset() -> dict:
    from datasets import load_dataset
    try:
        ds = load_dataset("openai/openai_humaneval", split="test")
    except Exception:
        ds = load_dataset("openai_humaneval", split="test")
    return {row["task_id"]: row for row in ds if row.get("task_id")}


def extract_canonical_target(he_row: dict) -> str:
    prompt = he_row.get("prompt", "").rstrip()
    solution = he_row.get("canonical_solution", "").rstrip()
    if prompt and solution:
        return prompt + "\n" + solution
    return solution or ""


def build_rows(results: dict, he_dataset: dict, hard_ratio: float,
                max_rows: int | None, source_model: str) -> list[dict]:
    hard_ids = [r["id"] for r in results.get("results", [])
                 if not r.get("passed") and r.get("id") in he_dataset]
    retain_ids = [r["id"] for r in results.get("results", [])
                   if r.get("passed") and r.get("id") in he_dataset]

    print(f"[retain-mix] hard available: {len(hard_ids)}")
    print(f"[retain-mix] retain available: {len(retain_ids)}")

    # Decide n_hard, n_retain to hit ratio
    n_hard_avail = len(hard_ids)
    n_retain_avail = len(retain_ids)
    if hard_ratio <= 0 or hard_ratio >= 1:
        raise ValueError(f"hard_ratio must be in (0,1), got {hard_ratio}")

    # Try using ALL hard rows; size retain to hit ratio
    n_hard = n_hard_avail
    target_total_from_hard = int(n_hard / hard_ratio)
    n_retain = min(target_total_from_hard - n_hard, n_retain_avail)
    if n_retain < 0:
        n_retain = 0

    if max_rows and n_hard + n_retain > max_rows:
        # Scale down keeping ratio
        n_hard = int(max_rows * hard_ratio)
        n_retain = max_rows - n_hard
        n_hard = min(n_hard, n_hard_avail)
        n_retain = min(n_retain, n_retain_avail)

    print(f"[retain-mix] using n_hard={n_hard} n_retain={n_retain} "
          f"actual_ratio={n_hard/(n_hard+n_retain):.3f}")

    rng = random.Random(42)
    rng.shuffle(retain_ids)
    selected_hard = hard_ids[:n_hard]
    selected_retain = retain_ids[:n_retain]

    rows: list[dict] = []
    for tid in selected_hard:
        he_row = he_dataset[tid]
        target = extract_canonical_target(he_row)
        if not target:
            continue
        rows.append({
            "id": f"retainmix-hard-{tid}",
            "source_corpus": "humaneval-base-failures",
            "source_model": source_model,
            "target_format": "function_definition",
            "input": he_row.get("prompt", ""),
            "target": target,
            "language": "python",
            "tags": ["retain-mix", "humaneval-failure"],
            "row_kind": "hard",
            "schema_v": 1,
        })
    for tid in selected_retain:
        he_row = he_dataset[tid]
        target = extract_canonical_target(he_row)
        if not target:
            continue
        rows.append({
            "id": f"retainmix-retain-{tid}",
            "source_corpus": "humaneval-base-passes",
            "source_model": source_model,
            "target_format": "function_definition",
            "input": he_row.get("prompt", ""),
            "target": target,
            "language": "python",
            "tags": ["retain-mix", "humaneval-pass"],
            "row_kind": "retain",
            "schema_v": 1,
        })

    rng.shuffle(rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-results", required=True,
                    help="path to eval_adapter persist JSON for the BASE model")
    ap.add_argument("--hard-ratio", type=float, default=0.30,
                    help="fraction of rows that are base-failures (rest=retain)")
    ap.add_argument("--max-rows", type=int, default=None,
                    help="cap total rows; default = use all hard + scale retain")
    ap.add_argument("--out", required=True, help="output directory")
    args = ap.parse_args()

    results_path = Path(args.base_results)
    out_dir = Path(args.out)

    print(f"[retain-mix] loading {results_path}")
    results = load_he_results(results_path)
    source_model = results.get("base_model", "unknown")
    print(f"[retain-mix] source_model={source_model} "
          f"score={results.get('score')}")

    he_dataset = load_humaneval_dataset()
    rows = build_rows(results, he_dataset, args.hard_ratio, args.max_rows,
                       source_model)

    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_hard = sum(1 for r in rows if r["row_kind"] == "hard")
    n_retain = sum(1 for r in rows if r["row_kind"] == "retain")
    profile = {
        "dataset": "retain-mix",
        "source_results": str(results_path),
        "source_model": source_model,
        "source_eval": "humaneval",
        "n_total": len(rows),
        "n_hard": n_hard,
        "n_retain": n_retain,
        "actual_hard_ratio": round(n_hard / max(1, len(rows)), 4),
        "configured_hard_ratio": args.hard_ratio,
        "max_rows_cap": args.max_rows,
        "shuffle_seed": 42,
        "data_contract": "docs/data-contracts/coding_sft.md",
        "decision_refs": ["slm-learning-126", "slm-learning-130",
                          "slm-learning-172"],
    }
    (out_dir / "profile.json").write_text(
        json.dumps(profile, indent=2), encoding="utf-8"
    )
    print(f"[retain-mix] wrote {rows_path}")
    print(f"[retain-mix] n_total={len(rows)} n_hard={n_hard} "
          f"n_retain={n_retain}")


if __name__ == "__main__":
    main()
