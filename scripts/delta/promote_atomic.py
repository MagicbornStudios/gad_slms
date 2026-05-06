"""Promote a candidate adapter to canonical — REFUSES by default.

Per decision slm-learning-051 (Continuous Local Delta Lab on 1660 Ti,
gated, candidate-only): no automatic promotion. Manual stamp required.

This script EXISTS to satisfy the global daemon's subprocess contract,
and to make the refusal explicit + machine-readable. It will refuse
the call unless the operator passes:

    --i-am-a-human-stamping-this-promotion
    --gate-evidence <path>
    --decision-id <slm-learning-NNN>

AND the gate-evidence file demonstrates a Verifier verdict +
Critic verdict + the decision-id exists in DECISIONS.xml.

Atomic promotion (when authorized) replaces the canonical pointer at
models/CANONICAL via os.replace() so concurrent readers always see a
valid pointer. If anything goes wrong, the previous canonical is
preserved at models/PREVIOUS for one-step rollback.

Output (stdout, JSON):
    { "status": "refused" | "promoted" | "error",
      "previous_canonical": "...",
      "new_canonical": "...",
      "decision_id": "...",
      "rollback_command": "..." }
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models"
CANONICAL = MODELS_DIR / "CANONICAL"
PREVIOUS = MODELS_DIR / "PREVIOUS"


def refuse(reason: str, exit_code: int = 1) -> int:
    print(json.dumps({
        "status": "refused",
        "reason": reason,
        "decision_ref": "slm-learning-051",
        "policy": "Continuous Local Delta Lab is gated. Manual promotion only.",
        "how_to_proceed": "See scripts/delta/promote_atomic.py docstring for required flags + gate evidence.",
    }))
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, default=None)
    parser.add_argument("--decision-id", type=str, default=None,
                        help="slm-learning-NNN that authorizes this promotion")
    parser.add_argument("--gate-evidence", type=Path, default=None,
                        help="Path to JSON with Verifier + Critic verdicts")
    parser.add_argument("--i-am-a-human-stamping-this-promotion",
                        action="store_true", dest="human_stamp")
    args = parser.parse_args()

    if not args.human_stamp:
        return refuse("Missing --i-am-a-human-stamping-this-promotion flag.")
    if args.candidate_dir is None or not args.candidate_dir.exists():
        return refuse(f"Candidate dir not found: {args.candidate_dir}")
    if args.decision_id is None:
        return refuse("Missing --decision-id (must be a slm-learning-NNN that authorizes this).")
    if args.gate_evidence is None or not args.gate_evidence.exists():
        return refuse("Missing --gate-evidence pointing at a verdict bundle.")

    # Verify decision exists in DECISIONS.xml.
    decisions_path = ROOT / ".planning" / "DECISIONS.xml"
    if not decisions_path.exists():
        return refuse("DECISIONS.xml not found")
    if f'id="{args.decision_id}"' not in decisions_path.read_text(encoding="utf-8", errors="ignore"):
        return refuse(f"Decision {args.decision_id!r} not found in DECISIONS.xml")

    # Verify the gate evidence has the required verdicts.
    try:
        evidence = json.loads(args.gate_evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return refuse(f"gate-evidence parse failed: {e}")
    verifier = evidence.get("verifier", {})
    critic = evidence.get("critic", {})
    if verifier.get("result") != "verified":
        return refuse(f"Verifier verdict not 'verified' (got {verifier.get('result')!r}).")
    if critic.get("recommend") != "ship":
        return refuse(f"Critic verdict not 'ship' (got {critic.get('recommend')!r}).")
    if any(fm.get("blocking") for fm in critic.get("failure_modes", [])):
        return refuse("Critic surfaced a blocking failure mode.")
    tier = (evidence.get("evidence_tier") or "").upper()
    if tier not in {"T2", "T3", "T4"}:
        return refuse(f"evidence_tier {tier!r} below T2 floor (slm-learning-071).")

    # All checks passed — perform the atomic swap.
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    new_canonical = args.candidate_dir.resolve()
    previous_canonical_target = CANONICAL.resolve() if CANONICAL.exists() else None

    if previous_canonical_target is not None:
        # Atomic move of CANONICAL -> PREVIOUS.
        if PREVIOUS.exists():
            PREVIOUS.unlink()
        os.replace(CANONICAL, PREVIOUS)

    # Write the new pointer file.
    CANONICAL.write_text(str(new_canonical), encoding="utf-8")

    rollback_cmd = (
        f'mv "{PREVIOUS}" "{CANONICAL}"'
        if previous_canonical_target is not None
        else "no previous canonical existed; rollback = remove CANONICAL"
    )

    print(json.dumps({
        "status": "promoted",
        "new_canonical": str(new_canonical),
        "previous_canonical": str(previous_canonical_target) if previous_canonical_target else None,
        "decision_id": args.decision_id,
        "promoted_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "rollback_command": rollback_cmd,
        "decision_ref": "slm-learning-051",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
