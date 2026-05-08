#!/usr/bin/env python3
"""
check_trace_score_consistency.py

Walks every version dir under a given eval-species root and flags
any case where TRACE.json composite and SCORE.md composite differ
by more than the tolerance.

Per AGENTS.md "Cross-Project Eval Scoring", TRACE.json is the
authoritative human-reviewed score. SCORE.md is discipline-only
(auto-derived from git/planning-doc metrics, excludes human-
playability deductions). When they disagree, cite TRACE.json.

Usage:
    python scripts/eval/check_trace_score_consistency.py \\
        C:/Users/benja/Documents/custom_portfolio/vendor/get-anything-done/evals/escape-the-dungeon/species

Output:
    - Per-version row: version_id | trace_composite | score_composite | delta | verdict
    - Exit 0 if all rows consistent (delta <= tolerance)
    - Exit 1 if any row exceeds tolerance (paper integrity warning)
    - Exit 2 on missing TRACE.json (TRACE is required; SCORE is optional)

The script is read-only and stdlib-only; safe to run anywhere.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TOLERANCE = 0.05


def parse_score_md_composite(score_md_path: Path) -> float | None:
    """Extract composite from `### **Composite: 0.935**` line."""
    if not score_md_path.is_file():
        return None
    text = score_md_path.read_text(encoding="utf-8")
    m = re.search(r"\*\*Composite:\s*([0-9]*\.?[0-9]+)\*\*", text)
    if m:
        return float(m.group(1))
    return None


def parse_trace_composite(trace_path: Path) -> tuple[float | None, float | None, str]:
    """
    Read TRACE.json and return (composite, human_review_score, gate_notes_excerpt).
    Composite may be null for rate-limited / unscored runs — that's not an error.
    """
    if not trace_path.is_file():
        return (None, None, "")
    try:
        data = json.loads(trace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return (None, None, "(TRACE.json invalid JSON)")

    scores = data.get("scores") or {}
    composite = scores.get("composite")
    if composite is not None and not isinstance(composite, (int, float)):
        composite = None

    human_review_score = None
    if isinstance(scores, dict):
        hr = scores.get("human_review")
        if isinstance(hr, (int, float)):
            human_review_score = hr

    if human_review_score is None:
        hr_obj = data.get("human_review")
        if isinstance(hr_obj, dict):
            score = hr_obj.get("score")
            if isinstance(score, (int, float)):
                human_review_score = score

    gate_notes = ""
    rc = data.get("requirement_coverage") or {}
    if isinstance(rc, dict):
        gate_notes = rc.get("gate_notes") or ""

    return (composite, human_review_score, gate_notes[:80])


def main(species_root: Path) -> int:
    if not species_root.is_dir():
        print(f"[ERROR] not a directory: {species_root}", file=sys.stderr)
        return 2

    rows: list[tuple[str, float | None, float | None, float | None, str, str]] = []
    missing_trace_count = 0
    drift_count = 0

    for species_dir in sorted(species_root.iterdir()):
        if not species_dir.is_dir():
            continue
        for version_dir in sorted(species_dir.iterdir()):
            if not version_dir.is_dir():
                continue
            trace_path = version_dir / "TRACE.json"
            score_path = version_dir / "SCORE.md"

            if not trace_path.is_file():
                # No TRACE.json: not necessarily a failure for archive/template dirs
                if score_path.is_file():
                    missing_trace_count += 1
                    rows.append((
                        f"{species_dir.name}/{version_dir.name}",
                        None,
                        parse_score_md_composite(score_path),
                        None,
                        "",
                        "MISSING_TRACE",
                    ))
                continue

            trace_comp, hr_score, gate_notes = parse_trace_composite(trace_path)
            score_comp = parse_score_md_composite(score_path)

            if trace_comp is None and score_comp is None:
                verdict = "BOTH_NULL"
            elif trace_comp is None:
                verdict = "TRACE_NULL"
            elif score_comp is None:
                verdict = "SCORE_MISSING"
            else:
                delta = abs(trace_comp - score_comp)
                if delta <= TOLERANCE:
                    verdict = "OK"
                else:
                    verdict = f"DRIFT_{delta:.3f}"
                    drift_count += 1

            rows.append((
                f"{species_dir.name}/{version_dir.name}",
                trace_comp,
                score_comp,
                hr_score,
                gate_notes,
                verdict,
            ))

    print(f"{'version':<22} {'trace':>8} {'score':>8} {'hr':>5}  {'verdict':<14} gate_notes")
    print("-" * 100)
    for label, trace_comp, score_comp, hr_score, gate_notes, verdict in rows:
        trace_s = f"{trace_comp:.3f}" if trace_comp is not None else "-"
        score_s = f"{score_comp:.3f}" if score_comp is not None else "-"
        hr_s = f"{hr_score:.2f}" if hr_score is not None else "-"
        print(f"{label:<22} {trace_s:>8} {score_s:>8} {hr_s:>5}  {verdict:<14} {gate_notes}")

    print("-" * 100)
    print(f"versions: {len(rows)}  drift: {drift_count}  missing-trace-with-score: {missing_trace_count}")

    if drift_count > 0:
        print(
            f"\n[WARN] {drift_count} version(s) drift > {TOLERANCE}. "
            "Cite TRACE.json composite in any paper-shaped doc.",
            file=sys.stderr,
        )
        return 1
    if missing_trace_count > 0:
        print(
            f"\n[INFO] {missing_trace_count} version(s) have SCORE.md but no TRACE.json. "
            "These cannot be cited in paper-shaped docs.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
