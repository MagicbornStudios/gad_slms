"""Action schema for Kael's proposed actions.

Every action Kael proposes carries:
- intent (what the operator asked)
- proposal (what Kael wants to do)
- blast_radius (low | medium | high)
- requires_approval (always true outside the no-side-effect set)
- rollback_plan (how to undo if approved-then-regretted)
- soul (always 'kael')
- decision_ref (which decision authorizes this surface)

Approval is the gate. Per `slm-learning-075`, Kael never auto-publishes
to the outside world, never makes purchases, never impersonates the
operator, never auto-promotes a model.

The no-side-effect set (Kael may execute without approval):
- gad note add
- gad state log
- gad snapshot (read-only)
- gad tasks list (read-only)
- gad decisions list (read-only)
- gad handoffs list (read-only)
- internal file reads
- internal classification calls

Everything else requires explicit operator confirmation.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Literal


BlastRadius = Literal["low", "medium", "high"]
Intent = Literal[
    "note",
    "state_log",
    "task_create",
    "task_stamp",
    "decision_log",
    "snapshot",
    "tasks_list",
    "decisions_list",
    "handoffs_list",
    "draft_email",
    "draft_message",
    "publish",  # always high-risk
    "deploy",   # always high-risk
    "purchase", # always high-risk
    "browser_action",  # always high-risk
    "summarize",
    "route_to_soul",
    "unknown",
]


NO_SIDE_EFFECT_INTENTS: set[str] = {
    "snapshot", "tasks_list", "decisions_list", "handoffs_list",
    "summarize", "note", "state_log",
}


@dataclass
class Action:
    """A single Kael-proposed action with approval metadata."""
    intent: str
    proposal: str  # human-readable summary of what will happen
    command: str | None  # the actual shell command if applicable
    blast_radius: BlastRadius
    requires_approval: bool
    rollback_plan: str
    soul: str = "kael"
    decision_refs: list[str] = field(default_factory=lambda: ["slm-learning-075", "slm-learning-084"])
    ts: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    status: str = "proposed"  # proposed | approved | rejected | executed | failed | reverted
    operator_note: str | None = None
    result_summary: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def classify_intent(text: str) -> Intent:
    """Heuristic intent classifier. Replaceable later by an SLM classifier
    (Phase K2 candidate per slm-learning-051 — local Tier 0 target)."""
    t = text.lower().strip()
    if any(p in t for p in ["take a note", "add a note", "note that", "log a note"]):
        return "note"
    if any(p in t for p in ["state log", "log that", "log a state", "record that"]):
        return "state_log"
    if any(p in t for p in ["add a task", "new task", "create a task"]):
        return "task_create"
    if any(p in t for p in ["mark task", "stamp task", "complete task", "task done"]):
        return "task_stamp"
    if any(p in t for p in ["log a decision", "add a decision", "record decision"]):
        return "decision_log"
    if "snapshot" in t or "what's the state" in t or "where are we" in t:
        return "snapshot"
    if "list tasks" in t or "show tasks" in t or "what tasks" in t or "tasks list" in t:
        return "tasks_list"
    if "list decisions" in t or "show decisions" in t or "what decisions" in t:
        return "decisions_list"
    if "list handoffs" in t or "show handoffs" in t:
        return "handoffs_list"
    if "draft" in t and "email" in t:
        return "draft_email"
    if "draft" in t and ("message" in t or "reply" in t or "post" in t):
        return "draft_message"
    if any(p in t for p in ["publish", "post to", "send to", "tweet"]):
        return "publish"
    if any(p in t for p in ["deploy", "ship", "release"]):
        return "deploy"
    if any(p in t for p in ["buy", "purchase", "order"]):
        return "purchase"
    if any(p in t for p in ["open browser", "navigate to", "click on", "visit"]):
        return "browser_action"
    if any(p in t for p in ["summarize", "summary", "tldr"]):
        return "summarize"
    return "unknown"


def blast_radius_for(intent: str) -> BlastRadius:
    if intent in NO_SIDE_EFFECT_INTENTS:
        return "low"
    if intent in {"task_create", "task_stamp", "decision_log", "draft_email", "draft_message"}:
        return "medium"
    if intent in {"publish", "deploy", "purchase", "browser_action"}:
        return "high"
    return "medium"


def requires_approval_for(intent: str) -> bool:
    """Per slm-learning-075: outbound + irreversible always require approval."""
    return intent not in NO_SIDE_EFFECT_INTENTS


def rollback_plan_for(intent: str, command: str | None) -> str:
    if intent == "note":
        return "ignore the note (no destructive impact)"
    if intent == "state_log":
        return "append a corrective state log entry; original is preserved"
    if intent == "task_create":
        return f"gad tasks rm <task-id> if needed (the new task)"
    if intent == "task_stamp":
        return "re-stamp task with prior status"
    if intent == "decision_log":
        return "edit DECISIONS.xml to add a counter-decision; original preserved per Archivist policy"
    if intent in {"draft_email", "draft_message"}:
        return "delete the draft before sending; nothing leaves the machine"
    if intent in NO_SIDE_EFFECT_INTENTS:
        return "no rollback needed (read-only)"
    return "varies — operator must verify before executing"
