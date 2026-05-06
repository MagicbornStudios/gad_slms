"""Cohort builder — slice a telemetry export into (project, content_type) JSONL buckets.

Workstream D-2 of the cross-instance bridge. Consumer side of phase
148 (per-domain LoRA registry).

Per closeout 2026-05-07: the producer's `gad telemetry export` now
populates `content_type` on every envelope (planning|code|site|eval|
narrative|meta). The consumer (this script) groups by
`(project, content_type)` so each cohort can train its own LoRA per
slm-learning-079.

Real-world distribution from 156K envelopes:
    planning=131549  meta=24683  code=233  site=10  narrative=5  eval=2

Implication: planning-shape adapters are trainable. Code/site/narrative
are NOT yet — we have <300 envelopes for code, single digits for the
others. This script makes the imbalance visible (eligible_for_training
flag in COHORTS.json) so we don't pretend.

Usage:

    .venv/Scripts/python.exe scripts/build_cohorts.py \\
        --raw-root data/raw \\
        --out-root data/cohorts \\
        --manifest-date 2026-05-06

    # Process latest if no date given
    .venv/Scripts/python.exe scripts/build_cohorts.py
        # picks newest data/raw/<date>/

    # Include meta envelopes (default: filtered out)
    .venv/Scripts/python.exe scripts/build_cohorts.py --include-meta

Decision refs: slm-learning-079 (per-domain ladder), slm-learning-082
(checkpoint registry), slm-learning-086 (data flywheel).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


SCHEMA_V = 1
DEFAULT_FLOOR = 1000  # min envelopes per cohort to be eligible_for_training


# Inference precedence per phase 148 PLAN.md (workstream D-1).
# Used only when the producer didn't populate content_type.
PATH_RULES = [
    # planning
    (re.compile(r"\.planning/.*\.(md|xml|toml|yaml|yml|json)$"), "planning"),
    # narrative / books
    (re.compile(r"(?:^|/)(narrative|souls|books)/"), "narrative"),
    (re.compile(r"\.story\.md$"), "narrative"),
    # site / marketing
    (re.compile(r"^sites/"), "site"),
    (re.compile(r"/marketing/"), "site"),
    (re.compile(r"^apps/[^/]+/site/"), "site"),
    # eval / species
    (re.compile(r"^evals?/"), "eval"),
    (re.compile(r"^species/"), "eval"),
    (re.compile(r"^generations/"), "eval"),
    # code (broad — last because the others claim code-extension files
    # under their dirs first)
    (re.compile(r"\.(ts|tsx|js|jsx|cjs|mjs|py|rs|go|java|rb|swift|kt)$"), "code"),
]


def infer_content_type(envelope: dict) -> str:
    """Returns the content_type. Honors producer-set field; falls back
    to path heuristic on tool_call file_path; default 'planning'."""
    # 1. Pre-set on envelope (passthrough, producer-side win)
    if envelope.get("content_type"):
        return envelope["content_type"]

    # 2. Path heuristic on tool_call file_path (if present)
    content = envelope.get("content")
    if isinstance(content, dict):
        # Various producer shapes: content.tool_call.inputs.file_path,
        # content.input_summary, content.path.
        candidates: list[str] = []
        tc = content.get("tool_call")
        if isinstance(tc, dict):
            inputs = tc.get("inputs") or tc.get("input")
            if isinstance(inputs, dict):
                fp = inputs.get("file_path") or inputs.get("path")
                if fp:
                    candidates.append(str(fp))
        for k in ("file_path", "path", "input_summary"):
            v = content.get(k)
            if isinstance(v, str):
                candidates.append(v)

        for path in candidates:
            for pattern, ct in PATH_RULES:
                if pattern.search(path):
                    return ct

    # 3. Default
    return "planning"


def stream_envelopes(events_path: Path) -> Iterable[dict]:
    with events_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cohort_filename(project: str, content_type: str) -> str:
    safe_proj = re.sub(r"[^a-zA-Z0-9_\-]", "-", project)[:48]
    return f"cohort-{safe_proj}-{content_type}.jsonl"


def build_cohorts(raw_dir: Path, out_root: Path, *,
                  include_meta: bool, floor: int) -> dict:
    manifest_path = raw_dir / "MANIFEST.json"
    events_path = raw_dir / "events.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError(f"no MANIFEST.json in {raw_dir}")
    if not events_path.exists():
        raise FileNotFoundError(f"no events.jsonl in {raw_dir}")

    with manifest_path.open(encoding="utf-8") as f:
        manifest = json.load(f)
    if manifest.get("schema_v") != SCHEMA_V:
        raise ValueError(
            f"manifest schema_v={manifest.get('schema_v')} != expected {SCHEMA_V}"
        )

    out_dir = out_root / raw_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    handles: dict[tuple[str, str], "object"] = {}
    counts: Counter[tuple[str, str]] = Counter()
    inferred_count = 0
    total_seen = 0
    skipped_meta = 0

    try:
        for env in stream_envelopes(events_path):
            total_seen += 1
            project = env.get("project") or "<unknown>"
            ct = infer_content_type(env)
            if not env.get("content_type"):
                inferred_count += 1
            if ct == "meta" and not include_meta:
                skipped_meta += 1
                continue

            key = (project, ct)
            counts[key] += 1
            if key not in handles:
                fname = cohort_filename(project, ct)
                handles[key] = (out_dir / fname).open(
                    "w", encoding="utf-8", errors="replace"
                )
            handles[key].write(json.dumps(env, ensure_ascii=False) + "\n")
    finally:
        for h in handles.values():
            h.close()

    cohorts_summary: list[dict] = []
    for (project, ct), n in counts.most_common():
        fname = cohort_filename(project, ct)
        path = out_dir / fname
        sha = sha256_of(path) if path.exists() else None
        cohorts_summary.append({
            "project": project,
            "content_type": ct,
            "row_count": n,
            "filename": fname,
            "sha256": sha,
            "eligible_for_training": n >= floor,
            "decision_refs": ["slm-learning-079", "slm-learning-082"],
        })

    summary = {
        "schema_v": SCHEMA_V,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "raw_dir": str(raw_dir),
        "raw_manifest_sha256": manifest.get("data_sha256"),
        "raw_row_count": manifest.get("row_count"),
        "envelopes_processed": total_seen,
        "envelopes_inferred": inferred_count,
        "skipped_meta": skipped_meta,
        "include_meta": include_meta,
        "training_eligible_floor": floor,
        "n_cohorts": len(cohorts_summary),
        "n_eligible": sum(1 for c in cohorts_summary if c["eligible_for_training"]),
        "cohorts": cohorts_summary,
        "decision_refs": ["slm-learning-079", "slm-learning-082", "slm-learning-086"],
    }

    summary_path = out_dir / "COHORTS.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--out-root", type=Path, default=Path("data/cohorts"))
    parser.add_argument("--manifest-date", type=str, default=None)
    parser.add_argument("--include-meta", action="store_true")
    parser.add_argument("--floor", type=int, default=DEFAULT_FLOOR,
                        help="Min envelopes per cohort for eligible_for_training")
    args = parser.parse_args()

    if not args.raw_root.exists():
        print(f"ERROR: {args.raw_root} not found", file=sys.stderr)
        return 2

    if args.manifest_date:
        target = args.raw_root / args.manifest_date
    else:
        candidates = sorted(p for p in args.raw_root.iterdir() if p.is_dir())
        if not candidates:
            print(f"ERROR: no dated subdirs in {args.raw_root}", file=sys.stderr)
            return 2
        target = candidates[-1]

    print(f"[cohorts] processing {target} -> {args.out_root / target.name}/")
    summary = build_cohorts(
        target, args.out_root,
        include_meta=args.include_meta,
        floor=args.floor,
    )
    print(f"[cohorts] {summary['envelopes_processed']} envelopes -> "
          f"{summary['n_cohorts']} cohorts ({summary['n_eligible']} eligible at floor={args.floor})")
    print()
    print(f"[cohorts] top cohorts (truncated to 12):")
    for c in summary["cohorts"][:12]:
        eligible = "[OK]" if c["eligible_for_training"] else "[no]"
        print(f"  {eligible} {c['project']:<24} {c['content_type']:<12} {c['row_count']:>8}  {c['filename']}")
    print()
    print(f"[cohorts] wrote {args.out_root / target.name / 'COHORTS.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
