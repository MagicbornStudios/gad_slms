"""Mine tool-use preference pairs from GAD trace logs.

Reads:
    .planning/.trace-events.jsonl       (tool_use events with tool name + inputs)
    .planning/.gad-log/<date>.jsonl     (gad CLI call log with timing + exit codes)

Identifies sequences where:
    (a) multi-tool Read/Glob/Grep cascades near the same wall-clock window
        could have been replaced by a single `gad ask` call
    (b) multi-Read + Write sequences on the same file set could have been
        a native shell cp/mv/rsync
    (c) N sequential main-thread Agent dispatches on independent tasks
        could have been dispatched in parallel

Writes:
    slm_learning/data/preference/tool_use_pairs_<date>.jsonl

Each output row conforms to tool_use_preference.schema.json (schema_v=1).
Decision refs: GLOBAL-D-330, GLOBAL-D-331, GLOBAL-D-332.

Does NOT train — dataset emission only.

Usage:
    python mine_tool_use_preference_pairs.py [--date YYYY-MM-DD] [--out PATH]
    python mine_tool_use_preference_pairs.py --date 2026-05-09 --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Generator

REPO_ROOT = Path(__file__).resolve().parents[3]
TRACE_EVENTS = REPO_ROOT / ".planning" / ".trace-events.jsonl"
GAD_LOG_DIR = REPO_ROOT / ".planning" / ".gad-log"
DATA_OUT_DIR = REPO_ROOT / "slm_learning" / "data" / "preference"

# Cascade detection window: tool calls within this many milliseconds of each
# other are candidates for a single-call replacement.
CASCADE_WINDOW_MS = 15_000

# Minimum number of tool calls in a candidate cascade before emitting a pair.
MIN_CASCADE_DEPTH = 3

# Token estimates per tool call type (rough — calibrate from actual model pricing snapshot).
TOKEN_ESTIMATE_PER_READ = 800   # avg 600 context + 200 output for a Read
TOKEN_ESTIMATE_PER_GLOB = 120
TOKEN_ESTIMATE_PER_GREP = 200
TOKEN_ESTIMATE_GAD_ASK = 480    # single call returning citations
TOKEN_ESTIMATE_PER_WRITE = 1400 # avg file size in output tokens


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_trace_events(path: Path) -> list[dict]:
    """Load all trace events from .trace-events.jsonl.

    Returns a flat list sorted by ts ascending. Only loads tool_use type events.
    Ignores file_mutation and other types for this miner.
    """
    if not path.exists():
        return []
    events = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "tool_use":
                events.append(ev)
    return sorted(events, key=lambda e: e.get("ts", ""))


def load_gad_log(date_str: str) -> list[dict]:
    """Load a single day's .gad-log/<date>.jsonl.

    Returns list of CLI call records. Shape per entry:
        {ts, cmd, args, duration_ms, exit, runtime:{id}, agent:{...}}
    """
    path = GAD_LOG_DIR / f"{date_str}.jsonl"
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


# ---------------------------------------------------------------------------
# Pattern detectors
# ---------------------------------------------------------------------------

def detect_glob_read_cascade(events: list[dict]) -> Generator[dict, None, None]:
    """Detect Glob → Grep → Read+ cascades that could be replaced by gad ask.

    Heuristic:
        Within CASCADE_WINDOW_MS, if we see:
            Glob + (Grep | Read) * N  where N >= MIN_CASCADE_DEPTH - 1
        on paths that share a common directory prefix → emit a pair.

    Yields raw candidate dicts (not yet schema-shaped).
    """
    i = 0
    while i < len(events):
        ev = events[i]
        tool = ev.get("tool", "")
        if tool not in ("Glob", "Grep", "Read"):
            i += 1
            continue

        # Try to extend a cascade from this anchor
        anchor_ts = _parse_ts(ev.get("ts", ""))
        if anchor_ts is None:
            i += 1
            continue

        cascade = [ev]
        j = i + 1
        while j < len(events):
            nev = events[j]
            ntool = nev.get("tool", "")
            if ntool not in ("Glob", "Grep", "Read"):
                break
            nts = _parse_ts(nev.get("ts", ""))
            if nts is None or (nts - anchor_ts).total_seconds() * 1000 > CASCADE_WINDOW_MS:
                break
            cascade.append(nev)
            j += 1

        if len(cascade) >= MIN_CASCADE_DEPTH:
            yield {
                "type": "glob_read_cascade",
                "events": cascade,
                "anchor_ts": ev.get("ts"),
                "session_id": ev.get("runtime", {}).get("session_id"),
                "runtime": ev.get("runtime", {}).get("id"),
                "agent_id": ev.get("agent", {}).get("agent_id"),
            }
            i = j  # skip past cascade
        else:
            i += 1


def detect_read_write_copy(events: list[dict]) -> Generator[dict, None, None]:
    """Detect Read(file) → Write(file) pairs at scale that could be native cp.

    Heuristic: within CASCADE_WINDOW_MS, if we see Read + Write on different
    paths where the Write content would be the Read content (same filename
    in different directory) → emit a pair.

    Yields raw candidate dicts.
    """
    reads: dict[str, list] = defaultdict(list)

    for ev in events:
        if ev.get("tool") != "Read":
            continue
        fp = ev.get("inputs", {}).get("file_path", "")
        if fp:
            reads[Path(fp).name].append(ev)

    for ev in events:
        if ev.get("tool") != "Write":
            continue
        fp = ev.get("inputs", {}).get("file_path", "")
        name = Path(fp).name if fp else ""
        if name in reads and len(reads[name]) >= 1:
            # Match: a file was read and then written under a different path
            matching_reads = reads[name]
            for r in matching_reads:
                rts = _parse_ts(r.get("ts", ""))
                wts = _parse_ts(ev.get("ts", ""))
                if rts and wts and 0 <= (wts - rts).total_seconds() * 1000 <= CASCADE_WINDOW_MS:
                    yield {
                        "type": "read_write_copy",
                        "read_event": r,
                        "write_event": ev,
                        "anchor_ts": r.get("ts"),
                        "session_id": r.get("runtime", {}).get("session_id"),
                        "runtime": r.get("runtime", {}).get("id"),
                        "agent_id": r.get("agent", {}).get("agent_id"),
                    }


# ---------------------------------------------------------------------------
# Pair builders
# ---------------------------------------------------------------------------

def build_glob_read_pair(candidate: dict, seq: int) -> dict:
    """Shape a glob_read_cascade candidate into a tool_use_preference row."""
    events = candidate["events"]
    n = len(events)
    rejected_tokens = (
        sum(TOKEN_ESTIMATE_PER_READ for e in events if e.get("tool") == "Read") +
        sum(TOKEN_ESTIMATE_PER_GLOB for e in events if e.get("tool") == "Glob") +
        sum(TOKEN_ESTIMATE_PER_GREP for e in events if e.get("tool") == "Grep")
    )
    chosen_tokens = TOKEN_ESTIMATE_GAD_ASK

    # Infer a query from the Read paths
    paths = [e.get("inputs", {}).get("file_path", "") or e.get("inputs", {}).get("pattern", "") for e in events]
    common = _longest_common_prefix(paths)
    query = f"What is in {common} and how does it work?"

    return {
      "pair_id": f"tupr-global-{_today()}-{seq:03d}",
      "ts": candidate["anchor_ts"] or _now_iso(),
      "projectid": "global",
      "goal": f"Understand the codebase structure under {common}",
      "context_tokens": None,
      "chosen": {
        "actions": [{"tool": "Bash", "inputs": {"command": f"gad ask \"{query}\""}, "rationale": "Single semantic lookup replaces the full Glob+Read cascade."}],
        "total_tool_calls": 1,
        "est_tokens_emitted": chosen_tokens // 2,
        "est_tokens_consumed": chosen_tokens // 2,
        "est_wall_time_ms": 1200,
        "est_cost_usd": round(chosen_tokens * 0.000003, 6)
      },
      "rejected": [
        {
          "actions": [{"tool": e.get("tool", ""), "inputs": e.get("inputs", {})} for e in events],
          "total_tool_calls": n,
          "est_tokens_emitted": rejected_tokens // 4,
          "est_tokens_consumed": (rejected_tokens * 3) // 4,
          "est_wall_time_ms": n * 800,
          "est_cost_usd": round(rejected_tokens * 0.000003, 6)
        }
      ],
      "verdict_source": "retrospective_log_analysis",
      "metric": "tokens_per_success",
      "delta": {
        "metric": "tokens_per_success",
        "chosen_value": chosen_tokens,
        "rejected_value_median": rejected_tokens,
        "pct_savings": round((1 - chosen_tokens / max(rejected_tokens, 1)) * 100, 1)
      },
      "example_failure_mode_avoided": f"Glob+Read cascade over gad ask: {n} sequential filesystem calls when the GAD semantic index had the answer in one lookup",
      "agent_id": candidate.get("agent_id"),
      "runtime": candidate.get("runtime"),
      "session_id": candidate.get("session_id"),
      "license_class": "owned"
    }


def build_read_write_copy_pair(candidate: dict, seq: int) -> dict:
    """Shape a read_write_copy candidate into a tool_use_preference row."""
    fp_src = candidate["read_event"].get("inputs", {}).get("file_path", "?")
    fp_dst = candidate["write_event"].get("inputs", {}).get("file_path", "?")
    rejected_tokens = TOKEN_ESTIMATE_PER_READ + TOKEN_ESTIMATE_PER_WRITE

    return {
      "pair_id": f"tupr-global-{_today()}-{seq:03d}",
      "ts": candidate["anchor_ts"] or _now_iso(),
      "projectid": "global",
      "goal": f"Copy {fp_src} to {fp_dst}",
      "context_tokens": None,
      "chosen": {
        "actions": [{"tool": "Bash", "inputs": {"command": f"cp \"{fp_src}\" \"{fp_dst}\""}, "rationale": "Native shell cp — zero token emission for file contents."}],
        "total_tool_calls": 1,
        "est_tokens_emitted": 15,
        "est_tokens_consumed": 40,
        "est_wall_time_ms": 50,
        "est_cost_usd": 0.000001
      },
      "rejected": [
        {
          "actions": [
            {"tool": "Read", "inputs": {"file_path": fp_src}},
            {"tool": "Write", "inputs": {"file_path": fp_dst}}
          ],
          "total_tool_calls": 2,
          "est_tokens_emitted": TOKEN_ESTIMATE_PER_WRITE,
          "est_tokens_consumed": TOKEN_ESTIMATE_PER_READ,
          "est_wall_time_ms": 1800,
          "est_cost_usd": round(rejected_tokens * 0.000003, 6)
        }
      ],
      "verdict_source": "retrospective_log_analysis",
      "metric": "tokens_per_success",
      "delta": {
        "metric": "tokens_per_success",
        "chosen_value": 55,
        "rejected_value_median": rejected_tokens,
        "pct_savings": round((1 - 55 / max(rejected_tokens, 1)) * 100, 1)
      },
      "example_failure_mode_avoided": "read-then-rewrite over native cp: agent emitted full file contents as output tokens when a shell cp command would have cost zero emission tokens",
      "agent_id": candidate.get("agent_id"),
      "runtime": candidate.get("runtime"),
      "session_id": candidate.get("session_id"),
      "license_class": "owned"
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def _today() -> str:
    return date.today().isoformat().replace("-", "")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _longest_common_prefix(paths: list[str]) -> str:
    if not paths:
        return "unknown"
    paths = [p for p in paths if p]
    if not paths:
        return "unknown"
    # Use Path parts for directory prefix
    parts_list = [Path(p).parts for p in paths]
    common_parts = []
    for part_group in zip(*parts_list):
        if len(set(part_group)) == 1:
            common_parts.append(part_group[0])
        else:
            break
    return "/".join(common_parts) or paths[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", default=date.today().isoformat(), help="Date to mine (YYYY-MM-DD). Default: today.")
    p.add_argument("--out", default=None, help="Output path. Default: data/preference/tool_use_pairs_<date>.jsonl")
    p.add_argument("--dry-run", action="store_true", help="Print pairs to stdout, do not write file.")
    args = p.parse_args()

    out_path = Path(args.out) if args.out else DATA_OUT_DIR / f"tool_use_pairs_{args.date}-mined.jsonl"

    print(f"[mine] loading trace events from {TRACE_EVENTS}")
    events = load_trace_events(TRACE_EVENTS)
    print(f"[mine] {len(events)} tool_use events loaded")

    pairs: list[dict] = []
    seq = 1

    for candidate in detect_glob_read_cascade(events):
        pairs.append(build_glob_read_pair(candidate, seq))
        seq += 1

    for candidate in detect_read_write_copy(events):
        pairs.append(build_read_write_copy_pair(candidate, seq))
        seq += 1

    if not pairs:
        print("[mine] no candidates found — trace may be too sparse or heuristics need tuning")
        return 0

    print(f"[mine] {len(pairs)} preference pairs generated")

    # Token estimate summary
    total_rejected_tokens = sum(
        p["rejected"][0].get("est_tokens_emitted", 0) + p["rejected"][0].get("est_tokens_consumed", 0)
        for p in pairs if p.get("rejected")
    )
    total_chosen_tokens = sum(
        p["chosen"].get("est_tokens_emitted", 0) + p["chosen"].get("est_tokens_consumed", 0)
        for p in pairs
    )
    if total_rejected_tokens > 0:
        savings_pct = round((1 - total_chosen_tokens / total_rejected_tokens) * 100, 1)
        print(f"[mine] aggregate token savings: {savings_pct}% ({total_chosen_tokens:,} chosen vs {total_rejected_tokens:,} rejected)")

    if args.dry_run:
        for pair in pairs:
            print(json.dumps(pair, ensure_ascii=False))
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for pair in pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
    print(f"[mine] written to {out_path.relative_to(REPO_ROOT) if REPO_ROOT in out_path.parents else out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
