"""Profile + transform OpenCodeReasoning into 5 variants.

Per 2026-05-08 directive (post-OCR-LoRA regression diagnosis), do
NOT train on raw OCR alone. This script produces 5 transformed
variants that test specific hypotheses about WHY raw OCR LoRA
regressed HumanEval/MBPP:

    ocr_raw                       — identity (control / baseline)
    ocr_no_think                  — strip <think>...</think> blocks
    ocr_function_normalized       — extract function-only; drop main
    ocr_mixed_instruction_50      — 50/50 mix with instruction-following
    ocr_high_quality_subset       — filter to high-quality rows only

The script does NOT train. It writes dataset profiles + samples to:

    data/processed/ocr-variants-2026-05-08/<variant>/
        rows.jsonl
        profile.json
        samples.md   (10 before/after examples for review)

Then `modal volume put slm-data ...` uploads each variant to the
volume; training jobs reference them via `dataset_volume_path`.

Decision refs: slm-learning-103, slm-learning-107.
Data contract: docs/data-contracts/coding_sft.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_BASE = REPO_ROOT / "data" / "processed" / "ocr-variants-2026-05-08"


# ----- transformations ------------------------------------------------

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
PYTHON_FENCE_RE = re.compile(r"```(?:python)?\s*\n?(.*?)\n?```", re.DOTALL)


def strip_think(text: str) -> str:
    """Remove <think>...</think> blocks. Preserve the rest verbatim."""
    return THINK_RE.sub("", text).strip()


def extract_python_code(text: str) -> str:
    """Pull the first python code block from text. Falls back to text."""
    m = PYTHON_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def looks_like_function_only(code: str) -> bool:
    """Heuristic: code defines functions but does not run them at the
    module level via input()/print() outside a function."""
    if not code.strip():
        return False
    # Has at least one def
    if "def " not in code:
        return False
    # Module-level input() or print() outside any def
    indent_zero_calls = re.findall(r"^(?:input\(|print\()", code, re.MULTILINE)
    if indent_zero_calls:
        return False
    # No `if __name__ == "__main__"` block
    if "__main__" in code:
        return False
    return True


def normalize_to_function(code: str) -> str | None:
    """Try to convert a competitive-programming program into a
    function-style solution. Conservative: returns None if we can't
    do it cleanly. The intent is to filter aggressively rather than
    do bad transformations."""
    code = code.strip()
    if looks_like_function_only(code):
        return code
    # Trivial pattern: ends with `print(some_expr)` and has a function
    # def above. Try to extract the def block as the answer.
    defs = re.findall(r"(def\s+\w+\(.*?\):\s*(?:\n[ \t].*)+)", code,
                      flags=re.MULTILINE)
    if len(defs) == 1:
        return defs[0].strip()
    # Multi-def: keep all defs, drop main-level statements
    if len(defs) > 1:
        return "\n\n".join(d.strip() for d in defs)
    return None


# ----- per-row variants -----------------------------------------------

def variant_raw(row: dict) -> dict | None:
    return {
        "id": f"ocr-raw-{row.get('id', '?')}",
        "source_corpus": "open-code-reasoning",
        "target_format": "competitive_program",
        "input": row.get("input", ""),
        "target": row.get("output", ""),
        "language": "python",
        "tags": ["competitive-programming", "raw"],
        "schema_v": 1,
    }


def variant_no_think(row: dict) -> dict | None:
    out = row.get("output", "")
    if "<think>" not in out:
        # Already think-free, skip (avoid duplicating with raw)
        return None
    return {
        "id": f"ocr-no-think-{row.get('id', '?')}",
        "source_corpus": "open-code-reasoning",
        "target_format": "competitive_program",
        "input": row.get("input", ""),
        "target": strip_think(out),
        "language": "python",
        "tags": ["competitive-programming", "no-think"],
        "schema_v": 1,
    }


def variant_function_normalized(row: dict) -> dict | None:
    out = row.get("output", "")
    code = extract_python_code(strip_think(out))
    func_code = normalize_to_function(code)
    if func_code is None:
        return None
    return {
        "id": f"ocr-fn-norm-{row.get('id', '?')}",
        "source_corpus": "open-code-reasoning",
        "target_format": "full_function_definition",
        "input": row.get("input", ""),
        "target": func_code,
        "language": "python",
        "tags": ["function-normalized"],
        "schema_v": 1,
    }


def variant_high_quality(row: dict) -> dict | None:
    out = row.get("output", "")
    inp = row.get("input", "")
    code = extract_python_code(strip_think(out))
    # Quality filters: code is parseable, between 5 and 200 LOC,
    # input prompt is non-trivial.
    if not code or len(code) < 50 or len(code) > 8000:
        return None
    if len(inp) < 20:
        return None
    try:
        compile(code, "<ocr>", "exec")
    except SyntaxError:
        return None
    func_code = normalize_to_function(code)
    if func_code is None:
        return None
    return {
        "id": f"ocr-hq-{row.get('id', '?')}",
        "source_corpus": "open-code-reasoning",
        "target_format": "full_function_definition",
        "input": inp,
        "target": func_code,
        "language": "python",
        "tags": ["high-quality", "syntax-clean", "function-normalized"],
        "schema_v": 1,
    }


VARIANTS = {
    "ocr_raw": variant_raw,
    "ocr_no_think": variant_no_think,
    "ocr_function_normalized": variant_function_normalized,
    "ocr_high_quality_subset": variant_high_quality,
}


def variant_mixed_instruction_50(rows: Iterable[dict],
                                  instruction_rows: Iterable[dict]) -> list[dict]:
    """50/50 mix: ocr_function_normalized + instruction-following.

    instruction_rows must be pre-loaded; we don't fetch them here
    because the operator may want to swap the source (open-instruct,
    alpaca-cleaned, ultrachat, etc.).
    """
    fn_rows = [variant_function_normalized(r) for r in rows]
    fn_rows = [r for r in fn_rows if r is not None]
    n = min(len(fn_rows), len(list(instruction_rows)))
    out = []
    for r in fn_rows[:n]:
        out.append(r)
    for r in instruction_rows:
        out.append({
            "id": f"instruct-{r.get('id', '?')}",
            "source_corpus": r.get("source_corpus", "instruction-following"),
            "target_format": r.get("target_format",
                                   "full_function_definition"),
            "input": r.get("input", ""),
            "target": r.get("output", ""),
            "language": "python",
            "tags": ["instruction-mix"],
            "schema_v": 1,
        })
    return out


# ----- driver --------------------------------------------------------

def load_ocr_rows(parquet_path: Path, limit: int | None) -> list[dict]:
    import pyarrow.parquet as pq
    table = pq.read_table(parquet_path)
    rows = []
    for i, batch in enumerate(table.to_batches()):
        for row in batch.to_pylist():
            rows.append({
                "id": row.get("id", i),
                "input": row.get("input") or row.get("question") or "",
                "output": row.get("output") or row.get("answer") or row.get("solution") or "",
            })
            if limit and len(rows) >= limit:
                return rows
    return rows


def write_variant(name: str, rows: list[dict], out_dir: Path) -> dict:
    var_dir = out_dir / name
    var_dir.mkdir(parents=True, exist_ok=True)
    rows_path = var_dir / "rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as fh:
        for r in rows:
            if r is None:
                continue
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Profile
    nonnull = [r for r in rows if r is not None]
    profile = {
        "variant": name,
        "n_rows": len(nonnull),
        "n_input_rows": len(rows),
        "kept_fraction": round(len(nonnull) / max(1, len(rows)), 3),
        "target_formats": _count(r["target_format"] for r in nonnull),
        "avg_target_chars": _avg(len(r["target"]) for r in nonnull),
        "avg_input_chars": _avg(len(r["input"]) for r in nonnull),
    }
    (var_dir / "profile.json").write_text(
        json.dumps(profile, indent=2), encoding="utf-8"
    )

    # Samples
    samples = nonnull[:10]
    with (var_dir / "samples.md").open("w", encoding="utf-8") as fh:
        fh.write(f"# {name} — 10 samples\n\n")
        for i, r in enumerate(samples):
            fh.write(f"## Sample {i+1} ({r['target_format']})\n\n")
            fh.write("### input\n```\n")
            fh.write(r["input"][:1000])
            fh.write("\n```\n\n### target\n```python\n")
            fh.write(r["target"][:1500])
            fh.write("\n```\n\n")

    return profile


def _count(it):
    out = {}
    for x in it:
        out[x] = out.get(x, 0) + 1
    return out


def _avg(it):
    items = list(it)
    return round(sum(items) / max(1, len(items)), 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data/external/open-code-reasoning/data.parquet")
    parser.add_argument("--limit", type=int, default=2000,
                        help="Cap input rows for fast prep.")
    parser.add_argument("--out", default=str(OUT_BASE))
    args = parser.parse_args()

    src = REPO_ROOT / args.source if not Path(args.source).is_absolute() else Path(args.source)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        print(f"ERROR: source not found: {src}")
        print("Hint: data is on the slm-data Modal volume; download a "
              "sample with `modal volume get slm-data "
              "external/open-code-reasoning/data.parquet ./local.parquet`")
        sys.exit(2)

    print(f"[prepare_ocr_variants] loading {src}")
    rows = load_ocr_rows(src, args.limit)
    print(f"[prepare_ocr_variants] loaded {len(rows)} input rows")

    profiles = {}
    for vname, vfn in VARIANTS.items():
        print(f"[prepare_ocr_variants] building variant {vname}")
        transformed = [vfn(r) for r in rows]
        profile = write_variant(vname, transformed, out_dir)
        profiles[vname] = profile
        print(f"  -> kept {profile['n_rows']}/{profile['n_input_rows']} "
              f"({profile['kept_fraction']*100:.1f}%)")

    # Mixed variant — needs instruction data; skipped if none provided.
    # Operator can run a separate pass with --instruction-source.
    print("[prepare_ocr_variants] ocr_mixed_instruction_50: "
          "skipped (needs --instruction-source)")
    profiles["ocr_mixed_instruction_50"] = {"variant": "ocr_mixed_instruction_50", "n_rows": 0,
                                              "kept_fraction": 0.0, "skipped_reason": "needs instruction-source"}

    # Top-level summary
    summary = {
        "ts": __import__("datetime").datetime.now().isoformat(),
        "source": str(src),
        "limit": args.limit,
        "variants": profiles,
        "data_contract": "docs/data-contracts/coding_sft.md",
    }
    (out_dir / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"[prepare_ocr_variants] wrote SUMMARY.json to {out_dir}")
    print("\nNext step:")
    print("  modal volume put slm-data \\")
    print(f"      {out_dir}/<variant>/rows.jsonl \\")
    print("      processed/ocr-variants/<variant>/rows.jsonl")
    print("Then update training spec dataset_volume_path to the volume location.")


if __name__ == "__main__":
    main()
