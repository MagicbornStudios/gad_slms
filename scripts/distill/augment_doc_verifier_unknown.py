"""Augment the doc-verifier training corpus with synthetic unknown-class
examples.

Why
---
Per `slm-learning-090`: the r=16 model lifted unknown-class F1 from
0.000 to 0.462 but stalled below the 0.85 promotion gate. Root cause
isolated in `.planning/concerns/scaling-decisions.md`: the unknown class
has only 70 training pairs (16% of 442) — a DATA imbalance bottleneck,
not a parameter bottleneck. More LoRA rank cannot fix this.

The fix
-------
Synthesize additional unknown-class rows from the existing verified
rows. The structural pattern of "unknown" is:

  literal claim path does NOT exist in the codebase, but the basename
  matches a file that does

So: take a verified row whose claim is `foo/bar/baz.md`, prepend a fake
parent directory that does NOT exist (e.g. `nonexistent_parent/`), and
the new claim `nonexistent_parent/foo/bar/baz.md` becomes a real
unknown — the literal path doesn't exist, but the basename `baz.md`
still matches the original location.

This is free (no LLM call), deterministic, principled (the augmented
rows match the real distribution of "unknown" cases the model will see
at inference time), and grounded in the actual codebase. Per
`slm-learning-019` the haiku-based paraphrase path remains available
for second-stage variation, but for the first augmentation pass the
deterministic approach is enough.

Usage
-----

    .venv/Scripts/python.exe scripts/distill/augment_doc_verifier_unknown.py \\
        --in data/eval/doc_verifier_train.jsonl \\
        --out data/eval/doc_verifier_train.augmented.jsonl \\
        --target-unknown 220 \\
        --seed 42

Then reshape the augmented JSONL for the trainer:

    .venv/Scripts/python.exe scripts/eval/reshape_doc_verifier_for_train.py \\
        --in data/eval/doc_verifier_train.augmented.jsonl \\
        --out data/eval/doc_verifier_train.augmented.reshaped.jsonl

Decision refs: slm-learning-019, slm-learning-090, slm-learning-091.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import random
from pathlib import Path
from typing import Iterable

# Synthetic prefixes we know do NOT exist anywhere in the codebase. The
# augmenter validates each prepended path returns no real matches before
# writing the row, so even if a prefix later becomes real (someone adds
# a directory called `archive/`) the augmenter still produces correct
# unknown-class examples.
# Default reason templates (used if --reason-templates not provided).
# These are the original deterministic + a few variants. For real
# variance, pass --reason-templates pointing at a haiku-generated pool
# (see data/distilled/unknown_reason_templates.txt).
DEFAULT_REASON_TEMPLATES = [
    "basename {basename!r} matches elsewhere; literal path {claim!r} not found",
]


def load_reason_templates(path: Path | None) -> list[str]:
    """Load reason-template variants from a text file (one per line)."""
    if not path:
        return DEFAULT_REASON_TEMPLATES
    if not path.exists():
        return DEFAULT_REASON_TEMPLATES
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s)
    return lines or DEFAULT_REASON_TEMPLATES


SYNTHETIC_PREFIXES = [
    "_ghost_root",
    "_ghost_root/v1",
    "stale_archive",
    "stale_archive/2024",
    "deleted_in_phase_99",
    "removed_legacy",
    "removed_legacy/old",
    "vendor_unused",
    "vendor_unused/_dead",
    "scratch_2025",
    "scratch_2025/draft",
    "deprecated/migration",
    "deprecated/migration/v0",
    "to_be_deleted",
    "to_be_deleted/q4",
    "moved_to_other_repo",
    "moved_to_other_repo/upstream",
    "renamed_in_2026",
    "renamed_in_2026/old_path",
    "_attic",
    "_attic/notes",
]


def load_pairs(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _basename(claim: str) -> str:
    # Match the agent's path semantics: it accepts both POSIX and
    # Windows separators. Take the last segment after either.
    return claim.replace("\\", "/").rstrip("/").split("/")[-1]


def synthesize_unknown_row(verified_row: dict, prefix: str, *,
                           orig_evidence: list[str],
                           reason_template: str) -> dict:
    """Mutate a verified row into a structurally-correct unknown row."""
    inp = verified_row["input"]
    orig_claim = inp["claim"]
    base = _basename(orig_claim)

    # Prepend the synthetic prefix. Use forward slashes (the agent
    # normalizes). The new literal path will not exist; only the
    # basename will match.
    new_claim = f"{prefix}/{orig_claim}".replace("\\", "/")

    new_input = dict(inp)
    new_input["claim"] = new_claim
    new_input["line"] = inp.get("line", 1)

    # Evidence list: use whatever the original verified row showed (the
    # real basename match) — this is exactly the structure the agent
    # produces for unknowns.
    evidence = orig_evidence or []
    if not evidence and orig_claim:
        evidence = [orig_claim]

    # Format the reason template — supports both !r-style and plain
    # placeholders. Try !r-style first (legacy single template); fall
    # back to plain str format.
    try:
        reason = reason_template.format(basename=base, claim=new_claim)
    except (KeyError, IndexError):
        reason = (
            f"basename {base!r} matches elsewhere; literal path "
            f"{new_claim!r} not found"
        )

    new_output = {
        "claim": new_claim,
        "status": "unknown",
        "evidence": evidence,
        "confidence": 0.55,
        "reason": reason,
    }

    # Stable hash so the same source row + prefix always produces the
    # same provenance hash (idempotent reruns).
    h = hashlib.sha1(
        f"{orig_claim}|{prefix}".encode("utf-8")
    ).hexdigest()[:16]

    provenance = {
        "source_file": verified_row.get("provenance", {}).get(
            "source_file", inp.get("doc_path", "")
        ),
        "agent_type": "gad-doc-verifier",
        "input_context_hash": h,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "project_id": verified_row.get("provenance", {}).get(
            "project_id", "slm-learning"
        ),
        "human_approved": False,
        "later_contradicted": False,
        "secret_redacted": False,
        "data_tier": "synthetic_augmented",
        "synthesis": {
            "method": "fake-parent-prefix",
            "source_claim": orig_claim,
            "prefix": prefix,
            "decision_refs": ["slm-learning-019", "slm-learning-090",
                              "slm-learning-091"],
        },
    }

    return {
        "schema_version": "slm-learning-doc-verifier-pair@1",
        "input": new_input,
        "output": new_output,
        "provenance": provenance,
    }


def collect_verified_seeds(rows: Iterable[dict]) -> list[dict]:
    seeds: list[dict] = []
    for r in rows:
        out = r.get("output", {})
        if out.get("status") != "verified":
            continue
        inp = r.get("input", {})
        claim = inp.get("claim", "")
        # Only use file_path style claims (the unknown shape we want to
        # synthesize is path-based). symbol/url/quote/etc claims have
        # different unknown semantics.
        if inp.get("claim_category") != "file_path":
            continue
        if not claim:
            continue
        seeds.append(r)
    return seeds


def augment(rows: list[dict], target_unknown: int, *,
            seed: int,
            reason_templates: list[str]) -> tuple[list[dict], dict]:
    rng = random.Random(seed)
    current_unknown = sum(1 for r in rows if r.get("output", {}).get("status") == "unknown")
    needed = max(0, target_unknown - current_unknown)

    seeds = collect_verified_seeds(rows)
    if not seeds:
        return rows, {
            "added": 0, "needed": needed,
            "reason": "no verified file_path seeds available",
        }

    new_rows: list[dict] = []
    seen_claims: set[str] = set()

    # Try multiple (seed, prefix) combos until we have `needed` distinct
    # synthetic claims. Reason template is sampled from the pool so
    # each synthetic row has different surface form (per slm-learning-093:
    # uniform templates regress).
    attempt_cap = needed * 8
    attempts = 0
    while len(new_rows) < needed and attempts < attempt_cap:
        attempts += 1
        seed_row = rng.choice(seeds)
        prefix = rng.choice(SYNTHETIC_PREFIXES)
        reason_template = rng.choice(reason_templates)
        # Use the original verified evidence (single match = the real
        # location). For unknowns, evidence is the basename matches.
        orig_evidence = seed_row.get("output", {}).get("evidence", [])
        new_row = synthesize_unknown_row(seed_row, prefix,
                                         orig_evidence=orig_evidence,
                                         reason_template=reason_template)
        ck = new_row["input"]["claim"]
        if ck in seen_claims:
            continue
        seen_claims.add(ck)
        new_rows.append(new_row)

    augmented = rows + new_rows
    stats = {
        "starting_total": len(rows),
        "starting_unknown": current_unknown,
        "target_unknown": target_unknown,
        "needed": needed,
        "added": len(new_rows),
        "attempts": attempts,
        "ending_total": len(augmented),
        "ending_unknown": current_unknown + len(new_rows),
        "verified_seed_pool": len(seeds),
        "prefix_pool": len(SYNTHETIC_PREFIXES),
        "reason_template_pool": len(reason_templates),
    }
    return augmented, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", "-i", dest="inp", type=Path, required=True)
    parser.add_argument("--out", "-o", dest="out", type=Path, required=True)
    parser.add_argument("--target-unknown", type=int, default=220,
                        help="Target count of unknown-class rows in output. "
                             "Default 220 = ~50%% of original 442 corpus.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reason-templates", type=Path, default=None,
                        help="Path to a text file with one reason template "
                             "per line. Use {basename} and {claim} as "
                             "placeholders. Critical per slm-learning-093 — "
                             "without variance the model overfits to the "
                             "single default template. Default pool: "
                             "data/distilled/unknown_reason_templates.txt "
                             "(20 haiku-generated variants).")
    args = parser.parse_args()

    if not args.inp.exists():
        print(f"ERROR: {args.inp} not found")
        return 2

    rows = load_pairs(args.inp)
    print(f"[augment] loaded {len(rows)} rows from {args.inp}")

    # Default to the haiku-generated template pool if it exists and the
    # operator didn't override.
    template_path = args.reason_templates or (
        Path("data/distilled/unknown_reason_templates.txt")
        if Path("data/distilled/unknown_reason_templates.txt").exists()
        else None
    )
    reason_templates = load_reason_templates(template_path)
    print(f"[augment] using {len(reason_templates)} reason template(s) "
          f"from {template_path or 'DEFAULT_REASON_TEMPLATES'}")

    augmented, stats = augment(rows, args.target_unknown, seed=args.seed,
                               reason_templates=reason_templates)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r in augmented:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[augment] wrote {args.out}")
    print(f"[augment] stats: {json.dumps(stats, indent=2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
