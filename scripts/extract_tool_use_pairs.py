"""Extract tool-use training pairs from .planning/.trace-events.jsonl.

Single concern: convert real Claude-Code-on-this-repo trace events into
JSONL training pairs for tool-use fine-tuning.

Schema of each output pair:

  {
    "instruction": "<role-tagged context + 'next action:' prompt>",
    "command":     "<tool-name>(<json-args>)",
    "session":     "<session-id>",
    "seq":         <int>,
    "tool":        "<tool-name>",
    "source":      "trace-events"
  }

Context is built from the last N tool calls in the same session, with
inputs summarized (paths shown, long content truncated). Outputs are
summarized to a few-line preview to keep pairs short.

Why this format: matches the existing data/gad_tool_pairs.jsonl shape so
our existing trainer (jsonl_pairs adapter) reads it without changes.

Usage:

  .venv/Scripts/python.exe scripts/extract_tool_use_pairs.py \\
      --in .planning/.trace-events.jsonl \\
      --out data/tool_use_pairs.jsonl \\
      --context-window 5
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# Secret patterns we strip from BOTH inputs and outputs of every event
# before writing training pairs. Order matters: more specific first.
SECRET_PATTERNS = [
    (re.compile(r'sk-ant-[A-Za-z0-9_\-]{20,}'),    '[REDACTED_ANTHROPIC_KEY]'),
    (re.compile(r'sk-[A-Za-z0-9]{20,}'),            '[REDACTED_OPENAI_KEY]'),
    (re.compile(r'\bnpm_[A-Za-z0-9_\-]{30,}'),      '[REDACTED_NPM_TOKEN]'),
    (re.compile(r'\bghp_[A-Za-z0-9]{30,}'),         '[REDACTED_GH_PAT]'),
    (re.compile(r'\bgh[ous]_[A-Za-z0-9]{30,}'),     '[REDACTED_GH_TOKEN]'),
    (re.compile(r'\bgithub_pat_[A-Za-z0-9_]{50,}'), '[REDACTED_GH_FINEPAT]'),
    (re.compile(r'\bAKIA[A-Z0-9]{16}\b'),            '[REDACTED_AWS_KEY]'),
    (re.compile(r'\bhf_[A-Za-z0-9]{30,}'),          '[REDACTED_HF_TOKEN]'),
    (re.compile(r'\bxoxb-[A-Za-z0-9-]{30,}'),       '[REDACTED_SLACK_TOKEN]'),
]


def _sanitize(text: str) -> str:
    """Strip known secret patterns. Returns the redacted text."""
    if not text:
        return text
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _sanitize_obj(obj):
    """Recursively redact secrets in any JSON-able structure."""
    if isinstance(obj, str):
        return _sanitize(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_obj(v) for v in obj]
    return obj


def _summarize_inputs(tool: str, inputs: dict) -> str:
    """Render tool inputs compactly for context (not the target)."""
    if tool in ("Read",):
        return f"Read({inputs.get('file_path', '?')})"
    if tool in ("Edit",):
        path = inputs.get("file_path", "?")
        old = (inputs.get("old_string") or "")[:60].replace("\n", " ")
        return f"Edit({path}, old={old!r})"
    if tool in ("Write",):
        path = inputs.get("file_path", "?")
        size = len(inputs.get("content") or "")
        return f"Write({path}, {size}b)"
    if tool in ("Bash",):
        cmd = (inputs.get("command") or "")[:120].replace("\n", " ")
        return f"Bash({cmd!r})"
    if tool in ("PowerShell",):
        cmd = (inputs.get("command") or "")[:120].replace("\n", " ")
        return f"PowerShell({cmd!r})"
    if tool in ("Grep",):
        return f"Grep({inputs.get('pattern','?')!r}, path={inputs.get('path', '.')})"
    if tool in ("Glob",):
        return f"Glob({inputs.get('pattern','?')!r})"
    if tool in ("Agent",):
        return f"Agent({inputs.get('subagent_type','?')}, {inputs.get('description','?')!r})"
    if tool in ("Monitor", "ScheduleWakeup", "TaskStop", "ToolSearch"):
        return f"{tool}(...)"
    return f"{tool}(...)"


def _summarize_output(output, max_chars: int = 240) -> str:
    """Render tool output compactly. May be str or dict."""
    if output is None:
        return ""
    if isinstance(output, dict):
        s = json.dumps(output, ensure_ascii=False)
    else:
        s = str(output)
    s = s.replace("\n", " ")
    if len(s) > max_chars:
        s = s[:max_chars] + "...[truncated]"
    return s


def _render_context(history: list[dict]) -> str:
    """Compact pretty-print of N prior tool events."""
    if not history:
        return "(start of session)"
    lines = []
    for i, ev in enumerate(history, start=1):
        tool = ev.get("tool", "?")
        ipt = ev.get("inputs") or {}
        out = _summarize_output(ev.get("outputs"))
        lines.append(
            f"  step {i}: {_summarize_inputs(tool, ipt)} -> {out}"
        )
    return "\n".join(lines)


def _render_target(tool: str, inputs: dict) -> str:
    """The target the model should learn to produce: tool_name(args_json)."""
    args_json = json.dumps(inputs or {}, ensure_ascii=False, sort_keys=True)
    return f"{tool}({args_json})"


def extract(
    in_path: Path,
    out_path: Path,
    context_window: int = 5,
    skip_failed: bool = True,
    skip_tools: set[str] | None = None,
) -> dict:
    """Walk events, emit JSONL pairs, return stats."""
    skip_tools = skip_tools or {"TaskStop", "Monitor", "ScheduleWakeup", "ToolSearch"}
    by_session: dict[str, list[dict]] = defaultdict(list)
    skipped_other = 0

    with in_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") != "tool_use":
                continue  # file_mutations are derived events, skip
            if skip_failed and ev.get("success") is False:
                continue
            tool = ev.get("tool")
            if not tool or tool in skip_tools:
                skipped_other += 1
                continue
            # Redact secrets from inputs + outputs BEFORE storing
            ev["inputs"] = _sanitize_obj(ev.get("inputs"))
            ev["outputs"] = _sanitize_obj(ev.get("outputs"))
            sid = (ev.get("runtime") or {}).get("session_id") or "unknown"
            by_session[sid].append(ev)

    n_pairs = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fout:
        for sid, events in by_session.items():
            events.sort(key=lambda e: e.get("seq", 0))
            for i, ev in enumerate(events):
                history = events[max(0, i - context_window): i]
                context_block = _render_context(history)
                instruction = (
                    "You are a coding agent working on the slm-learning monorepo. "
                    "Given the recent tool calls in this session, choose the next tool call.\n\n"
                    f"Recent steps:\n{context_block}\n\n"
                    "Next action:"
                )
                target = _render_target(ev.get("tool"), ev.get("inputs") or {})
                fout.write(json.dumps({
                    "instruction": instruction,
                    "command": target,
                    "session": sid,
                    "seq": ev.get("seq"),
                    "tool": ev.get("tool"),
                    "source": "trace-events",
                }, ensure_ascii=False) + "\n")
                n_pairs += 1

    return {
        "sessions": len(by_session),
        "pairs": n_pairs,
        "skipped_unwanted_tools": skipped_other,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--in", dest="in_path", default=".planning/.trace-events.jsonl")
    p.add_argument("--out", dest="out_path", default="data/tool_use_pairs.jsonl")
    p.add_argument("--context-window", type=int, default=5)
    p.add_argument("--include-failed", action="store_true",
                   help="Include events where success=false (default: skip)")
    p.add_argument("--show-samples", type=int, default=2,
                   help="Print N pairs from each session as a sanity check")
    args = p.parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)

    if not in_path.exists():
        print(f"FATAL: input not found: {in_path}", file=sys.stderr)
        return 2

    stats = extract(
        in_path, out_path,
        context_window=args.context_window,
        skip_failed=not args.include_failed,
    )

    print(f"sessions: {stats['sessions']}")
    print(f"pairs:    {stats['pairs']}")
    print(f"skipped (unwanted tools): {stats['skipped_unwanted_tools']}")
    print(f"output:   {out_path}")

    if args.show_samples:
        print(f"\n--- {args.show_samples} sample pairs ---")
        with out_path.open(encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= args.show_samples:
                    break
                p = json.loads(line)
                print(f"\n[pair {i+1}] tool={p['tool']} session={p['session'][:8]}")
                print(f"  instruction (last 200 chars): ...{p['instruction'][-200:]}")
                print(f"  command: {p['command'][:200]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
