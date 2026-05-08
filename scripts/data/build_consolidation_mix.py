"""Build a hard+retain consolidation mix from existing hard and retain banks.

Per slm-learning-178/180. The "consolidation" recipe: combine
base-specific hard rows (failures + canonical solutions) with
retain rows (base passes that must be preserved) at a configured
ratio. Empirically validated at 1.5B (slm-learning-173:
hard+retain LIFTED +9.1/+3.0 where hard-only regressed −6.7/−3.7).

This script is the general form of build_retain_mix_dataset.py —
operates on EXISTING hard rows (already-built dataset) + an existing
retain-bank dir, instead of rebuilding from raw eval JSON. Use this
when you want to mix the same hard rows with a different retain bank
(e.g., humaneval-retain for an MBPP-hard arm) or different ratios.

Inputs:
  --hard <path>          — path to existing hard rows.jsonl
  --retain-bank <dir>    — path to retain-bank dir containing passed.jsonl
  --hard-ratio 0.30      — target fraction of total rows that are hard
  --max-rows N           — cap total rows; default = use all hard + scale retain
  --shuffle-seed 42
  --out <dir>            — output directory

Outputs:
  <out>/rows.jsonl       — combined + shuffled
  <out>/profile.json     — n_total, n_hard, n_retain, actual_ratio,
                            sources, lineage

Decision refs: slm-learning-172, 173, 178, 180.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        print(f"ERROR: {path}", file=sys.stderr)
        sys.exit(2)
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hard", required=True)
    ap.add_argument("--retain-bank", required=True,
                    help="dir containing passed.jsonl + profile.json")
    ap.add_argument("--hard-ratio", type=float, default=0.30)
    ap.add_argument("--max-rows", type=int, default=None)
    ap.add_argument("--shuffle-seed", type=int, default=42)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    hard_rows = read_jsonl(Path(args.hard))
    retain_dir = Path(args.retain_bank)
    retain_rows = read_jsonl(retain_dir / "passed.jsonl")
    retain_profile = {}
    rp_path = retain_dir / "profile.json"
    if rp_path.is_file():
        retain_profile = json.loads(rp_path.read_text(encoding="utf-8"))

    n_hard_avail = len(hard_rows)
    n_retain_avail = len(retain_rows)
    if not 0 < args.hard_ratio < 1:
        raise ValueError("hard-ratio must be in (0,1)")

    n_hard = n_hard_avail
    target_total_from_hard = int(round(n_hard / args.hard_ratio))
    n_retain = max(0, min(target_total_from_hard - n_hard, n_retain_avail))

    if args.max_rows and n_hard + n_retain > args.max_rows:
        n_hard = int(round(args.max_rows * args.hard_ratio))
        n_retain = args.max_rows - n_hard
        n_hard = min(n_hard, n_hard_avail)
        n_retain = min(n_retain, n_retain_avail)

    rng = random.Random(args.shuffle_seed)
    rng.shuffle(retain_rows)
    selected = list(hard_rows[:n_hard]) + list(retain_rows[:n_retain])
    rng.shuffle(selected)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as fh:
        for r in selected:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_h = sum(1 for r in selected if r.get("row_kind") == "hard"
              or r.get("source_corpus", "").endswith("base-failures"))
    n_r = sum(1 for r in selected if r.get("row_kind") == "retain"
              or r.get("source_corpus", "").endswith("base-passes"))
    profile = {
        "dataset": "consolidation-mix",
        "ts": dt.datetime.utcnow().isoformat() + "Z",
        "hard_source": args.hard,
        "retain_bank": str(retain_dir),
        "retain_bank_id": retain_profile.get("retain_bank_id"),
        "configured_hard_ratio": args.hard_ratio,
        "actual_hard_ratio": round(n_h / max(1, len(selected)), 4),
        "n_total": len(selected),
        "n_hard": n_h,
        "n_retain": n_r,
        "max_rows_cap": args.max_rows,
        "shuffle_seed": args.shuffle_seed,
        "decision_refs": ["slm-learning-172", "slm-learning-173",
                           "slm-learning-178", "slm-learning-180"],
    }
    (out_dir / "profile.json").write_text(
        json.dumps(profile, indent=2), encoding="utf-8"
    )
    print(f"[consolidation-mix] wrote {rows_path}")
    print(f"[consolidation-mix] n_total={len(selected)} "
          f"hard={n_h} retain={n_r} actual_ratio={profile['actual_hard_ratio']}")


if __name__ == "__main__":
    main()
