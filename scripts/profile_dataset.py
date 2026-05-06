"""Dataset profiling — required before any higher-rank LoRA training.

Per ChatGPT priority directive 2026-05-06: "Build dataset profiling
before any higher-rank LoRA: raw examples, exact/near duplicates,
project distribution, task-shape distribution, output-schema
distribution, label balance, effective data size estimate,
recommended LoRA rank."

Reads any JSONL corpus with `instruction` + `command` fields (the
slm-learning trainer's expected shape per
`src/slm_from_scratch/finetune/data/jsonl_pairs.py`) and emits a
structured profile JSON.

Usage:

    .venv/Scripts/python.exe scripts/profile_dataset.py \\
        --in data/agent_corpus_gad-doc-verifier.bootstrapped.jsonl \\
        --out experiments/profiles/doc_verifier.profile.json

    # Compare corpora side-by-side
    .venv/Scripts/python.exe scripts/profile_dataset.py \\
        --in data/gad_tool_pairs_v2.jsonl \\
        --in data/openmathinstruct_5k.jsonl \\
        --in data/multitask_combined.jsonl \\
        --out experiments/profiles/multi.profile.json

LoRA rank recommendation heuristic (rule-based, evidence-tier T1):

    effective_size <  500   → rank=4   (BitFit / IA3 territory)
    effective_size <  2000  → rank=8
    effective_size <  10000 → rank=16
    effective_size >= 10000 → rank=32

Effective size = raw - exact_dupes - near_dupes_above_threshold.

Decision refs: slm-learning-049 (adapter ladder), slm-learning-051
(candidate-only training), slm-learning-071 (evidence-tier T1+).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def normalize_for_dup(text: str) -> str:
    """Lowercase + collapse whitespace + strip — for near-dup detection."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower()).strip()


def shingle_set(text: str, k: int = 5) -> set[str]:
    """Word-level k-shingles for jaccard similarity."""
    words = normalize_for_dup(text).split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def detect_near_dupes(rows: list[dict], threshold: float = 0.85,
                      sample_cap: int = 5000) -> int:
    """Approximate near-dup count via shingle jaccard on a capped sample.

    O(n^2) jaccard is too slow for large corpora; we cap at sample_cap
    and project the rate to the full corpus.
    """
    if len(rows) <= 1:
        return 0
    sampled = rows[:sample_cap]
    shingles = [shingle_set(r.get("instruction", ""), k=5) for r in sampled]
    near_count = 0
    seen = set()
    for i in range(len(sampled)):
        if i in seen:
            continue
        for j in range(i + 1, len(sampled)):
            if j in seen:
                continue
            if jaccard(shingles[i], shingles[j]) >= threshold:
                near_count += 1
                seen.add(j)
    if len(rows) > sample_cap:
        rate = near_count / sample_cap
        return int(rate * len(rows))
    return near_count


def derive_task_shape(row: dict) -> str:
    """Heuristic task-shape from instruction + response surface."""
    instr = row.get("instruction", "")
    resp = row.get("command", "")
    if not isinstance(instr, str):
        instr = ""
    if not isinstance(resp, str):
        resp = ""

    # CLI translation
    if resp.strip().startswith("gad ") or "gad " in resp[:30]:
        return "cli_translation"
    # Math / numeric
    if re.search(r"\b(?:solve|calculate|compute|how many|how much)\b", instr.lower()):
        return "math_word_problem"
    # Tool call (JSON shape)
    if resp.strip().startswith("{") and ('"tool"' in resp or '"function"' in resp):
        return "tool_call_json"
    # Tool call (Python-call shape from telemetry)
    if re.match(r"^\w+\(\{", resp.strip()):
        return "tool_call_python_repr"
    # Code completion (def / class / function bodies)
    if re.search(r"^\s*(def |class |function |const |let |var |#include)", resp[:60], re.MULTILINE):
        return "code_completion"
    # Doc verification
    if isinstance(row.get("output"), dict) and row["output"].get("status") in {
        "verified", "refuted", "unknown"
    }:
        return "doc_verification"
    # Reasoning / explanation
    if len(resp) > 400 and "\n\n" in resp:
        return "long_form_reasoning"
    # Short answer
    if len(resp) < 80:
        return "short_answer"
    return "other"


def derive_output_schema(row: dict) -> str:
    resp = row.get("command", "")
    if isinstance(row.get("output"), dict):
        return "structured_dict"
    if not isinstance(resp, str):
        return "non_string"
    s = resp.strip()
    if not s:
        return "empty"
    if s.startswith("gad "):
        return "single_line_cli"
    if s.startswith("{") and s.endswith("}"):
        return "json_object"
    if "\n" in s:
        return "multi_line"
    return "single_line"


def derive_label(row: dict) -> str | None:
    """For doc-verifier shape, label is in output.status."""
    out = row.get("output")
    if isinstance(out, dict) and out.get("status") in {
        "verified", "refuted", "unknown"
    }:
        return out["status"]
    return None


def derive_project(row: dict) -> str:
    prov = row.get("provenance", {})
    if isinstance(prov, dict):
        for key in ("project_id", "project", "source_project"):
            if key in prov and prov[key]:
                return str(prov[key])
    if "project" in row and row["project"]:
        return str(row["project"])
    if "project_root" in row.get("input", {}) if isinstance(row.get("input"), dict) else False:
        pr = row["input"]["project_root"]
        return Path(str(pr)).name
    return "<unknown>"


def recommend_rank(effective_size: int) -> tuple[int, str]:
    if effective_size < 500:
        return 4, "small corpus — try BitFit/IA³ first; rank=4 if LoRA needed"
    if effective_size < 2000:
        return 8, "rank=8 sufficient at this scale; rank=16 only if underfit"
    if effective_size < 10000:
        return 16, "rank=16 reasonable; rank=32 only if multi-task"
    return 32, "rank=32 OK for >10k; consider DoRA for quality lift"


def length_stats(rows: list[dict], field: str) -> dict:
    lengths = [len(r.get(field, "")) for r in rows if isinstance(r.get(field), str)]
    if not lengths:
        return {"min": 0, "median": 0, "p75": 0, "p95": 0, "max": 0, "n": 0}
    s = sorted(lengths)
    n = len(s)
    return {
        "min": s[0],
        "median": s[n // 2],
        "p75": s[(n * 3) // 4],
        "p95": s[(n * 95) // 100],
        "max": s[-1],
        "n": n,
    }


def profile_corpus(path: Path, near_dup_threshold: float = 0.85) -> dict:
    rows = load_jsonl(path)
    n_raw = len(rows)

    # Exact dupes (sha of instruction+response)
    seen_sha: set[str] = set()
    n_exact_dup = 0
    for r in rows:
        key = sha((r.get("instruction") or "") + "||" + (r.get("command") or ""))
        if key in seen_sha:
            n_exact_dup += 1
        else:
            seen_sha.add(key)

    # Near-dupes (capped, projected)
    n_near_dup = detect_near_dupes(rows, threshold=near_dup_threshold)

    # Distributions
    project_dist = Counter(derive_project(r) for r in rows)
    task_shape_dist = Counter(derive_task_shape(r) for r in rows)
    output_schema_dist = Counter(derive_output_schema(r) for r in rows)
    label_dist = Counter(derive_label(r) for r in rows if derive_label(r) is not None)

    effective_size = max(0, n_raw - n_exact_dup - n_near_dup)
    rank, rank_reason = recommend_rank(effective_size)

    instr_lens = length_stats(rows, "instruction")
    resp_lens = length_stats(rows, "command")

    return {
        "path": str(path),
        "n_raw": n_raw,
        "n_exact_dup": n_exact_dup,
        "n_near_dup_estimated": n_near_dup,
        "near_dup_threshold": near_dup_threshold,
        "effective_size": effective_size,
        "duplication_rate": round((n_exact_dup + n_near_dup) / n_raw, 3) if n_raw else 0,
        "instruction_length_chars": instr_lens,
        "response_length_chars": resp_lens,
        "project_distribution": dict(project_dist.most_common()),
        "task_shape_distribution": dict(task_shape_dist.most_common()),
        "output_schema_distribution": dict(output_schema_dist.most_common()),
        "label_distribution": dict(label_dist.most_common()) if label_dist else None,
        "label_balance_warning": (
            "imbalanced" if label_dist and (
                max(label_dist.values()) / sum(label_dist.values()) > 0.7
            ) else None
        ) if label_dist else None,
        "recommended_lora_rank": rank,
        "recommended_lora_rank_reason": rank_reason,
        "decision_refs": ["slm-learning-049", "slm-learning-051", "slm-learning-071"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", "-i", action="append", required=True,
                        dest="inputs", help="Input JSONL path (repeatable)")
    parser.add_argument("--out", "-o", type=Path, default=None,
                        help="Output JSON path (default: stdout)")
    parser.add_argument("--near-dup-threshold", type=float, default=0.85)
    args = parser.parse_args()

    profiles = []
    for p in args.inputs:
        path = Path(p)
        if not path.exists():
            print(f"WARN: {path} does not exist, skipping")
            continue
        profile = profile_corpus(path, near_dup_threshold=args.near_dup_threshold)
        profiles.append(profile)
        print(f"[profile] {path.name}: raw={profile['n_raw']} "
              f"effective={profile['effective_size']} "
              f"rank={profile['recommended_lora_rank']}")

    summary = {
        "schema_v": 1,
        "profiles": profiles,
        "n_corpora": len(profiles),
    }

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\n[profile] wrote {args.out}")
    else:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
