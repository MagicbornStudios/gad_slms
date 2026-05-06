"""SWE-bench evaluation harness — STUB scaffolding.

Workstream C of the cross-instance bridge handoff
(.planning/handoffs/open/h-2026-05-06T09-30-00-slm-learning-bridge.md)
+ phase 06 (SWE-bench Integration, .planning/phases/PHASE-06-swe-bench-integration.md).

This is a SCAFFOLD — full SWE-bench-Lite + SWE-bench-Verified
evaluation requires the official harness (Docker preferred, subprocess
fallback for Windows), patch generator, and test runner. Phase 06's
PLAN.md spells out the eight tasks.

For now this script:

1. Loads the official `princeton-nlp/SWE-bench_Lite` dataset metadata
   from HuggingFace (or stubs out if unavailable).
2. Locks a 50-issue slice via `data/swe_bench_slice_v1.json` (created
   on first run if missing). Selection: 30 from Lite + 20 from
   Verified, diverse repos, mixed difficulty.
3. Returns a phase-146-shaped JSON envelope with status="scaffold"
   so downstream consumers can see the contract works without a real
   run yet.

Real scoring (patch_generator + test_runner) is phase 06 SL-T-06-03/04.

Usage:
    .venv-gpu/Scripts/python.exe scripts/eval_swebench.py \\
        --model-path scrubster/dr-stein-stage25-qwen15-multitask \\
        --slice-version v1 \\
        --out experiments/runs/stage25_qwen15_multitask/eval/swebench.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLICE_PATH = ROOT / "data" / "swe_bench_slice_v1.json"


# Hand-picked slice — until phase 06 SL-T-06-02 lands the diversity
# selector, this seeds the slice with a small set of well-known issues
# from Lite + Verified that exercise different repos and difficulty
# bands. Phase 06 will replace this with a curated 50-issue slice.
SCAFFOLD_SLICE = {
    "version": "v1-scaffold",
    "lite_issue_ids": [
        "django__django-11099",
        "django__django-11451",
        "django__django-11815",
        "django__django-12453",
        "django__django-13230",
        "matplotlib__matplotlib-23314",
        "matplotlib__matplotlib-23476",
        "matplotlib__matplotlib-25775",
        "psf__requests-1142",
        "psf__requests-1724",
        "psf__requests-2317",
        "pytest-dev__pytest-5103",
        "pytest-dev__pytest-7373",
        "scikit-learn__scikit-learn-13280",
        "scikit-learn__scikit-learn-13439",
        "scikit-learn__scikit-learn-25232",
        "sphinx-doc__sphinx-7686",
        "sphinx-doc__sphinx-8265",
        "sphinx-doc__sphinx-8475",
        "sympy__sympy-13615",
        "sympy__sympy-15873",
        "sympy__sympy-21379",
        "sympy__sympy-22456",
        "astropy__astropy-7166",
        "astropy__astropy-12907",
        "pylint-dev__pylint-4661",
        "pylint-dev__pylint-7993",
        "pydata__xarray-3993",
        "pydata__xarray-4248",
        "mwaskom__seaborn-3010",
    ],
    "verified_issue_ids": [
        "django__django-11138",
        "django__django-11532",
        "django__django-12517",
        "django__django-12700",
        "django__django-13363",
        "django__django-14787",
        "django__django-15252",
        "django__django-15814",
        "matplotlib__matplotlib-21568",
        "matplotlib__matplotlib-22871",
        "psf__requests-863",
        "scikit-learn__scikit-learn-10297",
        "scikit-learn__scikit-learn-13496",
        "scikit-learn__scikit-learn-14894",
        "sphinx-doc__sphinx-8627",
        "sphinx-doc__sphinx-9711",
        "sympy__sympy-15011",
        "sympy__sympy-17630",
        "sympy__sympy-18189",
        "sympy__sympy-23117",
    ],
}


def ensure_slice(slice_path: Path) -> dict:
    if slice_path.exists():
        return json.loads(slice_path.read_text(encoding="utf-8"))
    slice_path.parent.mkdir(parents=True, exist_ok=True)
    slice_path.write_text(json.dumps(SCAFFOLD_SLICE, indent=2), encoding="utf-8")
    return SCAFFOLD_SLICE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=str, required=True,
                        help="HF Hub id or local adapter path")
    parser.add_argument("--slice-version", type=str, default="v1",
                        help="Locked slice version")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output JSON path (stdout if omitted)")
    parser.add_argument("--lite-only", action="store_true",
                        help="Run only the SWE-bench-Lite portion")
    parser.add_argument("--verified-only", action="store_true",
                        help="Run only the SWE-bench-Verified portion")
    args = parser.parse_args()

    slice_data = ensure_slice(SLICE_PATH)
    issue_ids: list[str] = []
    if not args.verified_only:
        issue_ids.extend(slice_data["lite_issue_ids"])
    if not args.lite_only:
        issue_ids.extend(slice_data["verified_issue_ids"])

    # Scaffold result — actual run is phase 06 SL-T-06-03/04.
    issues = [
        {
            "issue_id": iid,
            "pass": None,
            "patch_chars": 0,
            "runtime_s": 0.0,
            "error_class": "scaffold_unimplemented",
        }
        for iid in issue_ids
    ]

    summary = {
        "schema_v": 1,
        "role": "benchmark_run",
        "benchmark": "swe_bench",
        "model_path": args.model_path,
        "slice_version": slice_data.get("version", "v1-scaffold"),
        "evaluated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "issues_total": len(issues),
        "issues": issues,
        "summary": {
            "passed": 0,
            "failed": 0,
            "scaffold_unimplemented": len(issues),
            "pass_rate": None,
            "vs_bare_base": None,
            "vs_opus_baseline": None,
            "evidence_tier": "T1",
        },
        "status": "scaffold",
        "decision_ref": "slm-learning-053 + slm-learning-070 + slm-learning-071",
        "next_step": "Phase 06 SL-T-06-03 (patch_generator) + SL-T-06-04 (test_runner) implement real scoring.",
    }

    out_text = json.dumps(summary, indent=2)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(out_text, encoding="utf-8")
        print(f"[swebench] wrote scaffold result to {args.out}")
    else:
        print(out_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
