"""
Pull standard reasoning + code corpuses from HuggingFace.

Drops each dataset under data/external/<name>/ as Parquet files, plus a
companion data/external/<name>/PREVIEW.json with the first 5 examples so you
can eyeball schema without loading the full set.

Run from the repo root with the GPU venv (datasets lib is installed there):

    .venv-gpu/Scripts/python.exe scripts/download_datasets.py [--only NAME ...]

Default downloads everything in DATASETS. Pass --only to pick a subset.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_DIR = ROOT / "data" / "external"

# (key, hf_repo, config, splits, kind)
#   kind tags: "code-eval", "code-train", "math", "reasoning", "commonsense", "instruct"
DATASETS = [
    ("humaneval",   "openai/openai_humaneval",        None,         ["test"],         "code-eval"),
    ("mbpp",        "google-research-datasets/mbpp",  None,         ["train", "test", "validation"], "code-train"),
    ("gsm8k",       "openai/gsm8k",                   "main",       ["train", "test"], "math"),
    ("arc_easy",    "allenai/ai2_arc",                "ARC-Easy",   ["train", "validation", "test"], "reasoning"),
    ("arc_challenge","allenai/ai2_arc",               "ARC-Challenge",["train", "validation", "test"], "reasoning"),
    ("hellaswag",   "Rowan/hellaswag",                None,         ["train", "validation"], "commonsense"),
    ("oasst1",      "OpenAssistant/oasst1",           None,         ["train", "validation"], "instruct"),
]


def download_one(key: str, repo: str, config: str | None, splits: list[str], kind: str, force: bool) -> dict:
    """Fetch one dataset. Returns a manifest entry."""
    from datasets import load_dataset

    out_dir = EXTERNAL_DIR / key
    if out_dir.exists() and not force:
        existing = list(out_dir.glob("*.parquet"))
        if existing:
            return {"key": key, "status": "skipped", "reason": "already present", "files": [p.name for p in existing]}

    out_dir.mkdir(parents=True, exist_ok=True)
    sizes: dict[str, int] = {}
    preview: dict[str, list] = {}

    print(f"[{key}] {repo}{(' / ' + config) if config else ''} -> {out_dir}", flush=True)
    t0 = time.time()

    for split in splits:
        try:
            ds = load_dataset(repo, config, split=split) if config else load_dataset(repo, split=split)
        except Exception as e:
            print(f"  ! split={split} failed: {e}", flush=True)
            continue

        path = out_dir / f"{split}.parquet"
        ds.to_parquet(path)
        sizes[split] = len(ds)
        preview[split] = [ds[i] for i in range(min(5, len(ds)))]
        print(f"  [OK] {split}: {len(ds)} rows -> {path.name}", flush=True)

    (out_dir / "PREVIEW.json").write_text(
        json.dumps(preview, indent=2, default=str), encoding="utf-8"
    )

    elapsed = time.time() - t0
    return {
        "key": key,
        "kind": kind,
        "repo": repo,
        "config": config,
        "splits": sizes,
        "elapsed_sec": round(elapsed, 1),
        "status": "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", help="Restrict to these dataset keys")
    parser.add_argument("--force", action="store_true", help="Re-download even if present")
    args = parser.parse_args()

    targets = DATASETS
    if args.only:
        wanted = set(args.only)
        targets = [d for d in DATASETS if d[0] in wanted]
        missing = wanted - {d[0] for d in DATASETS}
        if missing:
            print(f"Unknown dataset keys: {sorted(missing)}", file=sys.stderr)
            return 2

    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for key, repo, config, splits, kind in targets:
        try:
            manifest.append(download_one(key, repo, config, splits, kind, args.force))
        except Exception as e:
            print(f"[{key}] FAILED: {e}", file=sys.stderr)
            manifest.append({"key": key, "status": "error", "error": str(e)})

    (EXTERNAL_DIR / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    ok = sum(1 for m in manifest if m.get("status") == "ok")
    skipped = sum(1 for m in manifest if m.get("status") == "skipped")
    failed = sum(1 for m in manifest if m.get("status") == "error")
    print(f"\nSummary: ok={ok} skipped={skipped} failed={failed}")
    print(f"Manifest: {EXTERNAL_DIR / 'MANIFEST.json'}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
