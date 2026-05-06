"""Ingest GAD telemetry exports into training-shaped SFT pairs.

Workstream A of the cross-instance bridge handoff
(.planning/handoffs/open/h-2026-05-06T09-30-00-slm-learning-bridge.md).

Reads `data/raw/<YYYY-MM-DD>/{events.jsonl, MANIFEST.json}` exported by
`gad telemetry export` (phase 145 producer-side). Validates the
manifest + sha256, filters by role, and emits SFT-ready pairs to
`data/processed/<run-id>/sft.jsonl`.

Pair extraction strategies (one output file per strategy):

- `sft_basic.jsonl`     — instruction = prompt, command = response
                          (skip reasoning; simplest SFT)
- `sft_reasoned.jsonl`  — instruction = prompt, command = reasoning +
                          "\n\n" + response (chain-of-thought SFT)
- `sft_tooluse.jsonl`   — instruction = prior-context summary,
                          command = next tool_call as JSON

Each output schema matches the existing trainer's expected shape
(`instruction` + `command` fields per
src/slm_from_scratch/finetune/data/jsonl_pairs.py). Provenance carries
the source run_id, source manifest sha, and role lineage so we can
trace every pair back to its origin.

Usage:

    .venv/Scripts/python.exe scripts/ingest_gad_telemetry.py \\
        --raw-root data/raw \\
        --out-root data/processed \\
        --manifest-date 2026-05-06

    # or process all dated subdirs found under raw-root:
    .venv/Scripts/python.exe scripts/ingest_gad_telemetry.py \\
        --raw-root data/raw --out-root data/processed --all

Per slm-learning-051 (Continuous Local Delta Lab): the output of this
script is candidate training data; nothing is trained automatically.
The trainer (scripts/18_stage25_finetune.py) is invoked separately
with the appropriate sft_*.jsonl path in its config.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


SCHEMA_V = 1


@dataclass
class IngestStats:
    envelopes_read: int = 0
    by_role: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    runs_seen: int = 0
    pairs_basic: int = 0
    pairs_reasoned: int = 0
    pairs_tooluse: int = 0
    skipped_no_response: int = 0
    skipped_no_prompt: int = 0
    sha_verified: bool = False
    manifest_path: str = ""
    output_files: list[str] = field(default_factory=list)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(manifest_path: Path) -> dict:
    with manifest_path.open(encoding="utf-8") as f:
        manifest = json.load(f)
    if manifest.get("schema_v") != SCHEMA_V:
        raise ValueError(
            f"manifest schema_v={manifest.get('schema_v')} != "
            f"expected {SCHEMA_V} at {manifest_path}"
        )
    return manifest


def verify_data_sha(manifest: dict, data_path: Path) -> bool:
    expected = manifest.get("data_sha256")
    if not expected:
        return False
    actual = sha256_of(data_path)
    if actual != expected:
        raise ValueError(
            f"sha256 mismatch for {data_path}: "
            f"manifest={expected[:12]}... actual={actual[:12]}..."
        )
    return True


def stream_envelopes(events_path: Path) -> Iterable[dict]:
    with events_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


_WORKER_PREFIX_RE = None


def _worker_prefix(run_id: str) -> str:
    """Extract worker prefix from run_id like 'cx-w1-2026-05-04T...' or
    'gd-1924f...-2026-05-01T...'. Falls back to first segment.
    Telemetry envelopes assign a fresh run_id per message burst, so
    pairing prompt -> response requires grouping above the run_id."""
    if not run_id:
        return "<unknown>"
    parts = run_id.split("-")
    if len(parts) >= 2:
        # cx-w1-... -> cx-w1; gd-<uuid>-<iso> -> gd-<uuid prefix>
        if len(parts) >= 4 and parts[0] == "gd":
            return "-".join(parts[:2])
        if parts[0] in ("cx", "claude", "cc"):
            return "-".join(parts[:2])
    return parts[0]


def _session_key(env: dict) -> str:
    """Group key for chronological prompt -> response pairing."""
    proj = env.get("project") or "<no-proj>"
    runtime = env.get("runtime") or "<no-rt>"
    wp = _worker_prefix(env.get("run_id", ""))
    return f"{proj}|{runtime}|{wp}"


def group_by_run(envelopes: Iterable[dict]) -> dict[str, list[dict]]:
    """Group envelopes by SESSION (project + runtime + worker prefix),
    preserving timestamp order so prompt -> response pairing works
    across run_id boundaries.

    The producer assigns one run_id per message burst, so the same
    conversation has different run_ids for prompt, reasoning, and
    response. Grouping by session_key bridges that gap.
    """
    sessions: dict[str, list[dict]] = defaultdict(list)
    for env in envelopes:
        sessions[_session_key(env)].append(env)
    for k in sessions:
        sessions[k].sort(key=lambda e: (e.get("ts", ""), e.get("seq", 0)))
    return sessions


def extract_text(env: dict) -> str | None:
    """Extract plain text from an envelope's content payload.

    Envelope content shapes vary by role; this returns whatever string
    body is present, or None if the envelope is content-less or
    structured-only.
    """
    content = env.get("content")
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        for key in ("text", "value", "body", "message"):
            v = content.get(key)
            if isinstance(v, str) and v.strip():
                return v
    return None


def extract_tool_call(env: dict) -> dict | None:
    """Extract a structured tool_call from an envelope, if present."""
    content = env.get("content")
    if not isinstance(content, dict):
        return None
    if env.get("role") == "tool_call":
        return content
    if content.get("type") == "tool_call":
        return content
    return None


def build_pairs_for_run(run_envelopes: list[dict]) -> dict[str, list[dict]]:
    """Walk one run's envelopes and emit pair-bundles by strategy."""
    pairs = {"basic": [], "reasoned": [], "tooluse": []}
    last_prompt: str | None = None
    pending_reasoning: list[str] = []
    last_context_summary: list[str] = []  # rolling for tooluse

    for env in run_envelopes:
        role = env.get("role")
        text = extract_text(env)

        if role == "prompt":
            last_prompt = text
            pending_reasoning = []
            last_context_summary = []
            continue

        if role == "reasoning":
            if text:
                pending_reasoning.append(text)
                last_context_summary.append(f"[reasoning] {text[:200]}")
            continue

        if role == "response":
            if text and last_prompt:
                pairs["basic"].append({
                    "instruction": last_prompt,
                    "command": text,
                    "provenance": {
                        "run_id": env.get("run_id"),
                        "envelope_id": env.get("id"),
                        "ts": env.get("ts"),
                        "seq": env.get("seq"),
                        "role_lineage": ["prompt", "response"],
                    },
                })
                if pending_reasoning:
                    pairs["reasoned"].append({
                        "instruction": last_prompt,
                        "command": "\n\n".join(pending_reasoning) + "\n\n" + text,
                        "provenance": {
                            "run_id": env.get("run_id"),
                            "envelope_id": env.get("id"),
                            "ts": env.get("ts"),
                            "seq": env.get("seq"),
                            "role_lineage": ["prompt", "reasoning", "response"],
                            "reasoning_chunks": len(pending_reasoning),
                        },
                    })
                last_context_summary.append(f"[response] {text[:200]}")
            pending_reasoning = []
            continue

        if role == "tool_call":
            tc = extract_tool_call(env)
            if tc is not None and last_context_summary:
                pairs["tooluse"].append({
                    "instruction": "\n".join(last_context_summary[-10:]),
                    "command": json.dumps(tc, ensure_ascii=False),
                    "provenance": {
                        "run_id": env.get("run_id"),
                        "envelope_id": env.get("id"),
                        "ts": env.get("ts"),
                        "seq": env.get("seq"),
                        "role_lineage": [*[e.get("role") for e in run_envelopes[:run_envelopes.index(env)] if e.get("role") in {"prompt", "reasoning", "response", "tool_call", "tool_result"}][-5:], "tool_call"],
                    },
                })
            if isinstance(tc, dict):
                tool = tc.get("tool") or tc.get("type")
                last_context_summary.append(f"[tool_call] {tool}")
            continue

        if role == "tool_result":
            if text:
                last_context_summary.append(f"[tool_result] {text[:200]}")
            continue

    return pairs


def write_pairs(out_path: Path, pairs: list[dict]) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    return len(pairs)


def ingest_one_date(raw_dir: Path, out_root: Path) -> IngestStats:
    stats = IngestStats()
    manifest_path = raw_dir / "MANIFEST.json"
    events_path = raw_dir / "events.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError(f"no MANIFEST.json in {raw_dir}")
    if not events_path.exists():
        raise FileNotFoundError(f"no events.jsonl in {raw_dir}")
    stats.manifest_path = str(manifest_path)

    manifest = load_manifest(manifest_path)
    stats.sha_verified = verify_data_sha(manifest, events_path)

    all_pairs = {"basic": [], "reasoned": [], "tooluse": []}
    runs = group_by_run(stream_envelopes(events_path))
    stats.runs_seen = len(runs)

    for run_id, envs in runs.items():
        for env in envs:
            stats.envelopes_read += 1
            stats.by_role[env.get("role", "<unknown>")] += 1
        run_pairs = build_pairs_for_run(envs)
        for k in all_pairs:
            all_pairs[k].extend(run_pairs[k])

    if not all_pairs["basic"]:
        stats.skipped_no_response = stats.by_role.get("prompt", 0)
    if stats.by_role.get("prompt", 0) == 0:
        stats.skipped_no_prompt = stats.envelopes_read

    run_id_label = f"gad-telemetry-{raw_dir.name}"
    out_dir = out_root / run_id_label
    out_dir.mkdir(parents=True, exist_ok=True)

    if all_pairs["basic"]:
        n = write_pairs(out_dir / "sft_basic.jsonl", all_pairs["basic"])
        stats.pairs_basic = n
        stats.output_files.append(str(out_dir / "sft_basic.jsonl"))
    if all_pairs["reasoned"]:
        n = write_pairs(out_dir / "sft_reasoned.jsonl", all_pairs["reasoned"])
        stats.pairs_reasoned = n
        stats.output_files.append(str(out_dir / "sft_reasoned.jsonl"))
    if all_pairs["tooluse"]:
        n = write_pairs(out_dir / "sft_tooluse.jsonl", all_pairs["tooluse"])
        stats.pairs_tooluse = n
        stats.output_files.append(str(out_dir / "sft_tooluse.jsonl"))

    summary_path = out_dir / "INGEST_SUMMARY.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump({
            "ingest_run_id": run_id_label,
            "raw_dir": str(raw_dir),
            "manifest_sha256": manifest.get("data_sha256"),
            "manifest_row_count": manifest.get("row_count"),
            "manifest_role_histogram": manifest.get("role_histogram"),
            "envelopes_read": stats.envelopes_read,
            "by_role": dict(stats.by_role),
            "runs_seen": stats.runs_seen,
            "pairs_basic": stats.pairs_basic,
            "pairs_reasoned": stats.pairs_reasoned,
            "pairs_tooluse": stats.pairs_tooluse,
            "sha_verified": stats.sha_verified,
            "schema_v": SCHEMA_V,
            "output_files": stats.output_files,
        }, f, indent=2)
    stats.output_files.append(str(summary_path))
    return stats


def update_external_manifest(out_root: Path) -> None:
    """Append a 'gad-telemetry' entry to data/external/MANIFEST.json."""
    ext_root = Path("data/external")
    ext_root.mkdir(parents=True, exist_ok=True)
    manifest_path = ext_root / "MANIFEST.json"
    existing: dict = {}
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8") as f:
            raw = json.load(f)
        # Some legacy manifests were lists; normalize to dict shape.
        if isinstance(raw, list):
            existing = {"sources": {}, "legacy_list": raw}
        elif isinstance(raw, dict):
            existing = raw
    sources = existing.setdefault("sources", {})
    sources["gad-telemetry"] = {
        "kind": "telemetry-export",
        "schema_v": SCHEMA_V,
        "ingested_to": str(out_root),
        "producer": "gad telemetry export (phase 145)",
        "consumer_script": "scripts/ingest_gad_telemetry.py",
    }
    existing.setdefault("schema_v", 1)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--out-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--manifest-date", type=str, default=None,
                        help="Single date subdir to process (e.g. 2026-05-06)")
    parser.add_argument("--all", action="store_true",
                        help="Process every dated subdir found under raw-root")
    parser.add_argument("--update-external-manifest", action="store_true",
                        default=True,
                        help="Update data/external/MANIFEST.json (default true)")
    args = parser.parse_args()

    if not args.raw_root.exists():
        print(f"ERROR: raw-root {args.raw_root} does not exist", file=sys.stderr)
        return 2

    targets: list[Path] = []
    if args.manifest_date:
        targets.append(args.raw_root / args.manifest_date)
    elif args.all:
        targets = sorted(p for p in args.raw_root.iterdir() if p.is_dir())
    else:
        # default: process the newest dated subdir
        candidates = sorted(p for p in args.raw_root.iterdir() if p.is_dir())
        if not candidates:
            print(f"ERROR: no dated subdirs in {args.raw_root}", file=sys.stderr)
            return 2
        targets.append(candidates[-1])

    all_stats: list[IngestStats] = []
    for target in targets:
        if not target.exists():
            print(f"WARN: {target} does not exist, skipping", file=sys.stderr)
            continue
        try:
            print(f"[ingest] processing {target} ...")
            stats = ingest_one_date(target, args.out_root)
            all_stats.append(stats)
            print(f"  envelopes={stats.envelopes_read} runs={stats.runs_seen} "
                  f"basic={stats.pairs_basic} reasoned={stats.pairs_reasoned} "
                  f"tooluse={stats.pairs_tooluse} sha_ok={stats.sha_verified}")
        except Exception as e:
            print(f"ERROR processing {target}: {e}", file=sys.stderr)
            return 1

    if args.update_external_manifest and all_stats:
        update_external_manifest(args.out_root)

    print(f"\n[ingest] done. {len(all_stats)} target(s) processed.")
    for s in all_stats:
        print(f"  {s.manifest_path} -> {len(s.output_files)} output(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
