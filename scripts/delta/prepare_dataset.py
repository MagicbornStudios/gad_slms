"""Convert telemetry envelopes into trainer-ready SFT pairs.

Subprocess contract for global daemon (gad-monorepo phase 147). The
daemon hands us a telemetry export (DuckDB / Parquet / JSONL) and asks
us to produce a dataset suitable for `train_delta.py`.

Two-stage pipeline:

  1. Cohort step — group raw envelopes by (project, content_type) using
     `scripts/build_cohorts.py`. Already shipped; reused here.
  2. Pair-build step — walk the cohort grouped by run_id (session) and
     emit prompt -> response pairs. Pair shape conforms to
     `data/eval/doc_verifier_train.reshaped.jsonl` (fields: instruction,
     command, system_prompt, provenance) so the trainer config used for
     specialist runs (rank=8/16, qwen-1.5B) can be reused unchanged.

Daemon contract:

    python scripts/delta/prepare_dataset.py \\
        --manifest <path-to-MANIFEST.json> \\
        --content-type planning \\
        --project global \\
        --out-dir data/processed/<run-id>/ \\
        [--holdout-frac 0.05] [--seed 42]

Output:
    data/processed/<run-id>/sft.jsonl          full pair set
    data/processed/<run-id>/sft.train.jsonl    train split (95% by default)
    data/processed/<run-id>/sft.holdout.jsonl  holdout split (5%)
    data/processed/<run-id>/PREPARE.json       summary + counts

Stdout (JSON, single line):
    {"status": "ok", "out_dir": "...", "rows_in": N, "pairs_out": M,
     "holdout_n": K, "elapsed_seconds": S}

Per slm-learning-051: this script is candidate-only — it shapes data,
does not train. Per slm-learning-019: synthetic distillation pairs
go through scripts/distill/* + this script's --include-distilled flag
(not yet implemented; planned for v2).

Decision refs: slm-learning-051, slm-learning-079, slm-learning-082,
slm-learning-086.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


SYSTEM_PROMPT_PLANNING = (
    "You are a planning specialist for the GAD ecosystem. Given a "
    "user prompt + context, summarize, route, or produce the next "
    "action. Be concise. Cite file paths with backticks."
)

SYSTEM_PROMPT_GENERIC = (
    "You are an assistant. Answer the user's question helpfully and "
    "concisely."
)


def load_envelopes(jsonl_path: Path) -> list[dict]:
    rows: list[dict] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def filter_envelopes(rows: list[dict], project: str | None,
                     content_type: str | None) -> list[dict]:
    out = []
    for r in rows:
        if project and r.get("project") != project:
            continue
        if content_type:
            ct = r.get("content_type") or (
                r.get("content", {}).get("content_type")
                if isinstance(r.get("content"), dict) else None
            )
            if ct and ct != content_type:
                continue
        out.append(r)
    return out


def envelope_text(r: dict) -> str:
    """Extract human-readable text from an envelope's content field."""
    c = r.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, dict):
        for k in ("text", "value", "input_summary", "summary",
                  "tool_name", "gad_command"):
            v = c.get(k)
            if isinstance(v, str) and v.strip():
                return v
        # Fallback: stringify the dict (truncated)
        return json.dumps(c, ensure_ascii=False)[:1500]
    return ""


def build_pairs(rows: list[dict], system_prompt: str,
                strategy: str = "reasoning_to_response") -> list[dict]:
    """Build SFT pairs from telemetry envelopes.

    Strategies:

    - reasoning_to_response (default for planning cohort)
        Group by handoff_id. For each handoff that has both a reasoning
        chain AND a response, concatenate the reasoning chunks (in seq
        order) as the instruction, and the final response text as the
        target. Trains the model to summarize a chain-of-thought into a
        completion message — the core planning specialist signal in the
        global cohort (per audit-2026-05-07-data-quality-honest.md).

    - prompt_to_response (legacy, kept for cohorts where prompts and
        responses share a join key)
        Within each run_id, find adjacent prompt -> response pairs,
        folding intermediate reasoning into the instruction context.
        Returns 0 pairs on the global planning cohort because prompts
        are stored without handoff_id or task_id.
    """
    if strategy == "prompt_to_response":
        return _build_prompt_to_response(rows, system_prompt)
    if strategy == "handoff_prompt_to_response":
        return _build_handoff_prompt_to_response(rows, system_prompt)
    return _build_reasoning_to_response(rows, system_prompt)


def _build_handoff_prompt_to_response(rows: list[dict],
                                       system_prompt: str) -> list[dict]:
    """Pair handoff body (role=prompt with handoff_id) with completion
    (role=response with same handoff_id). This is the right shape for
    a planning specialist trained on the gad-monorepo handoffs adapter
    (commit dad42a4d, 2026-05-07 onwards).
    """
    prompts_by_hid: dict[str, dict] = {}
    responses_by_hid: dict[str, list[dict]] = {}
    reasoning_by_hid: dict[str, list[dict]] = {}

    for r in rows:
        hid = r.get("handoff_id")
        if not hid:
            continue
        role = r.get("role")
        if role == "prompt":
            prompts_by_hid.setdefault(hid, r)  # first wins
        elif role == "response":
            responses_by_hid.setdefault(hid, []).append(r)
        elif role == "reasoning":
            reasoning_by_hid.setdefault(hid, []).append(r)

    pairs: list[dict] = []
    for hid, prompt_env in prompts_by_hid.items():
        responses = responses_by_hid.get(hid, [])
        if not responses:
            continue
        # Sort responses by ts; the LAST is the final closeout
        responses.sort(key=lambda x: (x.get("ts") or "", x.get("seq", 0)))
        target = responses[-1]

        prompt_text = envelope_text(prompt_env).strip()
        response_text = envelope_text(target).strip()
        if not prompt_text or not response_text:
            continue

        # Optional: include reasoning chunks for this handoff as
        # additional context. Useful but adds length.
        reasoning_chunks = [envelope_text(e) for e in
                            sorted(reasoning_by_hid.get(hid, []),
                                   key=lambda x: (x.get("ts") or "",
                                                  x.get("seq", 0)))
                            if envelope_text(e)]

        if len(prompt_text) > 4000:
            prompt_text = prompt_text[:4000] + "\n[truncated]"
        if len(response_text) > 4000:
            response_text = response_text[:4000] + "\n[truncated]"

        instruction = (
            f"You are a planning specialist for the GAD ecosystem. The "
            f"following is a handoff brief assigned to you. Produce a "
            f"completion message that summarizes the work done, names "
            f"changed files, validation steps, and any remaining gaps.\n\n"
            f"Handoff: {hid}\n\n"
            f"Brief:\n{prompt_text}"
        )
        if reasoning_chunks:
            joined_reasoning = "\n\n".join(reasoning_chunks)
            if len(joined_reasoning) > 6000:
                joined_reasoning = joined_reasoning[:6000] + "\n[truncated]"
            # Skip embedding reasoning by default — keeps the
            # instruction tight. The handoff brief itself + handoff_id
            # is enough signal.

        provenance = {
            "source_handoff_id": hid,
            "source_envelope_ids": [prompt_env.get("id")] +
                                    [e.get("id") for e in responses],
            "reasoning_chunk_count": len(reasoning_chunks),
            "agent_type": "planning",
            "project_id": prompt_env.get("project"),
            "agent_id": target.get("agent_id"),
            "runtime": target.get("runtime"),
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "human_approved": False,
            "later_contradicted": False,
            "secret_redacted": True,
            "data_tier": "telemetry_extracted",
            "pair_strategy": "handoff_prompt_to_response",
        }

        pairs.append({
            "instruction": instruction,
            "command": response_text,
            "system_prompt": system_prompt,
            "provenance": provenance,
        })

    return pairs


def _build_reasoning_to_response(rows: list[dict], system_prompt: str) -> list[dict]:
    by_handoff: dict[str, list[dict]] = {}
    for r in rows:
        hid = r.get("handoff_id")
        if not hid:
            continue
        if r.get("role") not in {"reasoning", "response"}:
            continue
        by_handoff.setdefault(hid, []).append(r)

    pairs: list[dict] = []
    for hid, env_list in by_handoff.items():
        env_list.sort(key=lambda x: (x.get("ts") or "", x.get("seq", 0)))

        reasoning_chunks: list[str] = []
        responses: list[dict] = []
        for e in env_list:
            role = e.get("role")
            txt = envelope_text(e)
            if not txt:
                continue
            if role == "reasoning":
                reasoning_chunks.append(txt)
            elif role == "response":
                responses.append(e)

        if not responses or not reasoning_chunks:
            continue

        # Use the LAST response as the target — that's the final
        # completion summary. Earlier responses (if any) get folded
        # into the reasoning context.
        target = responses[-1]
        for r in responses[:-1]:
            t = envelope_text(r)
            if t:
                reasoning_chunks.append(t)

        instruction_text = "\n\n---\n\n".join(reasoning_chunks).strip()
        if len(instruction_text) > 6000:
            instruction_text = instruction_text[:6000] + "\n[truncated]"

        instruction = (
            "Below is the chain-of-thought from working on a planning "
            "handoff. Summarize the work into a concise completion "
            "message that names the changed files, validation steps, "
            "and any remaining gaps.\n\n"
            f"Handoff: {hid}\n\n"
            f"Reasoning trace:\n{instruction_text}"
        )

        command = envelope_text(target).strip()
        if len(command) > 4000:
            command = command[:4000] + "\n[truncated]"

        if not command:
            continue

        provenance = {
            "source_handoff_id": hid,
            "source_envelope_ids": [e.get("id") for e in env_list],
            "reasoning_chunk_count": len(reasoning_chunks),
            "agent_type": "planning",
            "project_id": target.get("project"),
            "agent_id": target.get("agent_id"),
            "runtime": target.get("runtime"),
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "human_approved": False,
            "later_contradicted": False,
            "secret_redacted": True,
            "data_tier": "telemetry_extracted",
            "pair_strategy": "reasoning_to_response",
        }

        pairs.append({
            "instruction": instruction,
            "command": command,
            "system_prompt": system_prompt,
            "provenance": provenance,
        })

    return pairs


def _build_prompt_to_response(rows: list[dict], system_prompt: str) -> list[dict]:
    by_run: dict[str, list[dict]] = {}
    for r in rows:
        rid = r.get("run_id") or "_no_run"
        by_run.setdefault(rid, []).append(r)

    pairs: list[dict] = []

    for rid, env_list in by_run.items():
        env_list.sort(key=lambda x: x.get("seq", 0))

        i = 0
        while i < len(env_list):
            r = env_list[i]
            if r.get("role") != "prompt":
                i += 1
                continue

            prompt_text = envelope_text(r)
            reasoning_chunks: list[str] = []

            j = i + 1
            response_text = None
            while j < len(env_list):
                nxt = env_list[j]
                role = nxt.get("role")
                if role == "reasoning":
                    txt = envelope_text(nxt)
                    if txt:
                        reasoning_chunks.append(txt)
                    j += 1
                    continue
                if role == "response":
                    response_text = envelope_text(nxt)
                    j += 1
                    break
                break

            if not response_text or not prompt_text:
                i += 1
                continue

            instruction = prompt_text.strip()
            if len(instruction) > 4000:
                instruction = instruction[:4000] + "\n[truncated]"

            command = response_text.strip()
            if len(command) > 4000:
                command = command[:4000] + "\n[truncated]"

            provenance = {
                "source_run_id": rid,
                "source_envelope_ids": [r.get("id"), env_list[j-1].get("id") if j > 0 else None],
                "reasoning_chunk_count": len(reasoning_chunks),
                "agent_type": "planning",
                "project_id": r.get("project"),
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                "human_approved": False,
                "later_contradicted": False,
                "secret_redacted": True,
                "data_tier": "telemetry_extracted",
                "pair_strategy": "prompt_to_response",
            }

            pairs.append({
                "instruction": instruction,
                "command": command,
                "system_prompt": system_prompt,
                "provenance": provenance,
            })

            i = j

    return pairs


def split_holdout(pairs: list[dict], frac: float, seed: int) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    shuffled = list(pairs)
    rng.shuffle(shuffled)
    n_hold = max(1, int(len(shuffled) * frac))
    holdout = shuffled[:n_hold]
    train = shuffled[n_hold:]
    return train, holdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=False,
                        help="MANIFEST.json from a telemetry export. "
                             "Used to discover the cohort JSONL path.")
    parser.add_argument("--cohort", type=Path, required=False,
                        help="Direct path to a cohort JSONL (skips manifest "
                             "lookup).")
    parser.add_argument("--project", type=str, default=None,
                        help="Filter envelopes to this project")
    parser.add_argument("--content-type", type=str, default=None,
                        help="Filter envelopes to this content_type")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--holdout-frac", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--system-prompt", type=str, default=None,
                        help="Override system prompt (default: planning if "
                             "content_type=planning, else generic)")
    parser.add_argument("--strategy", type=str, default="reasoning_to_response",
                        choices=["reasoning_to_response", "prompt_to_response",
                                 "handoff_prompt_to_response"],
                        help="Pair-building strategy. reasoning_to_response "
                             "(default) groups by handoff_id and emits "
                             "(reasoning chain -> response). "
                             "handoff_prompt_to_response groups by handoff_id "
                             "and emits (handoff body prompt -> final response) "
                             "— USE THIS for the planning specialist when the "
                             "telemetry export includes the handoffs adapter "
                             "(gad-monorepo dad42a4d+). "
                             "prompt_to_response is the legacy heuristic "
                             "that requires prompt + response in same run_id.")
    args = parser.parse_args()

    t0 = time.time()

    if not args.cohort and not args.manifest:
        print(json.dumps({"status": "error",
                          "error": "must pass --cohort OR --manifest"}))
        return 2

    if args.cohort:
        cohort_path = args.cohort
    else:
        if not args.manifest.exists():
            print(json.dumps({"status": "error",
                              "error": f"manifest not found: {args.manifest}"}))
            return 2
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        # Accept either {events_jsonl: ...} or fall back to sibling events.jsonl
        ev = manifest.get("events_jsonl") or "events.jsonl"
        cohort_path = (args.manifest.parent / ev).resolve()

    if not cohort_path.exists():
        print(json.dumps({"status": "error",
                          "error": f"cohort jsonl not found: {cohort_path}"}))
        return 2

    rows = load_envelopes(cohort_path)
    rows = filter_envelopes(rows, args.project, args.content_type)

    sys_prompt = args.system_prompt or (
        SYSTEM_PROMPT_PLANNING
        if args.content_type == "planning"
        else SYSTEM_PROMPT_GENERIC
    )

    pairs = build_pairs(rows, sys_prompt, strategy=args.strategy)
    train, holdout = split_holdout(pairs, args.holdout_frac, args.seed)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    full_path = args.out_dir / "sft.jsonl"
    train_path = args.out_dir / "sft.train.jsonl"
    holdout_path = args.out_dir / "sft.holdout.jsonl"
    summary_path = args.out_dir / "PREPARE.json"

    for path, items in [(full_path, pairs),
                        (train_path, train),
                        (holdout_path, holdout)]:
        with path.open("w", encoding="utf-8") as f:
            for r in items:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    elapsed = time.time() - t0
    summary = {
        "status": "ok",
        "schema_v": 1,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "cohort_path": str(cohort_path),
        "project_filter": args.project,
        "content_type_filter": args.content_type,
        "strategy": args.strategy,
        "rows_in": len(rows),
        "pairs_out": len(pairs),
        "train_n": len(train),
        "holdout_n": len(holdout),
        "out_dir": str(args.out_dir),
        "elapsed_seconds": round(elapsed, 2),
        "decision_refs": ["slm-learning-051", "slm-learning-079",
                          "slm-learning-082", "slm-learning-086"],
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Single-line JSON to stdout for daemon consumption
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
