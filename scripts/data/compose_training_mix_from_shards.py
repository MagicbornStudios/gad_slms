"""Compose a training rows.jsonl from a context_root + delta_packet shard + retain bank.

Per slm-learning-186/188. The "compose" step is what turns sharded
delta packets into a usable training file, materializing
shared_instruction + delta.minimal_prompt → delta.correction at load
time so storage stays compressed.

Inputs:
  --root <id>            — context_root id (file at data/context_roots/<id>.json)
  --packet-dir <dir>     — dir of delta_packet JSON files (or a glob)
  --retain-bank <dir>    — retain bank dir (containing passed.jsonl)
  --hard-ratio 0.30      — fraction of total rows that are hard
  --max-rows N           — cap total rows
  --out <dir>            — output directory

Outputs:
  <out>/rows.jsonl       — composed rows in the SFTTrainer-compatible format
                            ({"input": ..., "target": ...})
  <out>/profile.json     — n_total, n_hard, n_retain, source ids, lineage

Each composed hard row:
  input  = root.shared_instruction + "\n\n" + packet.minimal_prompt
  target = packet.correction

Each composed retain row:
  input  = root.shared_instruction + "\n\n" + retain.input
  target = retain.target

Decision refs: slm-learning-186, 187, 188.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_root(root_id: str) -> dict:
    p = REPO_ROOT / "data" / "context_roots" / f"{root_id}.json"
    if not p.is_file():
        raise SystemExit(f"context_root not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def load_packets(packet_dir: Path) -> list[dict]:
    packets = []
    for p in sorted(packet_dir.glob("*.json")):
        if p.name == "_index.json":
            continue
        try:
            packets.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return packets


def load_retain(retain_dir: Path) -> list[dict]:
    p = retain_dir / "passed.jsonl"
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--packet-dir", required=True)
    ap.add_argument("--retain-bank", required=True)
    ap.add_argument("--hard-ratio", type=float, default=0.30)
    ap.add_argument("--max-rows", type=int, default=None)
    ap.add_argument("--shuffle-seed", type=int, default=42)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = load_root(args.root)
    packets = load_packets(Path(args.packet_dir))
    retain_rows = load_retain(Path(args.retain_bank))

    shared = root.get("shared_instruction", "")

    hard_rows = [
        {
            "input": (shared + "\n\n" + p.get("minimal_prompt", "")).rstrip(),
            "target": p.get("correction", ""),
            "row_kind": "hard",
            "packet_id": p.get("packet_id"),
            "source_corpus": "delta_packets",
        }
        for p in packets
    ]

    n_hard = len(hard_rows)
    if not 0 < args.hard_ratio < 1:
        raise SystemExit("hard-ratio must be in (0,1)")
    target_total = int(round(n_hard / args.hard_ratio))
    n_retain = max(0, min(target_total - n_hard, len(retain_rows)))
    if args.max_rows and n_hard + n_retain > args.max_rows:
        n_hard_cap = int(round(args.max_rows * args.hard_ratio))
        n_retain = args.max_rows - n_hard_cap
        n_hard_cap = min(n_hard_cap, n_hard)
        n_retain = min(n_retain, len(retain_rows))
        hard_rows = hard_rows[:n_hard_cap]
        n_hard = n_hard_cap

    rng = random.Random(args.shuffle_seed)
    rng.shuffle(retain_rows)
    retain_selected = []
    for r in retain_rows[:n_retain]:
        retain_selected.append({
            "input": (shared + "\n\n" + r.get("input", "")).rstrip(),
            "target": r.get("target", ""),
            "row_kind": "retain",
            "packet_id": r.get("id"),
            "source_corpus": "retain_bank",
        })

    composed = hard_rows + retain_selected
    rng.shuffle(composed)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as fh:
        for row in composed:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    profile = {
        "ts": dt.datetime.utcnow().isoformat() + "Z",
        "root_context_id": args.root,
        "packet_dir": str(args.packet_dir),
        "retain_bank": str(args.retain_bank),
        "n_total": len(composed),
        "n_hard": n_hard,
        "n_retain": len(retain_selected),
        "configured_hard_ratio": args.hard_ratio,
        "actual_hard_ratio": round(n_hard / max(1, len(composed)), 4),
        "shuffle_seed": args.shuffle_seed,
        "decision_refs": ["slm-learning-186", "slm-learning-187",
                           "slm-learning-188"],
    }
    (out_dir / "profile.json").write_text(json.dumps(profile, indent=2),
                                            encoding="utf-8")
    print(f"[compose] wrote {rows_path}")
    print(f"[compose] n_total={len(composed)} hard={n_hard} retain={len(retain_selected)} "
          f"actual_ratio={profile['actual_hard_ratio']}")


if __name__ == "__main__":
    main()
