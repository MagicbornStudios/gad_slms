"""Build 0.5B-base-failure dataset for the morphism prototype.

Per slm-learning-169: morphism Variant A trains on 0.5B-base-failure
rows, NOT on 7B-hard or generic fn_norm. This script pulls the
0.5B base × HumanEval results from the Modal volume (or a local
copy if already downloaded), filters to the failed cases, looks up
canonical solutions, and writes:

    data/processed/0p5b-hard-fn-norm-2026-05-08/rows.jsonl
    data/processed/0p5b-hard-fn-norm-2026-05-08/profile.json

This is a small wrapper around build_7b_hard_fn_norm_dataset.py
that uses the same row schema but with 0p5b-hard tags + a
results path that points at the 0.5B persist_run_id artifact.

Usage:
    python scripts/data/build_0p5b_hard_fn_norm_dataset.py

The expected results path lives on the slm-models volume at:
    /models/eval-runs/morphism-0p5b-base-2026-05-08/humaneval_chat_base_n164.json
which is what eval_adapter.py persists when called with
--persist-run-id morphism-0p5b-base-2026-05-08. Pull it locally first via:
    .venv/Scripts/modal.exe volume get slm-models \\
        eval-runs/morphism-0p5b-base-2026-05-08/humaneval_chat_base_n164.json \\
        tmp/diag-2026-05-08/base_he_0p5b_full.json

Decision refs: slm-learning-130, slm-learning-165, slm-learning-169.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS = REPO_ROOT / "tmp" / "diag-2026-05-08" / "base_he_0p5b_full.json"
DEFAULT_OUT = REPO_ROOT / "data" / "processed" / "0p5b-hard-fn-norm-2026-05-08"


def load_he_results(path: Path) -> dict:
    if not path.is_file():
        print(f"ERROR: results file not found: {path}", file=sys.stderr)
        print("Pull from Modal first:", file=sys.stderr)
        print("  .venv/Scripts/modal.exe volume get slm-models \\", file=sys.stderr)
        print("    eval-runs/morphism-0p5b-base-2026-05-08/humaneval_chat_base_n164.json \\", file=sys.stderr)
        print(f"    {path}", file=sys.stderr)
        sys.exit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def load_humaneval_dataset() -> dict:
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: datasets package not installed", file=sys.stderr)
        sys.exit(2)
    try:
        ds = load_dataset("openai/openai_humaneval", split="test")
    except Exception as e:
        print(f"ERROR: failed to load HumanEval: {e}", file=sys.stderr)
        sys.exit(2)
    out = {}
    for row in ds:
        tid = row.get("task_id")
        if tid:
            out[tid] = row
    return out


def extract_canonical_target(he_row: dict) -> str:
    prompt = he_row.get("prompt", "").rstrip()
    solution = he_row.get("canonical_solution", "").rstrip()
    if prompt and solution:
        return prompt + "\n" + solution
    return solution or ""


def build_gap_rows(results: dict, he_dataset: dict) -> list[dict]:
    rows = []
    seen = set()
    for r in results.get("results", []):
        if r.get("passed"):
            continue
        tid = r.get("id", "")
        if not tid or tid in seen:
            continue
        seen.add(tid)
        if tid not in he_dataset:
            continue
        he_row = he_dataset[tid]
        target = extract_canonical_target(he_row)
        if not target:
            continue
        rows.append({
            "id": f"hard-fnnorm-{tid}",
            "source_corpus": "humaneval-base-failures",
            "source_model": results.get("base_model", "Qwen/Qwen2.5-Coder-0.5B-Instruct"),
            "target_format": "function_definition",
            "input": he_row.get("prompt", ""),
            "target": target,
            "language": "python",
            "tags": ["0p5b-hard", "humaneval-failure"],
            "schema_v": 1,
        })
    return rows


def write_dataset(rows: list[dict], out_dir: Path, results: dict) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    profile = {
        "dataset": "0p5b-hard-fn-norm",
        "source_results": str(results.get("persisted_path") or "unknown"),
        "source_model": results.get("base_model"),
        "source_eval": "humaneval",
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
        "decision_refs": ["slm-learning-130", "slm-learning-165",
                          "slm-learning-169"],
    }
    (out_dir / "profile.json").write_text(
        json.dumps(profile, indent=2), encoding="utf-8"
    )
    return profile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(DEFAULT_RESULTS))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    results_path = Path(args.results)
    out_dir = Path(args.out)

    print(f"[build_0p5b_hard] loading {results_path}")
    results = load_he_results(results_path)
    n_total = len(results.get("results", []))
    n_failed = sum(1 for r in results.get("results", []) if not r.get("passed"))
    print(f"[build_0p5b_hard] total={n_total} failed={n_failed} "
          f"score={results.get('score')}")

    print("[build_0p5b_hard] loading HumanEval canonical dataset")
    he_dataset = load_humaneval_dataset()
    print(f"[build_0p5b_hard] HE rows: {len(he_dataset)}")

    print("[build_0p5b_hard] extracting failed cases")
    rows = build_gap_rows(results, he_dataset)
    print(f"[build_0p5b_hard] extracted {len(rows)} gap rows")

    profile = write_dataset(rows, out_dir, results)
    print(f"[build_0p5b_hard] wrote {out_dir}/rows.jsonl")
    print(f"[build_0p5b_hard] wrote {out_dir}/profile.json")
    print(f"\nDataset summary: n_rows={profile['n_rows']} "
          f"avg_target_chars={profile['avg_target_chars']}")
    print(f"\nNext: upload to Modal volume:")
    print(f"  .venv/Scripts/modal.exe run modal_app/train_lora.py::upload \\")
    print(f"    {out_dir}/rows.jsonl \\")
    print(f"    processed/0p5b-hard-fn-norm-2026-05-08/rows.jsonl")


if __name__ == "__main__":
    main()
