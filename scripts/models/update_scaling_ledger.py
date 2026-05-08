#!/usr/bin/env python3
"""
Update the GAD Scaling Ledger with new model entries.

The ledger records honest system growth: base models, adapters, routers, and assemblies
with parameter counts, evaluation results, and promotion status.

Usage:
    python update_scaling_ledger.py \
        --entry-id ladder-7b-hard-fn-norm-2026-05-08 \
        --entry-type adapter \
        --base-model Qwen/Qwen2.5-Coder-7B-Instruct \
        --base-params 7610000000 \
        --adapter-params 18460000 \
        --evals '{"humaneval":0.848,"mbpp":0.823}' \
        --promotion-status staging

    python update_scaling_ledger.py \
        --from experiments/entry_config.yaml

Entry fields are validated against schemas/scaling_ledger.schema.json.
Missing optional fields default to null.
Duplicate entry_id updates the existing entry (idempotent).
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import jsonschema
    import yaml
except ImportError:
    print("ERROR: Required packages not found. Install with:")
    print("  pip install jsonschema pyyaml")
    sys.exit(2)


def load_schema() -> Dict[str, Any]:
    """Load the JSON schema for scaling ledger entries."""
    schema_path = Path(__file__).parent.parent.parent / "schemas" / "scaling_ledger.schema.json"
    if not schema_path.exists():
        print(f"ERROR: Schema file not found at {schema_path}")
        sys.exit(2)
    with open(schema_path) as f:
        return json.load(f)


def load_existing_ledger(ledger_path: Path) -> list:
    """Load existing ledger entries or return empty list if file doesn't exist."""
    if ledger_path.exists():
        with open(ledger_path) as f:
            return json.load(f)
    return []


def validate_entry(entry: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Validate entry against schema. Returns True if valid; prints error and returns False if invalid."""
    try:
        jsonschema.validate(instance=entry, schema=schema)
        return True
    except jsonschema.ValidationError as e:
        print(f"ERROR: Schema validation failed: {e.message}")
        print(f"  Failed at path: {'.'.join(str(p) for p in e.path)}")
        return False


def build_entry_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    """Construct entry dict from command-line arguments."""
    entry = {
        "entry_id": args.entry_id,
        "entry_type": args.entry_type,
        "model_or_system_id": args.model_or_system_id,
        "ts_added": args.ts_added or datetime.utcnow().isoformat() + "Z",
        "base_model": args.base_model,
        "base_params": args.base_params,
        "adapter_params": args.adapter_params,
        "adapter_count": args.adapter_count,
        "active_params_default": args.active_params_default,
        "active_params_max": args.active_params_max,
        "total_deployed_params": args.total_deployed_params,
        "trainable_params_last_run": args.trainable_params_last_run,
        "route_policy": args.route_policy,
        "fallback_models": args.fallback_models or [],
        "evals": args.evals or {},
        "cost_per_success": args.cost_per_success,
        "latency_p50_ms": args.latency_p50_ms,
        "fallback_rate": args.fallback_rate,
        "promotion_status": args.promotion_status,
        "rejection_reason": args.rejection_reason,
        "decision_refs": args.decision_refs or [],
        "notes": args.notes,
    }
    # Remove None values
    return {k: v for k, v in entry.items() if v is not None}


def build_entry_from_file(file_path: Path) -> Dict[str, Any]:
    """Load entry from YAML or JSON file."""
    if not file_path.exists():
        print(f"ERROR: Input file not found: {file_path}")
        sys.exit(2)

    suffix = file_path.suffix.lower()
    try:
        if suffix == ".json":
            with open(file_path) as f:
                return json.load(f)
        elif suffix in [".yaml", ".yml"]:
            with open(file_path) as f:
                return yaml.safe_load(f)
        else:
            print(f"ERROR: Unsupported file format: {suffix}. Use .json or .yaml")
            sys.exit(2)
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        print(f"ERROR: Failed to parse {file_path}: {e}")
        sys.exit(2)


def ensure_required_fields(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all required fields are present. Set defaults where reasonable."""
    required_fields = ["entry_id", "entry_type", "model_or_system_id", "ts_added", "base_model", "base_params", "promotion_status"]

    for field in required_fields:
        if field not in entry or entry[field] is None:
            if field == "ts_added" and field not in entry:
                entry[field] = datetime.utcnow().isoformat() + "Z"
            elif field == "base_params":
                print(f"ERROR: Required field '{field}' is missing")
                sys.exit(2)
            elif field not in ["ts_added"]:
                print(f"ERROR: Required field '{field}' is missing")
                sys.exit(2)

    return entry


def update_ledger(ledger: list, entry: Dict[str, Any]) -> list:
    """
    Add or update entry in ledger (idempotent by entry_id).
    Returns updated ledger.
    """
    entry_id = entry["entry_id"]

    # Find and remove existing entry with same ID
    ledger = [e for e in ledger if e.get("entry_id") != entry_id]

    # Append new/updated entry
    ledger.append(entry)

    # Sort by entry_id for consistency
    ledger.sort(key=lambda e: e.get("entry_id", ""))

    return ledger


def save_ledger(ledger: list, ledger_path: Path) -> None:
    """Write ledger to JSON file."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)
    print(f"[OK] Ledger updated: {ledger_path}")


def render_markdown_summary(ledger: list, output_path: Path) -> None:
    """
    Render human-readable markdown summary of the ledger.
    Groups by entry_type and includes key metrics.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Group by entry_type
    by_type = {}
    for entry in ledger:
        etype = entry.get("entry_type", "unknown")
        if etype not in by_type:
            by_type[etype] = []
        by_type[etype].append(entry)

    lines = [
        "# GAD Scaling Ledger",
        "",
        "Authoritative record of system growth: base models, adapters, and assemblies.",
        "Each entry records honest parameter counts, evaluation results, and promotion status.",
        "",
        f"**Last updated:** {datetime.utcnow().isoformat()}Z",
        "",
    ]

    # Active assemblies (system_assembly entries, canonical or staging)
    active = [e for e in by_type.get("system_assembly", []) if e.get("promotion_status") in ["canonical", "staging"]]
    if active:
        lines.extend([
            "## Active Assemblies",
            "",
            "Currently routable systems:",
            "",
        ])
        for entry in active:
            lines.extend(_render_entry_summary(entry))
        lines.append("")

    # Base model inventory
    bases = by_type.get("base_model", [])
    if bases:
        lines.extend([
            "## Base Model Inventory",
            "",
            "| Model | Params | Status |",
            "|---|---|---|",
        ])
        for entry in bases:
            status = entry.get("promotion_status", "unknown")
            params = entry.get("base_params", 0)
            model_id = entry.get("model_or_system_id", "?")
            lines.append(f"| {model_id} | {params:,} | {status} |")
        lines.append("")

    # Adapter inventory (canonical, staging, rejected)
    adapters_canonical = [e for e in by_type.get("adapter", []) if e.get("promotion_status") == "canonical"]
    adapters_staging = [e for e in by_type.get("adapter", []) if e.get("promotion_status") == "staging"]
    adapters_rejected = [e for e in by_type.get("adapter", []) if e.get("promotion_status") == "rejected"]

    if adapters_canonical:
        lines.extend([
            "## Canonical Adapters",
            "",
            "Promoted to production:",
            "",
        ])
        for entry in adapters_canonical:
            lines.extend(_render_adapter_entry(entry))
        lines.append("")

    if adapters_staging:
        lines.extend([
            "## Staging Adapters",
            "",
            "Awaiting promotion decision:",
            "",
        ])
        for entry in adapters_staging:
            lines.extend(_render_adapter_entry(entry))
        lines.append("")

    if adapters_rejected:
        lines.extend([
            "## Rejected Adapters",
            "",
        ])
        for entry in adapters_rejected:
            lines.extend(_render_adapter_entry(entry, include_rejection_reason=True))
        lines.append("")

    # Cost-efficiency leaderboard
    all_evals = [e for e in ledger if e.get("evals")]
    if all_evals:
        lines.extend([
            "## Evaluation Scores",
            "",
        ])
        # Group by benchmark
        benchmark_scores = {}
        for entry in all_evals:
            for benchmark, score in entry.get("evals", {}).items():
                if benchmark not in benchmark_scores:
                    benchmark_scores[benchmark] = []
                benchmark_scores[benchmark].append((entry.get("entry_id"), score))

        for benchmark in sorted(benchmark_scores.keys()):
            lines.append(f"### {benchmark.upper()}")
            lines.append("")
            lines.append("| Entry | Score |")
            lines.append("|---|---|")
            for entry_id, score in sorted(benchmark_scores[benchmark], key=lambda x: x[1], reverse=True):
                score_str = f"{score:.1%}" if isinstance(score, float) and score <= 1 else str(score)
                lines.append(f"| {entry_id} | {score_str} |")
            lines.append("")

    # Total deployed params over time (chronological)
    with_params = [e for e in ledger if e.get("total_deployed_params")]
    if with_params:
        lines.extend([
            "## Total Deployed Parameters Over Time",
            "",
            "| Entry | Added | Total Params | Active Params |",
            "|---|---|---|---|",
        ])
        for entry in sorted(with_params, key=lambda e: e.get("ts_added", "")):
            entry_id = entry.get("entry_id", "?")
            ts = entry.get("ts_added", "?")[:10]  # Just date
            total_p = entry.get("total_deployed_params", 0)
            active_p = entry.get("active_params_default", "?")
            lines.append(f"| {entry_id} | {ts} | {total_p:,} | {active_p} |")
        lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    print(f"[OK] Markdown summary: {output_path}")


def _render_entry_summary(entry: Dict[str, Any]) -> list:
    """Render a single entry as markdown lines."""
    lines = []
    entry_id = entry.get("entry_id", "?")
    model_id = entry.get("model_or_system_id", "?")
    status = entry.get("promotion_status", "?")
    lines.append(f"### {entry_id}")
    lines.append(f"- **Model:** {model_id}")
    lines.append(f"- **Status:** {status}")
    if entry.get("total_deployed_params"):
        lines.append(f"- **Total params:** {entry['total_deployed_params']:,}")
    if entry.get("evals"):
        evals_str = ", ".join(f"{k}: {v}" for k, v in entry["evals"].items())
        lines.append(f"- **Evals:** {evals_str}")
    if entry.get("notes"):
        lines.append(f"- **Notes:** {entry['notes']}")
    lines.append("")
    return lines


def _render_adapter_entry(entry: Dict[str, Any], include_rejection_reason: bool = False) -> list:
    """Render an adapter entry as markdown lines."""
    lines = []
    entry_id = entry.get("entry_id", "?")
    base = entry.get("base_model", "?")
    adapter_params = entry.get("adapter_params", 0)
    status = entry.get("promotion_status", "?")

    lines.append(f"#### {entry_id}")
    lines.append(f"- **Base:** {base}")
    lines.append(f"- **Adapter params:** {adapter_params:,}")
    lines.append(f"- **Status:** {status}")

    if include_rejection_reason and entry.get("rejection_reason"):
        lines.append(f"- **Reason:** {entry['rejection_reason']}")

    if entry.get("evals"):
        evals_str = ", ".join(f"{k}: {v}" for k, v in entry["evals"].items())
        lines.append(f"- **Evals:** {evals_str}")

    if entry.get("decision_refs"):
        refs_str = ", ".join(entry["decision_refs"])
        lines.append(f"- **Decisions:** {refs_str}")

    lines.append("")
    return lines


def main():
    parser = argparse.ArgumentParser(
        description="Update the GAD Scaling Ledger with a new entry.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--from",
        dest="from_file",
        type=Path,
        help="Load entry from YAML or JSON file",
    )
    input_group.add_argument(
        "--entry-id",
        help="Unique kebab-case identifier",
    )

    parser.add_argument("--entry-type", help="Type: base_model|adapter|router|fallback_route|skill_bundle|system_assembly")
    parser.add_argument("--model-or-system-id", help="Canonical model or system name")
    parser.add_argument("--ts-added", help="ISO8601 timestamp (defaults to now)")
    parser.add_argument("--base-model", help="Reference to base model")
    parser.add_argument("--base-params", type=int, help="Parameters in dense base")
    parser.add_argument("--adapter-params", type=int, help="Sum of adapter parameters")
    parser.add_argument("--adapter-count", type=int, help="Number of adapters")
    parser.add_argument("--active-params-default", help="Default active params (int or string)")
    parser.add_argument("--active-params-max", type=int, help="Maximum active params")
    parser.add_argument("--total-deployed-params", type=int, help="Total system params")
    parser.add_argument("--trainable-params-last-run", type=int, help="Trainable params in last training")
    parser.add_argument("--route-policy", help="router-selected|merged|stacked|single|fallback|moe")
    parser.add_argument("--fallback-models", type=json.loads, help='JSON list of fallback model IDs')
    parser.add_argument("--evals", type=json.loads, help='JSON object of benchmark scores')
    parser.add_argument("--cost-per-success", type=float, help="USD cost per successful task")
    parser.add_argument("--latency-p50-ms", type=int, help="Median latency in ms")
    parser.add_argument("--fallback-rate", type=float, help="Fraction falling back (0.0-1.0)")
    parser.add_argument("--promotion-status", help="candidate|staging|canonical|rejected|salvage_candidate|negative_teacher|skeleton_adapter|quarantined")
    parser.add_argument("--rejection-reason", help="Reason if rejected")
    parser.add_argument("--decision-refs", type=json.loads, help='JSON list of decision IDs (e.g., ["slm-learning-001"])')
    parser.add_argument("--notes", help="Free-text notes")
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=Path(__file__).parent.parent.parent / "reports" / "scaling" / "gad_scaling_ledger.json",
        help="Path to ledger JSON file",
    )
    parser.add_argument(
        "--markdown-path",
        type=Path,
        default=Path(__file__).parent.parent.parent / "reports" / "scaling" / "gad_scaling_ledger.md",
        help="Path to output markdown summary",
    )

    args = parser.parse_args()

    # Load schema
    schema = load_schema()

    # Build entry from args or file
    if args.from_file:
        entry = build_entry_from_file(args.from_file)
    else:
        entry = build_entry_from_args(args)

    # Ensure required fields
    entry = ensure_required_fields(entry)

    # Validate
    if not validate_entry(entry, schema):
        sys.exit(2)

    # Load existing ledger
    ledger = load_existing_ledger(args.ledger_path)

    # Update ledger
    ledger = update_ledger(ledger, entry)

    # Save
    save_ledger(ledger, args.ledger_path)
    render_markdown_summary(ledger, args.markdown_path)

    print(f"[OK] Entry added/updated: {entry['entry_id']}")
    sys.exit(0)


if __name__ == "__main__":
    main()
