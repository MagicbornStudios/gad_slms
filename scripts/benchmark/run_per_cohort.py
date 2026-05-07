"""Per-cohort benchmark dispatcher (Workstream D-4 of phase 148).

Given a candidate adapter + cohort metadata, dispatch the right
benchmark suite for the cohort's content_type and emit a benchmark_run
envelope (phase-146 shape) suitable for ingestion back into the
training factory.

Subprocess contract:

    .venv-gpu/Scripts/python.exe scripts/benchmark/run_per_cohort.py \\
        --adapter <path-or-hf-id> \\
        --cohort-meta data/cohorts/<date>/COHORTS.json \\
        --cohort-id <project>-<content_type> \\
        [--max-cases 30] [--out <path>] [--no-frontier]

Stdout (single-line JSON envelope, phase-146 shape):

    {
      "schema_v": 1, "ts": "...", "role": "meta",
      "content": {
        "kind": "benchmark_run",
        "benchmark_name": "...",
        "score": 0.NN,
        "n": 30,
        "adapter_id": "...",
        "cohort_id": "global-planning",
        "evidence_tier": "T1|T2",
        "delegate_to": ["scripts/<other_eval>.py"]
      }
    }

Content-type → benchmark mapping (per workstream-d handoff D-4):

  code      -> SWE-bench Verified + HumanEval + LiveCodeBench
  narrative -> perplexity on held-out narrative slice
  planning  -> perplexity on held-out + (where available) plan-quality
  site      -> perplexity on held-out
  eval      -> reuse eval_gad_tools.py (the GAD-tools 30-case suite)

Every dispatch logs (delegate cmd, returncode, captured stdout tail)
into the envelope so the daemon can audit which underlying script
actually ran. v1 keeps the dispatch logic conservative — it shells
out to scripts that already exist; missing benchmarks return
status=unimplemented.

Decision refs: slm-learning-051 (candidate-only), slm-learning-079
(per-domain ladder), slm-learning-082 (registry), slm-learning-086
(data flywheel).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]


# Per-content-type dispatch map. Each value is a list of "benchmark
# units" — declarative records the dispatcher resolves to actual
# subprocess invocations.
DISPATCH: dict[str, list[dict]] = {
    "code": [
        {"name": "humaneval", "script": "scripts/eval_humaneval.py",
         "supports_adapter": True, "default_args": ["--max", "10"]},
        {"name": "swebench_v1", "script": "scripts/eval_swebench.py",
         "supports_adapter": True, "default_args": ["--subset", "verified",
                                                     "--max", "5"]},
        # LiveCodeBench: optional. Skipped if script missing.
        {"name": "livecodebench", "script": "scripts/eval_livecodebench.py",
         "supports_adapter": True, "default_args": []},
    ],
    "planning": [
        {"name": "gad_tools", "script": "scripts/delta/eval_candidate.py",
         "supports_adapter": True,
         "default_args": ["--benchmarks", "gad_tools", "--baseline-id",
                          "Qwen/Qwen2.5-1.5B-Instruct"]},
        # Planning-quality eval: not yet wired (TBD per phase 149).
        {"name": "plan_quality", "script": None,
         "supports_adapter": False, "default_args": [],
         "status_when_missing": "unimplemented"},
    ],
    "narrative": [
        {"name": "perplexity_narrative", "script": None,
         "supports_adapter": False, "default_args": [],
         "status_when_missing": "unimplemented"},
    ],
    "site": [
        {"name": "perplexity_site", "script": None,
         "supports_adapter": False, "default_args": [],
         "status_when_missing": "unimplemented"},
    ],
    "eval": [
        {"name": "gad_tools", "script": "scripts/delta/eval_candidate.py",
         "supports_adapter": True,
         "default_args": ["--benchmarks", "gad_tools", "--baseline-id",
                          "Qwen/Qwen2.5-1.5B-Instruct"]},
    ],
}


def parse_cohort_id(cid: str) -> tuple[str | None, str | None]:
    """Cohort IDs follow `<project>-<content_type>` per build_cohorts.py."""
    if "-" not in cid:
        return cid, None
    # Allow project names with hyphens (e.g. `magicborn-narrative`).
    # Greedy split on the LAST "-" works iff content_type never contains
    # hyphens — which is true today: planning/code/site/eval/narrative.
    project, ct = cid.rsplit("-", 1)
    return project, ct


def load_cohort_meta(meta_path: Path, cohort_id: str) -> dict | None:
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    cohorts = meta.get("cohorts") or []
    if isinstance(cohorts, dict):
        # Defensive: accept either {<cohort_id>: {...}} or [{...}, ...]
        return cohorts.get(cohort_id)
    project, content_type = parse_cohort_id(cohort_id)
    for c in cohorts:
        if c.get("project") == project and c.get("content_type") == content_type:
            return c
    return None


def dispatch_unit(unit: dict, *, adapter: str, max_cases: int,
                  no_frontier: bool, dry_run: bool) -> dict:
    name = unit["name"]
    script = unit.get("script")

    if not script:
        return {"name": name, "status": "unimplemented",
                "reason": unit.get("status_when_missing", "no script wired")}

    script_path = ROOT / script
    if not script_path.exists():
        return {"name": name, "status": "unimplemented",
                "reason": f"script not found: {script}"}

    py = ROOT / ".venv-gpu" / "Scripts" / "python.exe"
    if not py.exists():
        py_alt = ROOT / ".venv" / "Scripts" / "python.exe"
        py = py_alt if py_alt.exists() else Path("python")

    cmd: list[str] = [str(py), str(script_path)]
    if unit.get("supports_adapter"):
        # Heuristic: most of our eval scripts take --candidate-dir or
        # --model. Try --model first; fall back caller-side if that
        # script needs different arg names.
        cmd.extend(["--model", adapter])
    cmd.extend(unit.get("default_args", []))

    if no_frontier:
        cmd.append("--no-frontier")

    if dry_run:
        return {"name": name, "status": "dry-run", "cmd": " ".join(map(shlex.quote, cmd))}

    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    wall = time.time() - t0

    # Try to parse a JSON tail from stdout — most of our eval scripts
    # emit a JSON summary as the final non-empty line.
    score = None
    last_json = None
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            last_json = json.loads(line)
            score = last_json.get("score") or last_json.get("accuracy") \
                    or last_json.get("f1_macro")
            break
        except json.JSONDecodeError:
            continue

    status = "ok" if proc.returncode == 0 else "delegate_failed"
    return {
        "name": name,
        "status": status,
        "returncode": proc.returncode,
        "wall_seconds": round(wall, 2),
        "score": score,
        "cmd": " ".join(map(shlex.quote, cmd)),
        "stdout_tail": (proc.stdout or "")[-1500:],
        "stderr_tail": (proc.stderr or "")[-1500:],
        "parsed_summary": last_json,
    }


def build_envelope(*, adapter: str, cohort_id: str, content_type: str | None,
                   results: list[dict], cohort_meta: dict | None) -> dict:
    # Aggregate score across units that returned a numeric score.
    numeric = [r["score"] for r in results
               if isinstance(r.get("score"), (int, float))]
    aggregate = round(sum(numeric) / len(numeric), 4) if numeric else None

    # Evidence tier per slm-learning-071: T1 if any benchmark ran, T2
    # if at least one ran with n >= 30 (we approximate: at least one
    # status=ok with no delegate_failed alongside).
    any_ok = any(r.get("status") == "ok" for r in results)
    all_ok = all(r.get("status") == "ok" for r in results) and any_ok
    tier = "T2" if all_ok and aggregate is not None else (
           "T1" if any_ok else "T0")

    return {
        "schema_v": 1,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "role": "meta",
        "content": {
            "kind": "benchmark_run",
            "benchmark_name": f"per_cohort:{content_type or 'unknown'}",
            "score": aggregate,
            "n_units": len(results),
            "adapter_id": adapter,
            "cohort_id": cohort_id,
            "cohort_row_count": (cohort_meta or {}).get("row_count"),
            "cohort_eligible_for_training": (cohort_meta or {})
                .get("eligible_for_training"),
            "evidence_tier": tier,
            "results": results,
            "decision_refs": ["slm-learning-051", "slm-learning-079",
                              "slm-learning-082", "slm-learning-086"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True,
                        help="HF Hub id or local path of the adapter to bench")
    parser.add_argument("--cohort-id", required=True,
                        help="Cohort id, e.g. 'global-planning'")
    parser.add_argument("--cohort-meta", type=Path, default=None,
                        help="Path to COHORTS.json (defaults: latest in "
                             "data/cohorts/)")
    parser.add_argument("--content-type", default=None,
                        help="Override content_type (default: parsed from "
                             "cohort-id)")
    parser.add_argument("--max-cases", type=int, default=30)
    parser.add_argument("--no-frontier", action="store_true",
                        help="Pass --no-frontier through to delegate scripts")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print resolved subprocess commands; do not run")
    parser.add_argument("--out", type=Path, default=None,
                        help="Optional path to write the envelope (in addition "
                             "to stdout)")
    args = parser.parse_args()

    project, content_type = parse_cohort_id(args.cohort_id)
    if args.content_type:
        content_type = args.content_type
    if not content_type:
        print(json.dumps({"status": "error",
                          "error": f"cannot infer content_type from cohort_id "
                                   f"{args.cohort_id!r} (expected "
                                   f"<project>-<content_type>)"}))
        return 2

    if content_type not in DISPATCH:
        print(json.dumps({"status": "error",
                          "error": f"unknown content_type: {content_type}; "
                                   f"supported: {sorted(DISPATCH)}"}))
        return 2

    # Cohort meta lookup is best-effort — we still emit the envelope
    # if the meta file isn't present (just without the cohort row count).
    cohort_meta_path = args.cohort_meta
    if not cohort_meta_path:
        candidates = sorted((ROOT / "data" / "cohorts").glob("*/COHORTS.json"),
                            reverse=True)
        cohort_meta_path = candidates[0] if candidates else None

    cohort_meta = (load_cohort_meta(cohort_meta_path, args.cohort_id)
                   if cohort_meta_path else None)

    units = DISPATCH[content_type]
    results: list[dict] = []
    for unit in units:
        results.append(dispatch_unit(unit, adapter=args.adapter,
                                     max_cases=args.max_cases,
                                     no_frontier=args.no_frontier,
                                     dry_run=args.dry_run))

    envelope = build_envelope(adapter=args.adapter, cohort_id=args.cohort_id,
                              content_type=content_type, results=results,
                              cohort_meta=cohort_meta)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(envelope, indent=2), encoding="utf-8")

    # Single-line JSON envelope for daemon consumption
    print(json.dumps(envelope))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
