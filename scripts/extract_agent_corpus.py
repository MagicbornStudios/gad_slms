"""Agent corpus extractor — first-wave only.

Walks `.planning/` artifacts (and any --root supplied) looking for outputs
produced by the three first-wave agents:
  - gad-doc-verifier
  - gad-assumptions-analyzer
  - gad-codebase-mapper

Per decision slm-learning-038 we deliberately scope narrow.

Provenance schema is mandatory per slm-learning-041:
  source_file
  agent_type
  input_context_hash
  output
  timestamp
  project_id
  human_approved (bool)
  later_contradicted (bool)
  secret_redacted (bool)
  data_tier {gold | silver | synthetic}

Default tier = silver (frontier-produced, not human-reviewed). Mark gold via
the --gold-manifest path containing newline-separated source_file paths that a
human has reviewed and approved.

Output: data/agent_corpus_<agent>.jsonl per agent.

Usage:
    .venv/Scripts/python.exe scripts/extract_agent_corpus.py \\
        --root . \\
        --out-dir data \\
        --json

    .venv/Scripts/python.exe scripts/extract_agent_corpus.py \\
        --root . \\
        --root ../gad-monorepo \\
        --gold-manifest .planning/corpus-gold.txt
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

# Reuse the secret patterns from extract_tool_use_pairs.py to keep redaction
# consistent across the project.
SECRET_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "[REDACTED_ANTHROPIC_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"\bnpm_[A-Za-z0-9_\-]{30,}"), "[REDACTED_NPM_TOKEN]"),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}"), "[REDACTED_GH_PAT]"),
    (re.compile(r"\bgh[ous]_[A-Za-z0-9]{30,}"), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}"), "[REDACTED_GH_FINEPAT]"),
    (re.compile(r"\bAKIA[A-Z0-9]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bhf_[A-Za-z0-9]{30,}"), "[REDACTED_HF_TOKEN]"),
    (re.compile(r"\bxoxb-[A-Za-z0-9-]{30,}"), "[REDACTED_SLACK_TOKEN]"),
]

PROJECT_ID_DEFAULT = "slm-learning"
SCHEMA_VERSION = "slm-learning-agent-corpus@1"
AGENTS = ("gad-doc-verifier", "gad-assumptions-analyzer", "gad-codebase-mapper")

# codebase-mapper writes one of these filenames per focus area.
MAPPER_FILENAMES = (
    "STACK.md",
    "INTEGRATIONS.md",
    "ARCHITECTURE.md",
    "STRUCTURE.md",
    "CONVENTIONS.md",
    "TESTING.md",
    "CONCERNS.md",
)


def redact(text):
    if not text:
        return text, False
    redacted = False
    for pat, repl in SECRET_PATTERNS:
        new_text = pat.sub(repl, text)
        if new_text != text:
            redacted = True
            text = new_text
    return text, redacted


def hash_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def file_mtime_iso(path: Path):
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def make_record(agent_type, source_file, input_context, output, timestamp, project_id, gold_set, contradicted_set):
    output_redacted, out_red = redact(output)
    input_redacted, in_red = redact(input_context or "")
    return {
        "schema_version": SCHEMA_VERSION,
        "agent_type": agent_type,
        "source_file": str(source_file),
        "input_context_hash": hash_text(input_redacted),
        "input_preview": input_redacted[:280],
        "output": output_redacted,
        "timestamp": timestamp,
        "project_id": project_id,
        "human_approved": str(source_file) in gold_set,
        "later_contradicted": str(source_file) in contradicted_set,
        "secret_redacted": bool(out_red or in_red),
        "data_tier": "gold" if str(source_file) in gold_set else "silver",
    }


# ---- per-agent extractors ---------------------------------------------------


def extract_doc_verifier(root: Path, project_id, gold_set, contradicted_set):
    """Look for .planning/tmp/verify-*.json — the doc-verifier output shape."""
    out = []
    pattern = root / ".planning" / "tmp"
    if not pattern.exists():
        return out
    for p in pattern.glob("verify-*.json"):
        try:
            content = p.read_text(encoding="utf-8")
            payload = json.loads(content)
        except (OSError, json.JSONDecodeError):
            continue
        doc_path = payload.get("doc_path", p.stem)
        # Reconstruct the input context as: "verify {doc_path} for project {project_id}"
        input_context = (
            f"<verify_assignment>\n"
            f"  <doc_path>{doc_path}</doc_path>\n"
            f"  <project_id>{project_id}</project_id>\n"
            f"</verify_assignment>"
        )
        out.append(
            make_record(
                agent_type="gad-doc-verifier",
                source_file=p.relative_to(root),
                input_context=input_context,
                output=json.dumps(payload, indent=2),
                timestamp=file_mtime_iso(p),
                project_id=project_id,
                gold_set=gold_set,
                contradicted_set=contradicted_set,
            )
        )
    return out


def extract_codebase_mapper(root: Path, project_id, gold_set, contradicted_set):
    """Look for .planning/codebase/{STACK,INTEGRATIONS,ARCHITECTURE,...}.md."""
    out = []
    cb_dir = root / ".planning" / "codebase"
    if not cb_dir.exists():
        return out
    for fn in MAPPER_FILENAMES:
        p = cb_dir / fn
        if not p.exists():
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except OSError:
            continue
        focus_area = {
            "STACK.md": "tech",
            "INTEGRATIONS.md": "tech",
            "ARCHITECTURE.md": "arch",
            "STRUCTURE.md": "arch",
            "CONVENTIONS.md": "quality",
            "TESTING.md": "quality",
            "CONCERNS.md": "concerns",
        }[fn]
        input_context = (
            f"<map_assignment>\n"
            f"  <focus_area>{focus_area}</focus_area>\n"
            f"  <output_file>{fn}</output_file>\n"
            f"  <project_id>{project_id}</project_id>\n"
            f"</map_assignment>"
        )
        out.append(
            make_record(
                agent_type="gad-codebase-mapper",
                source_file=p.relative_to(root),
                input_context=input_context,
                output=content,
                timestamp=file_mtime_iso(p),
                project_id=project_id,
                gold_set=gold_set,
                contradicted_set=contradicted_set,
            )
        )
    return out


def extract_assumptions_analyzer(root: Path, project_id, gold_set, contradicted_set):
    """Look for .planning/phases/*-CONTEXT.md — assumptions output is embedded
    in CONTEXT.md per the discuss-phase workflow."""
    out = []
    phases = root / ".planning" / "phases"
    if not phases.exists():
        return out
    for p in phases.rglob("*-CONTEXT.md"):
        try:
            content = p.read_text(encoding="utf-8")
        except OSError:
            continue
        # The output we want is the "Assumptions" section if present.
        # Heuristic: if the file contains '## Assumptions' or 'Confident:'/'Likely:' markers
        if not any(marker in content for marker in ("Assumptions", "Confident:", "Likely:", "Unclear:")):
            continue
        phase_id = p.stem.replace("-CONTEXT", "")
        input_context = (
            f"<assumption_assignment>\n"
            f"  <phase>{phase_id}</phase>\n"
            f"  <project_id>{project_id}</project_id>\n"
            f"</assumption_assignment>"
        )
        out.append(
            make_record(
                agent_type="gad-assumptions-analyzer",
                source_file=p.relative_to(root),
                input_context=input_context,
                output=content,
                timestamp=file_mtime_iso(p),
                project_id=project_id,
                gold_set=gold_set,
                contradicted_set=contradicted_set,
            )
        )
    return out


def load_gold_manifest(path: Optional[Path]):
    if not path or not path.exists():
        return set(), set()
    gold = set()
    contradicted = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("CONTRADICTED:"):
            contradicted.add(line[len("CONTRADICTED:"):].strip())
        else:
            gold.add(line)
    return gold, contradicted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Project root(s) with a .planning/ dir. Repeatable. Defaults to '.'",
    )
    parser.add_argument("--project-id", default=PROJECT_ID_DEFAULT)
    parser.add_argument("--out-dir", default="data")
    parser.add_argument(
        "--gold-manifest",
        default=None,
        help="Path to a manifest of human-approved source_files (one per line).",
    )
    parser.add_argument("--json", action="store_true", help="Emit summary JSON to stdout.")
    args = parser.parse_args()

    roots = [Path(r).resolve() for r in (args.root or ["."])]
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    gold_set, contradicted_set = load_gold_manifest(
        Path(args.gold_manifest).resolve() if args.gold_manifest else None
    )

    by_agent = {a: [] for a in AGENTS}

    for root in roots:
        by_agent["gad-doc-verifier"].extend(
            extract_doc_verifier(root, args.project_id, gold_set, contradicted_set)
        )
        by_agent["gad-codebase-mapper"].extend(
            extract_codebase_mapper(root, args.project_id, gold_set, contradicted_set)
        )
        by_agent["gad-assumptions-analyzer"].extend(
            extract_assumptions_analyzer(root, args.project_id, gold_set, contradicted_set)
        )

    summary = {}
    for agent, records in by_agent.items():
        out_path = out_dir / f"agent_corpus_{agent}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        tier_counts = {"gold": 0, "silver": 0, "synthetic": 0}
        for rec in records:
            tier_counts[rec["data_tier"]] += 1
        summary[agent] = {
            "out": str(out_path.relative_to(Path.cwd())) if out_path.is_relative_to(Path.cwd()) else str(out_path),
            "count": len(records),
            "tiers": tier_counts,
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roots": [str(r) for r in roots],
        "project_id": args.project_id,
        "summary": summary,
    }

    if args.json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Agent corpus extracted @ {payload['generated_at']}")
        print(f"  roots      : {[str(r) for r in roots]}")
        print(f"  project_id : {args.project_id}")
        for agent, info in summary.items():
            print(f"  {agent:<28} -> {info['count']:>4} records ({info['tiers']}) -> {info['out']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
