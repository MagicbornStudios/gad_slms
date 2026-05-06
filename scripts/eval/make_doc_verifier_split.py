"""Build held-out eval split for the doc-verifier specialist.

Per ChatGPT priority directive 2026-05-06: "Before training
doc-verifier: create a held-out split from the 739 bootstrapped pairs,
report label balance: verified/refuted/unknown, train rank 8 first,
rank 16 only if underfit."

Strategy:

1. Load both bootstrapped corpora:
   - data/agent_corpus_gad-doc-verifier.bootstrapped.jsonl (475)
   - data/agent_corpus_gad-doc-verifier.bootstrapped.multiroot.jsonl (264)
2. Deduplicate by sha256(input.claim + input.doc_path).
3. Stratify by output.status (verified/refuted/unknown) so the
   split preserves label balance.
4. Sample N (default 50) for hold-out, rest goes to train.
5. Write splits to:
   - data/eval/doc_verifier_holdout.jsonl
   - data/eval/doc_verifier_train.jsonl
6. Emit a profile JSON to experiments/profiles/doc_verifier.split.json
   with label balance + recommended LoRA rank.

Usage:

    .venv/Scripts/python.exe scripts/eval/make_doc_verifier_split.py \\
        --holdout-n 50 \\
        --seed 42

Decision refs: slm-learning-051, slm-learning-071 (T1 evidence tier
with sample size declared).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCES = [
    ROOT / "data" / "agent_corpus_gad-doc-verifier.bootstrapped.jsonl",
    ROOT / "data" / "agent_corpus_gad-doc-verifier.bootstrapped.multiroot.jsonl",
]
HOLDOUT_PATH = ROOT / "data" / "eval" / "doc_verifier_holdout.jsonl"
TRAIN_PATH = ROOT / "data" / "eval" / "doc_verifier_train.jsonl"
PROFILE_PATH = ROOT / "experiments" / "profiles" / "doc_verifier.split.json"


def load(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for p in paths:
        if not p.exists():
            print(f"[split] WARN: {p} not found, skipping")
            continue
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        print(f"[split] loaded {len(rows)} rows after {p.name}")
    return rows


def dedup_key(row: dict) -> str:
    inp = row.get("input", {})
    claim = inp.get("claim", "") if isinstance(inp, dict) else ""
    doc = inp.get("doc_path", "") if isinstance(inp, dict) else ""
    return hashlib.sha256(f"{doc}||{claim}".encode("utf-8", errors="replace")).hexdigest()


def stratified_sample(rows: list[dict], n_holdout: int, seed: int = 42) -> tuple[list[dict], list[dict]]:
    """Sample n_holdout rows preserving status balance across {verified, refuted, unknown}."""
    rng = random.Random(seed)
    by_status: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        out = r.get("output", {})
        status = out.get("status", "unknown") if isinstance(out, dict) else "unknown"
        by_status[status].append(r)

    holdout: list[dict] = []
    train: list[dict] = []
    total = sum(len(v) for v in by_status.values())
    if total == 0:
        return [], []

    # Per-stratum allocate proportionally; round and adjust.
    target_per_status = {
        s: max(1, round(n_holdout * len(rows_s) / total))
        for s, rows_s in by_status.items()
    }
    # Adjust to hit n_holdout exactly (largest-stratum gets the remainder).
    diff = n_holdout - sum(target_per_status.values())
    if diff != 0 and target_per_status:
        biggest = max(target_per_status, key=lambda s: len(by_status[s]))
        target_per_status[biggest] = max(0, target_per_status[biggest] + diff)

    for status, rows_s in by_status.items():
        rng.shuffle(rows_s)
        k = min(target_per_status.get(status, 0), len(rows_s))
        holdout.extend(rows_s[:k])
        train.extend(rows_s[k:])

    rng.shuffle(holdout)
    rng.shuffle(train)
    return holdout, train


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def label_balance(rows: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for r in rows:
        out = r.get("output", {})
        status = out.get("status", "unknown") if isinstance(out, dict) else "unknown"
        counts[status] += 1
    return dict(counts.most_common())


def category_balance(rows: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for r in rows:
        inp = r.get("input", {})
        cat = inp.get("claim_category", "<unknown>") if isinstance(inp, dict) else "<unknown>"
        counts[cat] += 1
    return dict(counts.most_common())


def root_distribution(rows: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for r in rows:
        prov = r.get("provenance", {})
        proj = (prov.get("project_id", "<unknown>") if isinstance(prov, dict) else "<unknown>")
        counts[proj] += 1
    return dict(counts.most_common())


def recommend_rank(effective_size: int) -> tuple[int, str]:
    """Per ChatGPT priority directive 2026-05-06: rank=8 first for
    doc-verifier, rank=16 only if underfit. Floor at 8 honors that."""
    if effective_size < 2000:
        return 8, "rank=8 first per ChatGPT directive; rank=16 only if underfit"
    if effective_size < 10000:
        return 16, "rank=16 reasonable at this scale"
    return 32, "rank=32 OK for >10k"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout-n", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = load(SOURCES)
    print(f"[split] total raw rows: {len(rows)}")

    # Dedup
    seen: set[str] = set()
    deduped: list[dict] = []
    for r in rows:
        k = dedup_key(r)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)
    print(f"[split] after dedup: {len(deduped)} (removed {len(rows) - len(deduped)} dupes)")

    # Stratified split
    holdout, train = stratified_sample(deduped, args.holdout_n, seed=args.seed)
    print(f"[split] holdout: {len(holdout)}  train: {len(train)}")

    # Stats
    train_labels = label_balance(train)
    holdout_labels = label_balance(holdout)
    train_cats = category_balance(train)
    train_roots = root_distribution(train)

    rank, rank_reason = recommend_rank(len(train))

    profile = {
        "schema_v": 1,
        "ts": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "sources": [str(p) for p in SOURCES],
        "raw_total": len(rows),
        "deduped_total": len(deduped),
        "holdout_n": len(holdout),
        "train_n": len(train),
        "seed": args.seed,
        "stratified_by": "output.status",
        "label_balance_train": train_labels,
        "label_balance_holdout": holdout_labels,
        "claim_category_distribution_train": train_cats,
        "project_root_distribution_train": train_roots,
        "recommended_lora_rank": rank,
        "recommended_lora_rank_reason": rank_reason,
        "evidence_tier": "T1",
        "decision_refs": ["slm-learning-051", "slm-learning-071"],
    }

    if args.dry_run:
        print(json.dumps(profile, indent=2))
        return 0

    write_jsonl(HOLDOUT_PATH, holdout)
    write_jsonl(TRAIN_PATH, train)
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    print(f"[split] wrote {HOLDOUT_PATH}")
    print(f"[split] wrote {TRAIN_PATH}")
    print(f"[split] wrote {PROFILE_PATH}")
    print(f"\n[split] label balance train: {train_labels}")
    print(f"[split] label balance holdout: {holdout_labels}")
    print(f"[split] recommended LoRA rank: {rank} ({rank_reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
