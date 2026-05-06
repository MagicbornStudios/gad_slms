"""Natural-language → gad CLI translator backed by the local v2 adapter.

User-facing wrapper around the local OpenAI-compatible endpoint
(scripts/serve/start_v2.sh). Takes a natural-language request, hits
the v2 adapter (`scrubster/dr-stein-stage25-qwen15-instruct-v2`,
30/30 GAD-tools), and returns a single `gad` CLI command.

Per slm-learning-051 (Continuous Local Delta Lab): we LOG every
suggestion + user accept/reject to .planning/.trace-events.jsonl so
the data feeds back into Phase 05's first preference-pair training
candidates.

Usage:

    # interactive — prompts for confirmation before running
    python scripts/gad_nl.py "take a note that the build broke on Windows"

    # auto-run (no confirmation, dangerous on production)
    python scripts/gad_nl.py --yes "stamp task SL-T-04-09 done"

    # suggest only — print the command, do not execute
    python scripts/gad_nl.py --dry-run "log a state entry about the multitask run"

    # JSON output (machine-readable)
    python scripts/gad_nl.py --json "show recent decisions"

Recommended shell alias (Bash / Git Bash / WSL):

    alias gad?='python /c/Users/benja/Documents/slm_learning/scripts/gad_nl.py'

Recommended PowerShell function:

    function gadq { python C:\\Users\\benja\\Documents\\slm_learning\\scripts\\gad_nl.py $args }

Configuration via env:

    GAD_NL_ENDPOINT  default http://127.0.0.1:8000/v1/chat/completions
    GAD_NL_MODEL     default adapter
    GAD_NL_TIMEOUT   default 30
    GAD_NL_PROJECT   default current-dir's project (auto-detected from CLAUDE.md)

Decision refs: slm-learning-022 (1.5B Qwen base), slm-learning-040
(serving substrate), slm-learning-051 (CLDL — candidates only),
slm-learning-052 (NL view, never source).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = ROOT / ".planning" / ".trace-events.jsonl"

DEFAULT_ENDPOINT = os.environ.get(
    "GAD_NL_ENDPOINT", "http://127.0.0.1:8000/v1/chat/completions"
)
DEFAULT_MODEL = os.environ.get("GAD_NL_MODEL", "adapter")
DEFAULT_TIMEOUT = int(os.environ.get("GAD_NL_TIMEOUT", "30"))


SYSTEM_PROMPT = (
    "You are Dr. Stein. Translate the user's request into a single gad CLI "
    "command. Output only the command on one line. Begin the command with "
    "the literal token 'gad' followed by the subcommand and flags. Do not "
    "include backticks, prose, explanations, or trailing newlines."
)


def detect_project_id() -> str:
    """Best-effort: use the project id from CLAUDE.md or fall back."""
    claude_md = ROOT / "CLAUDE.md"
    if claude_md.exists():
        for line in claude_md.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"^\s*Project id:\s*`?([a-zA-Z0-9_\-]+)`?", line)
            if m:
                return m.group(1)
    return os.environ.get("GAD_NL_PROJECT", "slm-learning")


def call_endpoint(prompt: str, *, endpoint: str, model: str, timeout: int) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 128,
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise SystemExit(
            f"[gad_nl] endpoint {endpoint} unreachable: {e}\n"
            f"[gad_nl] start the server first: bash scripts/serve/start_v2.sh "
            f"(or --windows on Windows host)"
        )
    choices = payload.get("choices", [])
    if not choices:
        raise SystemExit("[gad_nl] empty response from endpoint")
    return choices[0]["message"]["content"].strip()


def sanitize_command(cmd: str) -> tuple[str, list[str]]:
    """Strip prose / fences. Return (clean_cmd, warnings)."""
    warnings: list[str] = []
    # Drop fenced blocks but keep contents.
    cmd = re.sub(r"^```[a-z]*\n?", "", cmd)
    cmd = re.sub(r"\n?```$", "", cmd)
    cmd = cmd.strip()
    # Single-line only — take the first non-empty line.
    lines = [l for l in cmd.splitlines() if l.strip()]
    if not lines:
        raise SystemExit("[gad_nl] model returned empty content")
    if len(lines) > 1:
        warnings.append(f"model returned {len(lines)} lines — using only the first")
    cmd = lines[0].strip()
    if cmd.startswith("`") and cmd.endswith("`"):
        cmd = cmd[1:-1].strip()
    if cmd.startswith("$ "):
        cmd = cmd[2:].strip()
    if not cmd.startswith("gad "):
        warnings.append(f"output does not start with 'gad ' — got: {cmd[:60]!r}")
    return cmd, warnings


def log_trace(event: dict) -> None:
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def trace_event(*, prompt: str, suggestion: str, warnings: list[str], action: str,
                project_id: str) -> dict:
    return {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": "gad_nl",
        "soul": "dr-stein",
        "project": project_id,
        "prompt": prompt,
        "suggestion": suggestion,
        "warnings": warnings,
        "action": action,           # "executed" | "rejected" | "dry_run" | "auto_executed"
        "decision_ref": "slm-learning-051 + slm-learning-052",
    }


def confirm_and_run(cmd: str, warnings: list[str]) -> str:
    print(f"\n[gad_nl] suggestion: {cmd}")
    if warnings:
        for w in warnings:
            print(f"[gad_nl]   warning: {w}")
    try:
        choice = input("[gad_nl] run it? [y/N/edit] ").strip().lower()
    except EOFError:
        return "rejected"
    if choice == "y":
        proc = subprocess.run(cmd, shell=True)
        return "executed" if proc.returncode == 0 else "executed_failed"
    if choice == "edit":
        try:
            new_cmd = input("[gad_nl] edited command: ").strip()
        except EOFError:
            return "rejected"
        if new_cmd:
            proc = subprocess.run(new_cmd, shell=True)
            return "executed_edited"
    return "rejected"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="+", help="Natural-language request")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Run the suggested command without confirmation")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the suggestion only, do not execute")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON to stdout (machine-readable)")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    prompt = " ".join(args.prompt)
    project_id = detect_project_id()
    raw = call_endpoint(prompt, endpoint=args.endpoint, model=args.model, timeout=args.timeout)
    cmd, warnings = sanitize_command(raw)

    if args.json:
        log_trace(trace_event(
            prompt=prompt, suggestion=cmd, warnings=warnings,
            action="suggested", project_id=project_id,
        ))
        print(json.dumps({
            "prompt": prompt,
            "suggestion": cmd,
            "warnings": warnings,
            "endpoint": args.endpoint,
            "model": args.model,
            "project_id": project_id,
        }, indent=2))
        return 0

    if args.dry_run:
        log_trace(trace_event(
            prompt=prompt, suggestion=cmd, warnings=warnings,
            action="dry_run", project_id=project_id,
        ))
        print(f"[gad_nl] suggestion: {cmd}")
        for w in warnings:
            print(f"[gad_nl]   warning: {w}")
        return 0

    if args.yes:
        log_trace(trace_event(
            prompt=prompt, suggestion=cmd, warnings=warnings,
            action="auto_executed", project_id=project_id,
        ))
        proc = subprocess.run(cmd, shell=True)
        return proc.returncode

    action = confirm_and_run(cmd, warnings)
    log_trace(trace_event(
        prompt=prompt, suggestion=cmd, warnings=warnings,
        action=action, project_id=project_id,
    ))
    return 0 if action.startswith("executed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
