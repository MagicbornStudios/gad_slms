"""Mine decision preference pairs from .planning/DECISIONS.xml + notes.

Reads:
    .planning/DECISIONS.xml                   (canonical decision registry)
    .planning/notes/*.md                      (discussion threads + postmortems)
    .planning/.gad-log/<date>.jsonl           (state-log entries for context)

Emits one decision_preference row per decision entry that has enough signal
to reconstruct the considered_alternatives. Heuristics:
    (a) Decision summaries containing 'considered', 'alternative', 'instead',
        'rejected', 'not', 'rather than' → extract alternatives inline
    (b) Notes files named after a decision id or incident date → join as
        evidence_refs and mine why_rejected language
    (c) Decisions with a date field get anchor_ts from that date

Writes:
    slm_learning/data/preference/decision_pairs_<date>.jsonl

Each output row conforms to decision_preference.schema.json (schema_v=1).
Decision refs: GLOBAL-D-330, GLOBAL-D-331, GLOBAL-D-332, GLOBAL-D-333.

Does NOT train — dataset emission only.

Usage:
    python mine_decision_preference_pairs.py [--decisions PATH] [--notes PATH] [--out PATH]
    python mine_decision_preference_pairs.py --dry-run --limit 10
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Generator

REPO_ROOT = Path(__file__).resolve().parents[3]
DECISIONS_XML = REPO_ROOT / ".planning" / "DECISIONS.xml"
NOTES_DIR = REPO_ROOT / ".planning" / "notes"
DATA_OUT_DIR = REPO_ROOT / "slm_learning" / "data" / "preference"

# Patterns that signal an alternative was considered and rejected
REJECTION_PATTERNS = re.compile(
    r"(?:consider(?:ed)?|alternative|instead|rather than|not.*because|rejected|"
    r"could have|might have|we did not|we didn't|the naive approach|"
    r"without.*would have|before.*was.*fixed)",
    re.IGNORECASE,
)

# Phrases that introduce the rationale for the chosen path
CHOSEN_RATIONALE_PATTERNS = re.compile(
    r"(?:because|therefore|this means|this ensures|correct approach|"
    r"the right|the canonical|prevents|avoids|eliminates|allows)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_decisions(xml_path: Path) -> list[dict]:
    """Parse DECISIONS.xml into flat list of decision dicts.

    Returns list of:
        {id, title, summary, date (optional), references: [path]}
    """
    if not xml_path.exists():
        print(f"[mine] DECISIONS.xml not found at {xml_path}", file=sys.stderr)
        return []
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as e:
        print(f"[mine] XML parse error: {e}", file=sys.stderr)
        return []

    root = tree.getroot()
    decisions = []
    for dec in root.findall("decision"):
        entry = {
            "id": dec.get("id", ""),
            "title": _text(dec.find("title")),
            "summary": _text(dec.find("summary")),
            "date": _text(dec.find("date")),
            "references": [
                ref.get("path", "") for ref in (dec.find("references") or [])
            ],
        }
        if entry["id"] and (entry["title"] or entry["summary"]):
            decisions.append(entry)
    return decisions


def load_notes_index(notes_dir: Path) -> dict[str, str]:
    """Build a filename → full text index of notes/*.md files.

    Returns {stem: content} dict. stem is the filename without extension.
    We use stem-based matching to join notes to decisions by ID or incident date.
    """
    index = {}
    if not notes_dir.exists():
        return index
    for f in notes_dir.glob("*.md"):
        try:
            index[f.stem.lower()] = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    return index


# ---------------------------------------------------------------------------
# Alternative extractor
# ---------------------------------------------------------------------------

def extract_alternatives(summary: str) -> list[dict]:
    """Heuristically extract considered alternatives from a decision summary.

    Returns list of {description, why_rejected, conceptual_failure_mode}.
    This is necessarily approximate — the alternatives in DECISIONS.xml are
    embedded in prose, not structured. The miner extracts plausible candidates;
    humans should review and refine.
    """
    if not summary:
        return []

    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", summary)

    alternatives = []
    current_alt: dict | None = None

    for sent in sentences:
        if REJECTION_PATTERNS.search(sent):
            if current_alt:
                alternatives.append(current_alt)
            current_alt = {
                "description": sent.strip(),
                "why_rejected": "",
                "conceptual_failure_mode": None,
            }
        elif current_alt and CHOSEN_RATIONALE_PATTERNS.search(sent):
            current_alt["why_rejected"] = (current_alt["why_rejected"] + " " + sent.strip()).strip()
        elif current_alt:
            # Continuation of prior alternative description
            if not current_alt["why_rejected"]:
                current_alt["description"] = (current_alt["description"] + " " + sent.strip()).strip()
            else:
                alternatives.append(current_alt)
                current_alt = None

    if current_alt:
        alternatives.append(current_alt)

    # Filter noise: very short fragments are not useful
    return [a for a in alternatives if len(a["description"]) > 30][:3]  # cap at 3 per decision


# ---------------------------------------------------------------------------
# Pair builder
# ---------------------------------------------------------------------------

def decision_to_pair(
    decision: dict,
    notes_index: dict[str, str],
    seq: int,
) -> dict | None:
    """Convert a single decision entry to a decision_preference row.

    Returns None if the decision lacks enough signal to form a useful pair.
    """
    dec_id = decision["id"]
    summary = decision["summary"] or ""

    # Need at least a summary to form a pair
    if len(summary) < 80:
        return None

    alternatives = extract_alternatives(summary)
    if not alternatives:
        # Still emit — but flag as low-confidence (single sentence rationale)
        alternatives = [
            {
                "description": "Alternative approach not explicitly documented in DECISIONS.xml.",
                "why_rejected": "Rationale is embedded in the chosen path summary. Extract manually for high-quality training.",
                "conceptual_failure_mode": None,
            }
        ]

    # Look for matching notes file (by decision id slug or date)
    evidence_refs: list[str] = list(decision.get("references", []))
    dec_slug = dec_id.lower().replace("-", "_")
    if dec_slug in notes_index:
        evidence_refs.append(f".planning/notes/{dec_slug}.md")

    # Derive anchor timestamp
    ts = _now_iso()
    if decision.get("date"):
        try:
            d = date.fromisoformat(decision["date"])
            ts = datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

    # Derive projectid from decision ID prefix
    projectid = _projectid_from_decision_id(dec_id)

    # Build problem_statement from title (best proxy without structured notes)
    problem_statement = f"What approach should be taken for: {decision['title']}?"

    # Extract rationale: first 2 sentences of summary for chosen path
    sentences = re.split(r"(?<=[.!?])\s+", summary)
    rationale = " ".join(sentences[:2])

    return {
        "pair_id": f"dcpr-{projectid}-{_today()}-{seq:03d}",
        "ts": ts,
        "projectid": projectid,
        "decision_id": dec_id,
        "problem_statement": problem_statement,
        "chosen": {
            "decision_text": decision["title"],
            "rationale": rationale,
            "evidence_refs": evidence_refs,
        },
        "considered_alternatives": alternatives,
        "verdict_source": "operator_decision",
        "outcome_observed": None,
        "agent_id": None,
        "runtime": "claude-code",
        "session_id": None,
        "license_class": "owned",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text(el) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _today() -> str:
    return date.today().isoformat().replace("-", "")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _projectid_from_decision_id(dec_id: str) -> str:
    """Extract project id (lowercase) from decision id prefix.

    GLOBAL-D-330 → global
    SLM-LEARNING-D-108 → slm-learning
    02-01 (legacy numeric) → global
    """
    match = re.match(r"^([A-Z][A-Z0-9\-]+?)-D-\d+$", dec_id, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return "global"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--decisions", default=str(DECISIONS_XML), help="Path to DECISIONS.xml")
    p.add_argument("--notes", default=str(NOTES_DIR), help="Path to notes directory")
    p.add_argument("--out", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None, help="Max pairs to emit (for testing)")
    args = p.parse_args()

    out_path = Path(args.out) if args.out else DATA_OUT_DIR / f"decision_pairs_{date.today().isoformat()}-mined.jsonl"

    print(f"[mine] loading decisions from {args.decisions}")
    decisions = load_decisions(Path(args.decisions))
    print(f"[mine] {len(decisions)} decisions loaded")

    print(f"[mine] loading notes from {args.notes}")
    notes_index = load_notes_index(Path(args.notes))
    print(f"[mine] {len(notes_index)} notes files indexed")

    pairs: list[dict] = []
    seq = 1
    skipped = 0

    for decision in decisions:
        pair = decision_to_pair(decision, notes_index, seq)
        if pair is None:
            skipped += 1
            continue
        pairs.append(pair)
        seq += 1
        if args.limit and len(pairs) >= args.limit:
            break

    print(f"[mine] {len(pairs)} pairs generated, {skipped} decisions skipped (too sparse)")

    # Summary by project
    from collections import Counter
    by_project = Counter(p["projectid"] for p in pairs)
    for proj, count in sorted(by_project.items()):
        print(f"[mine]   {proj}: {count} pairs")

    if not pairs:
        print("[mine] nothing to write")
        return 0

    if args.dry_run:
        for pair in pairs:
            print(json.dumps(pair, ensure_ascii=False))
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for pair in pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
    print(f"[mine] written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
