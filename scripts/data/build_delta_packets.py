"""Convert base-eval failures into delta_packet shards.

Per slm-learning-186/192: each failed case becomes a typed packet
attached to a shared context_root. Storage shrinks because the
shared_instruction lives in the root once, not in every row.

Inputs:
  --base-results <path>  — eval_adapter persist JSON for the base
  --root-id <id>         — context_root_id to attach packets to (must
                            already exist as a JSON in data/context_roots/)
  --out-dir <dir>        — packet output dir (default
                            data/delta_packets/base_failures/<base>/<bench>/<date>/)

For each FAILED case:
  1. Look up the canonical solution from the eval dataset.
  2. Build a delta_packet with:
       packet_id, root_context_id, base_model, task_shape,
       skill_id, pressure_source=base_eval_failure,
       failure_type (heuristic from judge_reason),
       base_output_ref (sha256 of completion_full),
       minimal_prompt, correction, tests, retain_tags,
       target_contract, provenance.

Outputs:
  <out-dir>/<packet_id>.json     — one file per packet
  <out-dir>/_index.json          — list of packet_ids + counts

Decision refs: slm-learning-186, 189, 192.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def heuristic_failure_type(judge_reason: str) -> str:
    """Heuristic mapping of judge reason → failure_type label."""
    r = (judge_reason or "").lower()
    if "syntax" in r or "indent" in r:
        return "syntax_or_indent"
    if "name" in r and "not defined" in r:
        return "wrong_signature"
    if "assert" in r:
        return "edge_case_miss"
    if "timeout" in r:
        return "infinite_loop_or_slow"
    if "type" in r and "error" in r:
        return "wrong_types"
    if "import" in r:
        return "missing_import"
    return "other"


def sha256_short(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_humaneval_dataset() -> dict:
    from datasets import load_dataset
    try:
        ds = load_dataset("openai/openai_humaneval", split="test")
    except Exception:
        ds = load_dataset("openai_humaneval", split="test")
    return {row["task_id"]: row for row in ds if row.get("task_id")}


def load_mbpp_dataset() -> dict:
    from datasets import load_dataset
    ds = load_dataset("google-research-datasets/mbpp", "sanitized",
                       split="test")
    return {f"mbpp-{row.get('task_id', i)}": row
            for i, row in enumerate(ds)}


def he_correction(row: dict) -> str:
    p = row.get("prompt", "").rstrip()
    s = row.get("canonical_solution", "").rstrip()
    return (p + "\n" + s) if (p and s) else (s or "")


def mbpp_correction(row: dict) -> str:
    return (row.get("code", "") or "").rstrip()


def mbpp_input(row: dict) -> str:
    text = row.get("prompt") or row.get("text") or ""
    test = row.get("test_list", [""])[0]
    return f"{text}\n\nExample test:\n{test}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-results", required=True)
    ap.add_argument("--root-id", required=True,
                    help="context_root_id (must exist in data/context_roots/)")
    ap.add_argument("--benchmark", default="humaneval",
                    choices=["humaneval", "mbpp"])
    ap.add_argument("--base-slug", required=True,
                    help="short slug like '1p5b' or '7b'")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--task-shape", default="function_repair")
    ap.add_argument("--skill-id", default="code_function_repair")
    ap.add_argument("--target-contract", default="function_definition")
    args = ap.parse_args()

    results = json.loads(Path(args.base_results).read_text(encoding="utf-8"))
    source_model = results.get("base_model", "unknown")

    # Verify root exists
    root_path = REPO_ROOT / "data" / "context_roots" / f"{args.root_id}.json"
    if not root_path.is_file():
        print(f"WARN: context_root not found at {root_path}; "
              "packets will reference a root that does not yet exist. "
              "Create the root JSON before composing training mixes.",
              file=sys.stderr)

    if args.benchmark == "humaneval":
        ds = load_humaneval_dataset()
    else:
        ds = load_mbpp_dataset()

    date = dt.date.today().isoformat()
    out_dir = (Path(args.out_dir) if args.out_dir else
               REPO_ROOT / "data" / "delta_packets" / "base_failures"
               / args.base_slug / args.benchmark / date)
    out_dir.mkdir(parents=True, exist_ok=True)

    packets = []
    for r in results.get("results", []):
        if r.get("passed"):
            continue
        tid = r.get("id", "")
        if not tid or tid not in ds:
            continue
        ds_row = ds[tid]
        if args.benchmark == "humaneval":
            min_prompt = ds_row.get("prompt", "")
            correction = he_correction(ds_row)
            tests = [ds_row.get("test", "") +
                      f"\ncheck({ds_row.get('entry_point', '')})"]
        else:
            min_prompt = mbpp_input(ds_row)
            correction = mbpp_correction(ds_row)
            tests = list(ds_row.get("test_list", []))
        if not correction:
            continue
        completion = r.get("completion_full", "") or ""
        packet_id = f"{args.base_slug}-{args.benchmark}-fail-{tid.split('/')[-1]}"
        packet = {
            "packet_id": packet_id,
            "root_context_id": args.root_id,
            "base_model": source_model,
            "task_shape": args.task_shape,
            "skill_id": args.skill_id,
            "pressure_source": "base_eval_failure",
            "failure_type": heuristic_failure_type(r.get("judge_reason", "")),
            "base_output_ref": sha256_short(completion),
            "minimal_prompt": min_prompt,
            "correction": correction,
            "tests": tests,
            "retain_tags": [f"{args.benchmark}_passed", "function_shape"],
            "target_contract": args.target_contract,
            "provenance": {
                "captured_at": dt.datetime.utcnow().isoformat() + "Z",
                "from_run_id": results.get("adapter_id", "BASE"),
                "captured_by": "build_delta_packets.py",
                "review_status": "auto",
            },
            "token_budget": 1024,
            "schema_v": 1,
        }
        out_path = out_dir / f"{packet_id}.json"
        out_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
        packets.append(packet_id)

    index = {
        "shard_id": f"{args.base_slug}-{args.benchmark}-base-failures-{date}",
        "ts": dt.datetime.utcnow().isoformat() + "Z",
        "root_context_id": args.root_id,
        "base_model": source_model,
        "benchmark": args.benchmark,
        "n_packets": len(packets),
        "packet_ids": packets,
        "decision_refs": ["slm-learning-186", "slm-learning-189",
                           "slm-learning-192"],
    }
    (out_dir / "_index.json").write_text(json.dumps(index, indent=2),
                                          encoding="utf-8")
    print(f"[delta-packets] wrote {len(packets)} packets to {out_dir}")


if __name__ == "__main__":
    main()
