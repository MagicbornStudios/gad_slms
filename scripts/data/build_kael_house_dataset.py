"""Build the Kael-house delta-packet dataset from escape-the-dungeon TRACE.json files.

Walks 21 TRACE.json files at custom_portfolio/vendor/get-anything-done/evals/
escape-the-dungeon/species/{bare,emergent,gad}/v*/TRACE.json, applies the
filter `composite < composite_threshold OR human_review < human_review_threshold`,
classifies each surviving failure into the 8-category taxonomy from
reports/research/kael_house_dataset_scoping_2026-05-08.md, and emits one delta
packet per failure that satisfies schemas/delta_packet.schema.json. Also
synthesizes a retain bank from bare/v2, bare/v3, bare/v5, emergent/v4 and
writes a MANIFEST.md. Decision refs: slm-learning-167, 186, 189, 191, 193,
197, 198. Task: SL-T-04-kael-house-dataset.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_CONTEXT_ID = "qwen-7b-escape-the-dungeon-trajectory"
BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
TASK_SHAPE = "decision_correction"
TARGET_CONTRACT = "game_implementation_step"
DECISION_REFS = [
    "slm-learning-167",
    "slm-learning-186",
    "slm-learning-189",
    "slm-learning-191",
    "slm-learning-193",
    "slm-learning-197",
    "slm-learning-198",
]

DEFAULT_TASK_STATEMENT = (
    "You are building an escape-the-dungeon browser game in TypeScript with "
    "KAPLAY. Your task is to implement the next phase or fix the current "
    "failing phase."
)

CATEGORY_PRESSURE = {
    "blank_screen_render": "tool_action_failure",
    "game_loop_stuck": "decision_correction",
    "tool_state_corruption": "tool_action_failure",
    "parse_exception": "tool_action_failure",
    "budget_exhaustion": "recurring_error",
    "content_missing": "edge_case_fix",
    "incomplete_test_coverage": "human_correction",
}

VALID_PRESSURE = {
    "base_eval_failure",
    "human_correction",
    "fallback_event",
    "contract_violation",
    "tool_action_failure",
    "recurring_error",
    "operator_curated",
    "synthetic_variant",
}


def _normalize_pressure(p: str) -> str:
    if p in VALID_PRESSURE:
        return p
    return "operator_curated"


TRACE_TO_CATEGORY = {
    ("bare", "v1"): "blank_screen_render",
    ("bare", "v2"): "content_missing",
    ("bare", "v3"): "content_missing",
    ("emergent", "v1"): "parse_exception",
    ("emergent", "v2"): "game_loop_stuck",
    ("gad", "v2"): "budget_exhaustion",
    ("gad", "v5"): "blank_screen_render",
    ("gad", "v6"): "blank_screen_render",
    ("gad", "v7"): "game_loop_stuck",
    ("gad", "v8"): "tool_state_corruption",
}

PEER_HINTS = {
    "blank_screen_render": "bare/v2",
    "game_loop_stuck": "bare/v2",
    "tool_state_corruption": "emergent/v2",
    "parse_exception": "bare/v2",
    "budget_exhaustion": "gad/v4",
    "content_missing": "bare/v5",
    "incomplete_test_coverage": "emergent/v4",
}

RETAIN_SOURCES = [
    {
        "species": "bare", "version": "v2",
        "description": "Most playable vertical slice — full title→rooms→combat→dialogue loop works on file:// open.",
        "pedagogical_signal": "Ship a complete vertical slice end-to-end before polishing any single screen. Working game loop > beautiful blank screen.",
        "tags": ["vertical_slice", "playable_loop", "scope_discipline"],
    },
    {
        "species": "bare", "version": "v3",
        "description": "Best UI/UX of round 3 — clean visuals, color coding, readable layout.",
        "pedagogical_signal": "When a single visual pass lands, lock the styling tokens (color, spacing, type-scale) so later phases don't regress them.",
        "tags": ["ui_polish", "visual_consistency", "frontend_quality"],
    },
    {
        "species": "bare", "version": "v5",
        "description": "Highest ingenuity — multi-enemy combat, training-affinity loop, forge UI, pressure mechanics with subtle hints.",
        "pedagogical_signal": "Mechanic depth comes from combinatorial design (forge composition, affinity, multi-enemy positioning), not from feature count.",
        "tags": ["mechanic_depth", "ingenuity", "forge_loop"],
    },
    {
        "species": "emergent", "version": "v4",
        "description": "First full skill-ratcheting cycle — discovered floor 1 is beatable by skipping combat, gathering crystals, crafting spells, then fighting fresh.",
        "pedagogical_signal": "Design the playable loop so the right answer must be DISCOVERED, not stated — discovery loops produce highest user satisfaction.",
        "tags": ["discovery_loop", "skill_ratcheting", "ingenuity"],
    },
]


def sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]


def is_no_signal(trace: dict[str, Any]) -> bool:
    scores = trace.get("scores") or {}
    composite = scores.get("composite")
    hr_obj = trace.get("human_review")
    if isinstance(hr_obj, dict):
        hr_score = hr_obj.get("score")
        if hr_score is None:
            hr_score = hr_obj.get("aggregate_score")
    else:
        hr_score = None
    return composite is None and hr_score is None


def is_infra_failure(trace: dict[str, Any]) -> bool:
    timing = trace.get("timing") or {}
    if timing.get("rate_limited") is True:
        return True
    if timing.get("api_interrupted") is True:
        return True
    return False


def passes_filter(trace: dict[str, Any], composite_thr: float,
                   human_thr: float) -> bool:
    scores = trace.get("scores") or {}
    composite = scores.get("composite")
    hr_obj = trace.get("human_review")
    if isinstance(hr_obj, dict):
        hr_score = hr_obj.get("score")
        if hr_score is None:
            hr_score = hr_obj.get("aggregate_score")
    else:
        hr_score = None
    if composite is None and hr_score is None:
        return False
    if composite is not None and composite < composite_thr:
        return True
    if hr_score is not None and hr_score < human_thr:
        return True
    return False


def extract_failure_evidence(trace: dict[str, Any]) -> str:
    parts: list[str] = []
    rc = trace.get("requirement_coverage") or {}
    gate_notes = rc.get("gate_notes")
    if gate_notes:
        parts.append(f"Gate notes: {gate_notes}")
    hr = trace.get("human_review")
    if isinstance(hr, dict):
        notes = hr.get("notes")
        if notes:
            parts.append(f"Human review: {notes}")
        dims = hr.get("dimensions")
        if isinstance(dims, dict):
            dim_lines = []
            for name, body in dims.items():
                if isinstance(body, dict):
                    score = body.get("score")
                    if score is not None:
                        dim_lines.append(f"  - {name}: {score}")
            if dim_lines:
                parts.append("Rubric dimensions:\n" + "\n".join(dim_lines))
    if not parts:
        parts.append("No evidence captured in trace; manual review required.")
    return "\n\n".join(parts)


def extract_prior_success(trace: dict[str, Any]) -> str:
    rc = trace.get("requirement_coverage") or {}
    fully = rc.get("fully_met")
    partial = rc.get("partially_met")
    not_met = rc.get("not_met")
    coverage = rc.get("coverage_ratio")
    timing = trace.get("timing") or {}
    phases = timing.get("phases_completed")
    tasks = timing.get("tasks_completed")
    bits: list[str] = []
    if phases is not None or tasks is not None:
        bits.append(
            f"Prior steps: {phases or 0} phases completed, "
            f"{tasks or 0} tasks completed."
        )
    if fully is not None or partial is not None or not_met is not None:
        bits.append(
            f"Requirement coverage so far: fully_met={fully}, "
            f"partially_met={partial}, not_met={not_met}, "
            f"coverage_ratio={coverage}."
        )
    if not bits:
        bits.append("Prior steps: no structured progress captured.")
    return " ".join(bits)


def build_minimal_prompt(trace: dict[str, Any]) -> str:
    task_statement = DEFAULT_TASK_STATEMENT
    explicit = (trace.get("requirements_summary") or
                 trace.get("task_description"))
    if isinstance(explicit, str) and explicit.strip():
        task_statement = explicit.strip()
    prior = extract_prior_success(trace)
    evidence = extract_failure_evidence(trace)
    return (
        f"{task_statement}\n\n"
        f"PRIOR PROGRESS:\n{prior}\n\n"
        f"FAILURE EVIDENCE:\n{evidence}"
    )


def _human_review_score(trace: dict[str, Any]) -> float | None:
    hr = trace.get("human_review")
    if not isinstance(hr, dict):
        return None
    score = hr.get("score")
    if score is None:
        score = hr.get("aggregate_score")
    return score


def build_packet(trace: dict[str, Any], species: str, version: str,
                  trace_path: Path) -> dict[str, Any] | None:
    key = (species, version)
    category = TRACE_TO_CATEGORY.get(key)
    if category is None:
        return None
    pressure = _normalize_pressure(CATEGORY_PRESSURE.get(category, "operator_curated"))
    peer = PEER_HINTS.get(category, "")
    peer_text = (
        f"MANUAL_REVIEW_REQUIRED — see retain peer at {peer}"
        if peer else "MANUAL_REVIEW_REQUIRED — needs operator hand-write"
    )
    failure_evidence = extract_failure_evidence(trace)
    minimal_prompt = build_minimal_prompt(trace)
    requirements_version = trace.get("requirements_version")
    schema_v_trace = trace.get("trace_schema_version")
    composite = (trace.get("scores") or {}).get("composite")
    human_score = _human_review_score(trace)
    packet_id = f"qwen-7b-etd-{species}-{version}-{category}"
    packet: dict[str, Any] = {
        "packet_id": packet_id,
        "root_context_id": ROOT_CONTEXT_ID,
        "base_model": BASE_MODEL,
        "task_shape": TASK_SHAPE,
        "skill_id": "kael_game_implementation_step",
        "pressure_source": pressure,
        "failure_type": category,
        "base_output_ref": sha256_path(trace_path),
        "minimal_prompt": minimal_prompt,
        "correction": peer_text,
        "tests": [],
        "retain_tags": [
            "kael-escape-the-dungeon",
            f"failure_{category}",
            f"species_{species}",
        ],
        "target_contract": TARGET_CONTRACT,
        "provenance": {
            "captured_at": dt.datetime.utcnow().isoformat() + "Z",
            "from_run_id": f"{species}/{version}",
            "captured_by": "build_kael_house_dataset.py",
            "review_status": "unreviewed",
        },
        "token_budget": 4096,
        "schema_v": 1,
        "peer_hint": peer,
        "failure_evidence": failure_evidence,
        "trajectory_context": "game_loop_recovery",
        "trace_schema_version_source": schema_v_trace,
        "requirements_version": requirements_version,
        "trace_composite": composite,
        "trace_human_review": human_score,
        "decision_refs": DECISION_REFS,
    }
    return packet


def validate_packet(packet: dict[str, Any]) -> None:
    required = ["packet_id", "root_context_id", "base_model", "task_shape",
                 "minimal_prompt", "correction"]
    for k in required:
        if k not in packet or packet[k] in (None, ""):
            raise ValueError(f"packet missing required field: {k}")
    if packet["task_shape"] not in {
        "function_repair", "function_completion", "tool_action",
        "schema_repair", "format_correction", "decision_correction",
        "edge_case_fix", "documentation", "other",
    }:
        raise ValueError(f"invalid task_shape: {packet['task_shape']}")
    if packet["pressure_source"] not in VALID_PRESSURE:
        raise ValueError(
            f"invalid pressure_source: {packet['pressure_source']}"
        )


def build_retain_rows(source_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    captured_at = dt.datetime.utcnow().isoformat() + "Z"
    for src in RETAIN_SOURCES:
        species = src["species"]
        version = src["version"]
        trace_path = source_root / "species" / species / version / "TRACE.json"
        score = None
        notes = ""
        if trace_path.is_file():
            try:
                tr = json.loads(trace_path.read_text(encoding="utf-8"))
                hr = tr.get("human_review")
                if isinstance(hr, dict):
                    score = hr.get("score")
                    if score is None:
                        score = hr.get("aggregate_score")
                    notes = hr.get("notes") or ""
            except Exception as e:
                notes = f"(failed to read trace: {e})"
        rows.append({
            "retain_id": f"retain-kael-etd-{species}-{version}",
            "source_trace": f"{species}/{version}",
            "source_path": str(trace_path).replace("\\", "/"),
            "description": src["description"],
            "pedagogical_signal": src["pedagogical_signal"],
            "human_review_score": score,
            "human_review_notes": notes,
            "tags": src["tags"] + ["kael-escape-the-dungeon", "retain_positive"],
            "captured_at": captured_at,
            "captured_by": "build_kael_house_dataset.py",
            "schema_v": 1,
        })
    return rows


def write_manifest(out_dir: Path, retain_dir: Path,
                    packets: list[dict[str, Any]],
                    skipped: list[tuple[str, str, str]],
                    n_retain: int, build_cmd: str) -> None:
    by_cat: dict[str, int] = {}
    for p in packets:
        c = p["failure_type"]
        by_cat[c] = by_cat.get(c, 0) + 1
    lines: list[str] = []
    lines.append("# Kael-house dataset manifest (escape-the-dungeon)")
    lines.append("")
    lines.append(f"Built: {dt.datetime.utcnow().isoformat()}Z")
    lines.append(f"Builder: scripts/data/build_kael_house_dataset.py")
    lines.append(f"Root context: {ROOT_CONTEXT_ID}")
    lines.append(f"Base model: {BASE_MODEL}")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- Delta packets: {len(packets)}")
    lines.append(f"- Retain rows: {n_retain}")
    lines.append("")
    lines.append("## Packets by failure_type")
    lines.append("")
    for cat in sorted(by_cat):
        lines.append(f"- {cat}: {by_cat[cat]}")
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    lines.append("- 21 TRACE.json files at "
                  "`custom_portfolio/vendor/get-anything-done/evals/"
                  "escape-the-dungeon/species/{bare,emergent,gad}/v*/TRACE.json`")
    lines.append("- Schema versions handled: None (pre-versioned), 3, 4")
    lines.append("")
    lines.append("## Lineage")
    lines.append("")
    lines.append("- Decision refs: " + ", ".join(DECISION_REFS))
    lines.append("- Filter: `composite < composite_threshold OR "
                  "human_review < human_review_threshold`")
    lines.append("- Skipped: rate-limited (`timing.rate_limited`) and "
                  "API-interrupted (`timing.api_interrupted`) traces are "
                  "infrastructure failures, not agent failures.")
    lines.append("- Skipped: traces with both composite and human_review null "
                  "(no signal).")
    lines.append("")
    if skipped:
        lines.append("## Skipped traces")
        lines.append("")
        lines.append("| species/version | reason |")
        lines.append("|---|---|")
        for sp, ver, reason in skipped:
            lines.append(f"| {sp}/{ver} | {reason} |")
        lines.append("")
    lines.append("## Build command")
    lines.append("")
    lines.append("```")
    lines.append(build_cmd)
    lines.append("```")
    lines.append("")
    lines.append("## Packet ids")
    lines.append("")
    for p in packets:
        lines.append(f"- {p['packet_id']}")
    lines.append("")
    lines.append("## Retain output")
    lines.append("")
    lines.append(f"- {retain_dir}/passed.jsonl ({n_retain} rows)")
    lines.append(f"- {retain_dir}/profile.json")
    lines.append("")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", required=True,
                     help="Path to escape-the-dungeon eval root "
                          "(contains species/{bare,emergent,gad}/v*/TRACE.json)")
    ap.add_argument("--out-dir", required=True,
                     help="Where to write delta_packet json + MANIFEST.md")
    ap.add_argument("--retain-out-dir", required=True,
                     help="Where to write retain bank passed.jsonl + "
                          "profile.json")
    ap.add_argument("--composite-threshold", type=float, default=0.7)
    ap.add_argument("--human-review-threshold", type=float, default=0.65)
    args = ap.parse_args()

    source_root = Path(args.source_root)
    out_dir = Path(args.out_dir)
    retain_dir = Path(args.retain_out_dir)
    species_root = source_root / "species"
    if not species_root.is_dir():
        print(f"ERROR: species root not found at {species_root}",
               file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    retain_dir.mkdir(parents=True, exist_ok=True)

    trace_paths: list[Path] = []
    for species_dir in sorted(species_root.iterdir()):
        if not species_dir.is_dir() or species_dir.name not in {
            "bare", "emergent", "gad",
        }:
            continue
        for version_dir in sorted(species_dir.iterdir()):
            if not version_dir.is_dir() or not version_dir.name.startswith("v"):
                continue
            tp = version_dir / "TRACE.json"
            if tp.is_file():
                trace_paths.append(tp)

    packets: list[dict[str, Any]] = []
    skipped: list[tuple[str, str, str]] = []
    schema_used: dict[str, int] = {"none": 0, "3": 0, "4": 0}

    try:
        import jsonschema
        schema = json.loads((REPO_ROOT / "schemas" /
                              "delta_packet.schema.json").read_text(
            encoding="utf-8"))
        jsonschema_available = True
    except Exception:
        jsonschema = None
        schema = None
        jsonschema_available = False

    for tp in trace_paths:
        species = tp.parent.parent.name
        version = tp.parent.name
        try:
            trace = json.loads(tp.read_text(encoding="utf-8"))
        except Exception as e:
            skipped.append((species, version, f"unreadable: {e}"))
            continue

        sv = trace.get("trace_schema_version")
        if sv is None:
            schema_used["none"] += 1
        else:
            schema_used[str(sv)] = schema_used.get(str(sv), 0) + 1

        if is_no_signal(trace):
            skipped.append((species, version,
                             "no_signal (composite + human_review null)"))
            continue
        if is_infra_failure(trace):
            skipped.append((species, version,
                             "infra_failure (rate_limited or api_interrupted)"))
            continue
        if not passes_filter(trace, args.composite_threshold,
                              args.human_review_threshold):
            skipped.append((species, version,
                             "above_threshold (positive run)"))
            continue

        packet = build_packet(trace, species, version, tp)
        if packet is None:
            skipped.append((species, version,
                             "no_category_mapping"))
            continue

        try:
            validate_packet(packet)
        except ValueError as e:
            skipped.append((species, version, f"validation_failed: {e}"))
            continue

        if jsonschema_available and schema is not None:
            try:
                jsonschema.validate(packet, schema)
            except Exception as e:
                skipped.append((species, version,
                                 f"jsonschema_failed: {e}"))
                continue

        out_path = out_dir / f"{packet['packet_id']}.json"
        out_path.write_text(
            json.dumps(packet, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        packets.append(packet)

    retain_rows = build_retain_rows(source_root)
    retain_jsonl = retain_dir / "passed.jsonl"
    with retain_jsonl.open("w", encoding="utf-8") as f:
        for r in retain_rows:
            f.write(json.dumps(r, ensure_ascii=False))
            f.write("\n")

    profile = {
        "retain_bank_id": "kael-escape-the-dungeon",
        "ts": dt.datetime.utcnow().isoformat() + "Z",
        "source_root": str(source_root).replace("\\", "/"),
        "source_traces": [r["source_trace"] for r in retain_rows],
        "n_retain_rows": len(retain_rows),
        "tags": ["kael-escape-the-dungeon", "retain_positive",
                  "trajectory_step"],
        "decision_refs": DECISION_REFS,
        "schema_v": 1,
    }
    (retain_dir / "profile.json").write_text(
        json.dumps(profile, indent=2),
        encoding="utf-8",
    )

    build_cmd = (
        ".venv/Scripts/python.exe scripts/data/build_kael_house_dataset.py "
        f"--source-root {args.source_root} --out-dir {args.out_dir} "
        f"--retain-out-dir {args.retain_out_dir}"
    )
    write_manifest(out_dir, retain_dir, packets, skipped, len(retain_rows),
                    build_cmd)

    print(f"[kael-house] traces inspected: {len(trace_paths)}")
    print(f"[kael-house] schema versions: {schema_used}")
    print(f"[kael-house] delta packets: {len(packets)}")
    print(f"[kael-house] retain rows: {len(retain_rows)}")
    print(f"[kael-house] skipped: {len(skipped)}")
    for sp, ver, reason in skipped:
        print(f"  - {sp}/{ver}: {reason}")
    print(f"[kael-house] manifest: {out_dir / 'MANIFEST.md'}")
    print(f"[kael-house] jsonschema_available: {jsonschema_available}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
