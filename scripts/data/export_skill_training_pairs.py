#!/usr/bin/env python3
"""
Skill-to-training-data exporter.

Reads a skill YAML (e.g., skills/benchmark-gated-training.skill.yaml) and
emits training data in 4 categories:
  A. Skill-selection examples (given task, which skill_id?)
  B. Skill-execution examples (given task + skill_id, what's next action?)
  C. Skill-failure examples (given violation, what failure mode?)
  D. DPO preference pairs (from prohibitions: aligned vs misaligned)

Usage:
  python export_skill_training_pairs.py --skill <path> [--out-dir <dir>]

Output:
  Writes selection.jsonl, execution.jsonl, failure.jsonl, dpo.jsonl
  Prints row counts per file.
  Exits 0 on success, 2 if skill YAML is malformed.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


def load_skill_yaml(skill_path: str) -> Dict[str, Any]:
    """Load and parse a skill YAML file. Handles multi-document YAML (uses first valid doc)."""
    try:
        with open(skill_path, "r") as f:
            # Use load_all to handle multi-document YAML files, skip invalid ones
            skill = None
            for doc in yaml.safe_load_all(f):
                if isinstance(doc, dict):
                    skill = doc
                    break
            if skill is None:
                raise ValueError("Skill YAML is empty or contains no valid mappings")
        return skill
    except FileNotFoundError:
        print(f"ERROR: Skill file not found: {skill_path}", file=sys.stderr)
        sys.exit(2)
    except yaml.YAMLError as e:
        print(f"ERROR: Malformed YAML in {skill_path}: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: Failed to load skill YAML: {e}", file=sys.stderr)
        sys.exit(2)


def extract_skill_id(skill: Dict[str, Any]) -> str:
    """Extract skill_id from skill dict. Validates presence."""
    skill_id = skill.get("skill_id") or skill.get("id")
    if not skill_id:
        print("ERROR: Skill YAML missing 'skill_id' or 'id' field", file=sys.stderr)
        sys.exit(2)
    return skill_id


def generate_selection_examples(
    skill: Dict[str, Any], skill_id: str
) -> List[Dict[str, Any]]:
    """
    Generate A. Skill-selection examples.
    From skill.applies_when, create examples to select this skill.
    """
    examples = []
    applies_when = skill.get("applies_when", [])
    if not isinstance(applies_when, list):
        applies_when = []

    for scenario in applies_when:
        if isinstance(scenario, str) and scenario.strip():
            examples.append(
                {
                    "input": scenario.strip(),
                    "target": skill_id,
                    "target_format": "classification_label",
                    "tags": ["skill_router"],
                }
            )
    return examples


def generate_execution_examples(
    skill: Dict[str, Any], skill_id: str
) -> List[Dict[str, Any]]:
    """
    Generate B. Skill-execution examples.
    From skill.examples with expected_output.next_step, create execution pairs.
    """
    examples = []
    skill_examples = skill.get("examples", [])
    if not isinstance(skill_examples, list):
        skill_examples = []

    for example in skill_examples:
        if isinstance(example, dict):
            input_info = example.get("input", {})
            if isinstance(input_info, dict):
                dataset = input_info.get("dataset", "")
                target_scale = input_info.get("target_scale", "")
            else:
                dataset = input_info
                target_scale = ""

            expected_output = example.get("expected_output", {})
            if isinstance(expected_output, dict):
                next_step = expected_output.get("next_step", "").strip()
                decision = expected_output.get("decision", "").strip()

                if next_step or decision:
                    input_text = f"Skill: {skill_id}. Dataset: {dataset}. Target scale: {target_scale}."
                    target_text = next_step if next_step else f"Decision: {decision}"
                    examples.append(
                        {
                            "input": input_text,
                            "target": target_text,
                            "target_format": "natural_language",
                            "tags": ["skill_execution"],
                        }
                    )
    return examples


def generate_failure_examples(
    skill: Dict[str, Any], skill_id: str
) -> List[Dict[str, Any]]:
    """
    Generate C. Skill-failure examples.
    From skill.failure_modes, extract description + mode pairs.
    """
    examples = []
    failure_modes = skill.get("failure_modes", [])
    if not isinstance(failure_modes, list):
        failure_modes = []

    for mode in failure_modes:
        if isinstance(mode, dict):
            description = mode.get("description", "").strip()
            mode_label = mode.get("name", "").strip()
            if description and mode_label:
                examples.append(
                    {
                        "input": description,
                        "target": mode_label,
                        "target_format": "classification_label",
                        "tags": ["skill_failure"],
                    }
                )
    return examples


def generate_dpo_examples(skill: Dict[str, Any], skill_id: str) -> List[Dict[str, Any]]:
    """
    Generate D. DPO preference pairs.
    From skill.prohibitions (strings), synthesize chosen (compliant) vs rejected (violates) pairs.
    """
    examples = []
    prohibitions = skill.get("prohibitions", [])
    if not isinstance(prohibitions, list):
        prohibitions = []

    for i, prohibition in enumerate(prohibitions):
        if isinstance(prohibition, str) and prohibition.strip():
            # Extract the "Do NOT" part and the reason/consequence
            prohibition_text = prohibition.strip()
            if prohibition_text.startswith("Do NOT "):
                violation = prohibition_text[7:]  # Remove "Do NOT " prefix

                # Synthesize compliant (chosen) and violating (rejected) outputs
                # Chosen: advises against the bad practice
                chosen_output = f"Do NOT {violation}"
                # Rejected: advocates for the bad practice
                rejected_output = f"Go ahead and {violation}"

                examples.append(
                    {
                        "prompt": f"Training scenario: You are about to {violation}. What should you do?",
                        "chosen": chosen_output,
                        "rejected": rejected_output,
                        "tags": ["skill_dpo"],
                    }
                )
    return examples


def write_jsonl(output_path: Path, rows: List[Dict[str, Any]]) -> int:
    """Write rows to JSONL file. Returns row count."""
    with open(output_path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Export skill YAML to training data JSONL files."
    )
    parser.add_argument(
        "--skill", required=True, help="Path to skill YAML file (e.g., skills/benchmark-gated-training.skill.yaml)"
    )
    parser.add_argument(
        "--out-dir",
        help="Output directory (default: data/skills/<skill_id>/)",
    )

    args = parser.parse_args()

    # Load skill YAML
    skill = load_skill_yaml(args.skill)
    skill_id = extract_skill_id(skill)

    # Determine output directory
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = Path("data") / "skills" / skill_id

    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate training examples
    selection_rows = generate_selection_examples(skill, skill_id)
    execution_rows = generate_execution_examples(skill, skill_id)
    failure_rows = generate_failure_examples(skill, skill_id)
    dpo_rows = generate_dpo_examples(skill, skill_id)

    # Write JSONL files
    selection_count = write_jsonl(out_dir / "selection.jsonl", selection_rows)
    execution_count = write_jsonl(out_dir / "execution.jsonl", execution_rows)
    failure_count = write_jsonl(out_dir / "failure.jsonl", failure_rows)
    dpo_count = write_jsonl(out_dir / "dpo.jsonl", dpo_rows)

    # Print summary
    print(f"Exported skill: {skill_id}")
    print(f"Output directory: {out_dir}")
    print(f"  selection.jsonl: {selection_count} rows")
    print(f"  execution.jsonl: {execution_count} rows")
    print(f"  failure.jsonl: {failure_count} rows")
    print(f"  dpo.jsonl: {dpo_count} rows")
    print(f"Total: {selection_count + execution_count + failure_count + dpo_count} rows")

    sys.exit(0)


if __name__ == "__main__":
    main()
