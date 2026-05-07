"""
Import + filter the agent_corpus_*.jsonl files emitted by `gad provenance export`.

Pipeline upstream: `gad provenance build` runs the joiner+survival+labeler over
.planning/.trace-archive/*.jsonl (every code edit by every agent, timestamped
and attributed to model+runtime+handoff+task+phase). Then `gad provenance
export` writes the labeled tuples to ../slm_learning/data/agent_corpus_*.jsonl.

This script is the slm_learning side of the bridge. It:
  1. Discovers all agent_corpus_*.jsonl files in data/
  2. Optionally filters by label (default: good only — these are the
     training signals where survival_pct >= 80% AND untouched >= 7d)
  3. Optionally filters by model (e.g. only learn from claude-opus-4-7
     output, not from older-model output we want to surpass)
  4. Splits into train/val by deterministic hash on session_id
  5. Writes data/processed/agent_corpus_<filter>_<split>.jsonl ready
     for the existing SFT trainer

Decision refs: GLOBAL-D-302 (heuristic), GLOBAL-D-304 (sink), and
slm-learning-072 (training data flywheel — this is its first concrete pipe).

Usage:
    .venv/Scripts/python.exe scripts/provenance/import_corpus.py
    .venv/Scripts/python.exe scripts/provenance/import_corpus.py --labels good,churn --train-pct 0.9
    .venv/Scripts/python.exe scripts/provenance/import_corpus.py --since 2026-05-01 --models claude-opus-4-7
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_DIR = DATA_DIR / "processed"


def discover_corpus_files(data_dir: Path, since: dt.date | None = None) -> list[Path]:
    files = sorted(data_dir.glob("agent_corpus_*.jsonl"))
    if since is None:
        return [f for f in files if not f.name.startswith("agent_corpus_manifest")]
    out = []
    for f in files:
        if f.name.startswith("agent_corpus_manifest"):
            continue
        # Filename pattern: agent_corpus_<projectid>_YYYY-MM-DD.jsonl
        try:
            date_str = f.stem.split("_")[-1]
            file_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            if file_date >= since:
                out.append(f)
        except ValueError:
            out.append(f)  # Keep files that don't match pattern (be lenient)
    return out


def deterministic_split(tup: dict, train_pct: float) -> str:
    """Hash-based split so a given session always lands in the same split.

    Falls back to (file_path, ts) when session_id is missing — older corpus
    files predate the provenance pipeline and have null session_id.
    """
    session_id = tup.get("session_id")
    if session_id:
        seed = session_id
    else:
        input_val = tup.get("input", "")
        input_str = input_val if isinstance(input_val, str) else json.dumps(input_val, sort_keys=True)
        seed = f"{tup.get('file_path', '')}:{tup.get('ts', '')}:{input_str[:80]}"
    h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)
    return "train" if (h % 100) / 100 < train_pct else "val"


def filter_tuple(tup: dict, labels: set[str] | None, models: set[str] | None) -> bool:
    if labels and tup.get("label") not in labels:
        return False
    if models and tup.get("model_id") not in models:
        return False
    if not tup.get("output"):  # Skip empty outputs
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=str(DATA_DIR),
                        help="Where the agent_corpus_*.jsonl files live")
    parser.add_argument("--out-dir", default=str(OUT_DIR),
                        help="Where to write processed train/val splits")
    parser.add_argument("--labels", default="good",
                        help="Comma-separated labels to include (default: good only). Use 'all' to skip label filter.")
    parser.add_argument("--models", default="",
                        help="Comma-separated model_ids to include (default: all). e.g. claude-opus-4-7")
    parser.add_argument("--since", default="",
                        help="Only include files dated YYYY-MM-DD or later")
    parser.add_argument("--train-pct", type=float, default=0.9,
                        help="Fraction of sessions assigned to train (rest to val)")
    parser.add_argument("--tag", default="",
                        help="Optional tag appended to output filenames")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary without writing output files")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    if not data_dir.exists():
        print(f"[import] data dir does not exist: {data_dir}", file=sys.stderr)
        return 1

    label_filter: set[str] | None
    if args.labels == "all":
        label_filter = None
    else:
        label_filter = {s.strip() for s in args.labels.split(",") if s.strip()}
    model_filter = {s.strip() for s in args.models.split(",") if s.strip()} or None

    since: dt.date | None = None
    if args.since:
        try:
            since = dt.datetime.strptime(args.since, "%Y-%m-%d").date()
        except ValueError:
            print(f"[import] invalid --since date: {args.since}", file=sys.stderr)
            return 1

    files = discover_corpus_files(data_dir, since=since)
    if not files:
        print(f"[import] no agent_corpus_*.jsonl files in {data_dir} (since={since})")
        return 0

    print(f"[import] reading {len(files)} corpus file(s) from {data_dir}")

    splits: dict[str, list[dict]] = {"train": [], "val": []}
    by_label: Counter = Counter()
    by_model: Counter = Counter()
    by_project: Counter = Counter()
    skipped_empty = 0
    skipped_filter = 0
    total_read = 0

    for f in files:
        with f.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    tup = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total_read += 1
                if not filter_tuple(tup, label_filter, model_filter):
                    if not tup.get("output"):
                        skipped_empty += 1
                    else:
                        skipped_filter += 1
                    continue
                split = deterministic_split(tup, args.train_pct)
                splits[split].append(tup)
                by_label[tup.get("label") or "?"] += 1
                by_model[tup.get("model_id") or "?"] += 1
                by_project[tup.get("project_id") or "?"] += 1

    print(f"\n[import] read {total_read} tuples")
    print(f"  kept:   {sum(len(v) for v in splits.values())}")
    print(f"  skipped (empty output):   {skipped_empty}")
    print(f"  skipped (filter mismatch): {skipped_filter}")
    print(f"\n  by label:   {dict(by_label)}")
    print(f"  by model:   {dict(by_model)}")
    print(f"  by project: {dict(by_project)}")
    print(f"\n  split: train={len(splits['train'])}  val={len(splits['val'])}")

    if args.dry_run:
        print("\n[import] --dry-run, not writing.")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    tag_suffix = f"_{args.tag}" if args.tag else ""
    label_suffix = "_".join(sorted(label_filter)) if label_filter else "all"
    timestamp = dt.datetime.now().strftime("%Y-%m-%d")

    for split_name, tuples in splits.items():
        if not tuples:
            continue
        out_path = out_dir / f"agent_corpus_{label_suffix}{tag_suffix}_{split_name}_{timestamp}.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for tup in tuples:
                fh.write(json.dumps(tup, ensure_ascii=False) + "\n")
        print(f"\n[import] wrote {len(tuples)} tuples -> {out_path.relative_to(ROOT)}")

    # Manifest for downstream consumers
    manifest_path = out_dir / f"agent_corpus_{label_suffix}{tag_suffix}_{timestamp}.manifest.json"
    manifest = {
        "imported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_files": [str(f.relative_to(ROOT)) for f in files],
        "filters": {
            "labels": sorted(label_filter) if label_filter else "all",
            "models": sorted(model_filter) if model_filter else "all",
            "since": str(since) if since else None,
        },
        "counts": {
            "total_read": total_read,
            "kept": sum(len(v) for v in splits.values()),
            "skipped_empty": skipped_empty,
            "skipped_filter": skipped_filter,
            "train": len(splits["train"]),
            "val": len(splits["val"]),
        },
        "by_label": dict(by_label),
        "by_model": dict(by_model),
        "by_project": dict(by_project),
        "decision_refs": ["GLOBAL-D-302", "GLOBAL-D-304", "slm-learning-072"],
    }
    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"\n[import] manifest -> {manifest_path.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
