"""Kael CLI — K0 text-only.

Per soul `narrative/souls/kael.md` and decision `slm-learning-084`. The
front door of the GAD council. Voice + tool integrations come in K1/K2/K3.

Subcommands:

    kael ask "..."           propose an action, approval-gated
    kael note "..."          shortcut: gad note add
    kael snapshot            shortcut: gad snapshot summary in plain text
    kael queue               show pending training queue jobs
    kael approve <action>    re-execute a previously-rejected action with stamp
    kael route "..."         classify intent + route to right soul (Dr. Stein, Gilgamesh, etc.)

Trace logs land at .planning/.trace-events.jsonl with source=kael for
the data flywheel (slm-learning-086).

Usage:

    python scripts/kael/kael.py ask "take a note that doc-verifier corpus is ready"
    python scripts/kael/kael.py snapshot
    python scripts/kael/kael.py queue

Recommended shell shim (Bash / Git Bash):

    alias kael='python /c/Users/benja/Documents/slm_learning/scripts/kael/kael.py'

Decision refs: slm-learning-075, slm-learning-084, slm-learning-085, slm-learning-086.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACE_PATH = ROOT / ".planning" / ".trace-events.jsonl"
QUEUE_DIR = ROOT / "experiments" / "queue"


# Local imports work after we ensure the scripts/kael dir is on sys.path
sys.path.insert(0, str(Path(__file__).parent))
from action_schema import (  # type: ignore[import]
    Action,
    classify_intent,
    blast_radius_for,
    requires_approval_for,
    rollback_plan_for,
    NO_SIDE_EFFECT_INTENTS,
)


def log_trace(payload: dict) -> None:
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload.setdefault("ts", dt.datetime.now(dt.timezone.utc).isoformat())
    payload.setdefault("source", "kael")
    payload.setdefault("soul", "kael")
    with TRACE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def quote_for_gad(text: str) -> str:
    """Shell-quote for the gad CLI on Windows + bash."""
    return text.replace('"', '\\"')


def propose_for_intent(intent: str, text: str) -> Action:
    proposal: str
    command: str | None = None
    if intent == "note":
        body = text.lower()
        for p in ["take a note that", "take a note", "add a note that",
                 "add a note", "note that", "log a note that"]:
            if p in body:
                body = text[body.find(p) + len(p):].strip()
                break
        body = body.strip(":,. ").strip()
        if not body:
            body = text
        proposal = f"Append a note to .planning/notes/ with body: {body[:120]}{'...' if len(body) > 120 else ''}"
        slug = body[:40].lower().replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-").strip("-") or "untitled"
        command = f'gad note add {slug} --projectid slm-learning --title "{quote_for_gad(body[:80])}" --body "{quote_for_gad(body)}"'
    elif intent == "state_log":
        body = text.strip(":,. ")
        for p in ["log that", "log a state entry", "state log", "record that"]:
            if p in body.lower():
                idx = body.lower().find(p) + len(p)
                body = body[idx:].strip(":,. ").strip()
                break
        if not body:
            body = text
        proposal = f"Append a state log entry: {body[:120]}{'...' if len(body) > 120 else ''}"
        command = f'gad state log "{quote_for_gad(body)}" --projectid slm-learning'
    elif intent == "snapshot":
        proposal = "Read project snapshot (read-only, no side effects)"
        command = "gad snapshot --projectid slm-learning"
    elif intent == "tasks_list":
        proposal = "List slm-learning tasks (read-only)"
        command = "gad tasks list --projectid slm-learning"
    elif intent == "decisions_list":
        proposal = "List slm-learning decisions (read-only)"
        command = "gad decisions list --projectid slm-learning"
    elif intent == "handoffs_list":
        proposal = "List open handoffs in slm-learning queue (read-only)"
        command = "gad handoffs list --projectid slm-learning"
    elif intent == "summarize":
        proposal = "Summarize current state via gad snapshot then NL summary"
        command = "gad snapshot --projectid slm-learning"
    elif intent in {"draft_email", "draft_message"}:
        proposal = f"DRAFT ONLY ({intent}) — would compose a message via the model gateway. NO SEND. Awaits operator approval to write to clipboard or drafts folder."
        command = None
    elif intent in {"publish", "deploy", "purchase", "browser_action"}:
        proposal = f"REFUSED-by-default: {intent} requires explicit per-action operator confirmation per slm-learning-075. Restate the request with --i-am-aware-this-is-outbound."
        command = None
    elif intent == "task_create":
        proposal = f"Create a new task with goal: {text[:120]}"
        command = None  # need a task id; defer to operator
    else:
        proposal = f"Unclassified intent. Will route to Dr. Stein for interpretation. Original request: {text[:200]}"
        command = None

    return Action(
        intent=intent,
        proposal=proposal,
        command=command,
        blast_radius=blast_radius_for(intent),
        requires_approval=requires_approval_for(intent),
        rollback_plan=rollback_plan_for(intent, command),
    )


def confirm(prompt: str) -> bool:
    try:
        ans = input(f"{prompt} [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in {"y", "yes"}


def cmd_ask(args: argparse.Namespace) -> int:
    text = " ".join(args.text).strip()
    if not text:
        print("[kael] no text given")
        return 2

    intent = classify_intent(text)
    action = propose_for_intent(intent, text)

    log_trace({
        "kind": "kael_proposal",
        "request": text,
        "intent": action.intent,
        "command": action.command,
        "blast_radius": action.blast_radius,
        "requires_approval": action.requires_approval,
    })

    print(f"[kael] intent: {action.intent} (blast_radius={action.blast_radius})")
    print(f"[kael] proposal: {action.proposal}")
    if action.command:
        print(f"[kael] command: {action.command}")
    if action.requires_approval and not args.yes:
        if not action.command:
            print(f"[kael] no executable command for this intent (rollback: {action.rollback_plan})")
            log_trace({"kind": "kael_action_status", "status": "no_command",
                       "intent": action.intent})
            return 0
        if not confirm("[kael] approve and execute?"):
            print("[kael] rejected — not executing")
            log_trace({"kind": "kael_action_status", "status": "rejected",
                       "intent": action.intent})
            return 0
    elif action.requires_approval and args.yes and action.blast_radius == "high":
        print("[kael] --yes is not honored for blast_radius=high. Approve interactively or restate request.")
        log_trace({"kind": "kael_action_status", "status": "high_blast_yes_refused",
                   "intent": action.intent})
        return 1

    if not action.command:
        return 0

    proc = subprocess.run(action.command, shell=True)
    status = "executed" if proc.returncode == 0 else "executed_failed"
    log_trace({"kind": "kael_action_status", "status": status,
               "intent": action.intent, "exit_code": proc.returncode})
    return proc.returncode


def cmd_note(args: argparse.Namespace) -> int:
    args.text = ["take", "a", "note", "that"] + args.body
    args.yes = False
    return cmd_ask(args)


def cmd_snapshot(_: argparse.Namespace) -> int:
    print("[kael] running snapshot ...")
    log_trace({"kind": "kael_snapshot_call"})
    return subprocess.run(
        "gad snapshot --projectid slm-learning", shell=True
    ).returncode


def cmd_queue(_: argparse.Namespace) -> int:
    print("[kael] training queue:")
    if not QUEUE_DIR.exists():
        print(f"  (queue dir {QUEUE_DIR} does not exist yet)")
        return 0
    for state in ("pending", "running", "evaluated", "promoted", "rejected"):
        d = QUEUE_DIR / state
        if not d.exists():
            continue
        jobs = sorted(d.glob("*.json"))
        print(f"  {state}: {len(jobs)} job(s)")
        for j in jobs[:5]:
            try:
                spec = json.loads(j.read_text(encoding="utf-8"))
                print(f"    - {spec.get('job_id', j.stem)}  base={spec.get('base_model', '?')}  rank={spec.get('rank', '?')}  target={spec.get('compute_target', '?')}")
            except (OSError, json.JSONDecodeError):
                print(f"    - {j.name} (parse error)")
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    text = " ".join(args.text).strip()
    intent = classify_intent(text)
    if intent in {"snapshot", "tasks_list", "decisions_list", "handoffs_list",
                  "summarize", "note", "state_log"}:
        soul = "kael"
        reason = "in Kael's no-side-effect surface"
    elif intent in {"task_create", "task_stamp", "decision_log"}:
        soul = "archivist"
        reason = "memory + decisions ownership"
    elif intent in {"draft_email", "draft_message"}:
        soul = "kael"
        reason = "drafting is Kael's surface; sending requires operator approval"
    elif intent in {"publish", "deploy", "purchase"}:
        soul = "operator-only"
        reason = "outbound side effects require human stamp"
    else:
        soul = "dr-stein"
        reason = "unclassified — defer to model-improvement scientist for interpretation"

    payload = {
        "intent": intent,
        "soul_routed_to": soul,
        "reason": reason,
        "request": text,
    }
    log_trace({"kind": "kael_route", **payload})
    print(json.dumps(payload, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    ask = sub.add_parser("ask", help="Propose an action from natural language")
    ask.add_argument("text", nargs="+")
    ask.add_argument("--yes", "-y", action="store_true",
                     help="Approve non-high-blast actions without prompt")
    ask.set_defaults(func=cmd_ask)

    note = sub.add_parser("note", help="Shortcut: take a note")
    note.add_argument("body", nargs="+")
    note.set_defaults(func=cmd_note)

    snap = sub.add_parser("snapshot", help="Run gad snapshot --projectid slm-learning")
    snap.set_defaults(func=cmd_snapshot)

    queue = sub.add_parser("queue", help="Show training queue contents")
    queue.set_defaults(func=cmd_queue)

    route = sub.add_parser("route", help="Classify intent + identify which soul should handle it")
    route.add_argument("text", nargs="+")
    route.set_defaults(func=cmd_route)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
