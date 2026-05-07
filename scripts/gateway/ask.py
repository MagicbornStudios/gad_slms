"""
gad ask — natural-language entry to the gad CLI.

Pipes a free-form prompt through the gateway router with intent=cli_translation,
returns a `gad <subcommand> ...` translation, and optionally executes it.

Usage:
    .venv/Scripts/python.exe scripts/gateway/ask.py "show me what's open in phase 145"
    .venv/Scripts/python.exe scripts/gateway/ask.py "stamp 152-bridge as done" --exec
    .venv/Scripts/python.exe scripts/gateway/ask.py "list pressure signals" --json

Routing is rule-based today (slm-learning-085) — intent=cli_translation + risk=low
goes to the local v2 SLM. If the local endpoint is unreachable, falls back to
frontier (Opus/GPT-5) so the bridge degrades gracefully on any host.

Decision refs: slm-learning-085, slm-learning-086.
Phase: bridge work for the SLM-as-CLI-frontend hypothesis (operator 2026-05-07).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.gateway.route import (  # type: ignore[import-not-found]
    RoutingDecision,
    decide,
    call_local,
    log_decision,
    LOCAL_ENDPOINT,
    LOCAL_MODEL,
)


SYSTEM_PROMPT = """You are a CLI translator for the gad command-line tool.

Translate the user's natural-language request into a single `gad` command line.
Only output the command — no explanation, no markdown fences, no comments.

Available top-level commands (most useful for translation):
  gad snapshot --projectid <id>                  state + roadmap + tasks
  gad tasks list --projectid <id> [--status done|planned|active] [--phase <n>]
  gad tasks show <id> --projectid <id>
  gad tasks stamp <id> --projectid <id> --status done [--skill-id <skill>]
  gad phases list --projectid <id>
  gad phases sweep --auto-close --projectid <id>
  gad decisions list --projectid <id> [--search <text>]
  gad decisions show <id> --projectid <id>
  gad decisions add <id> --projectid <id> --summary "<text>"
  gad handoffs list [--mine-first]
  gad handoffs claim-next --runtime <id>
  gad note add <slug> --projectid <id> --body "<text>"
  gad state log "<one-line>" --projectid <id>
  gad query run "<NL>" [--projectid <id>] [--type phase|task|decision]
  gad evolution evolve --projectid <id>
  gad evolution level-up --projectid <id>
  gad next --projectid <id>
  gad sprint show --projectid <id>
  gad runtime launch --projectid <id> --force-runtime <r> --launch-args "<args>"
  gad team start --profile <name> --projectid <id>
  gad agents list

Project ids commonly seen: global, slm-learning, get-anything-done, magicborn.
If the user gives a phrase that maps to a phase number (e.g. "phase 145"),
infer --phase 145. If they reference an entity by short id (145-01, gad-285),
pass it as the positional id without the project-prefix decoration.

Output only the command. One line. No quoting around the whole thing."""


def is_local_alive(endpoint: str = LOCAL_ENDPOINT, timeout: float = 1.5) -> bool:
    """Quick health check on the local OpenAI-compatible endpoint."""
    health_url = endpoint.replace("/v1/chat/completions", "/v1/models").replace("/chat/completions", "/models")
    try:
        with urllib.request.urlopen(health_url, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


def call_frontier_fallback(prompt: str, system: str) -> str:
    """Use whatever frontier CLI is available as a backstop when local is down."""
    combined = f"{system}\n\n---\nUser request: {prompt}"
    candidates = [
        ("claude", ["claude", "-p", combined]),
        ("codex", ["codex", "exec", "--full-auto", "--skip-git-repo-check", combined]),
        ("gemini", ["gemini", "-p", combined]),
    ]
    for cli, args in candidates:
        if not shutil.which(cli):
            continue
        try:
            out = subprocess.run(args, capture_output=True, text=True, timeout=120, check=True)
            return out.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            stderr_tail = (e.stderr if hasattr(e, "stderr") else "")[-200:] if hasattr(e, "stderr") else ""
            print(f"[ask] frontier {cli} failed (rc={getattr(e, 'returncode', '?')}): {stderr_tail}",
                  file=sys.stderr)
            continue
    raise RuntimeError(
        "No frontier CLI succeeded. Start the local v2 SLM (scripts/serve/start_v2.sh) "
        "or verify claude/codex/gemini auth."
    )


def extract_command(raw: str) -> str:
    """Strip code fences, system noise, leading 'bash$'/`>`/`$ ` if SLM emits them."""
    text = raw.strip()
    if text.startswith("```"):
        # strip leading ```lang and trailing ```
        text = "\n".join(line for line in text.splitlines() if not line.startswith("```")).strip()
    text = text.lstrip("$ ").lstrip("> ").lstrip("bash$ ").strip()
    # take only the first non-empty line (defensive against multiline output)
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("prompt", help="Natural-language request, e.g. 'show me phase 145 tasks'")
    parser.add_argument("--exec", action="store_true", dest="execute",
                        help="Execute the translated command (default: print only)")
    parser.add_argument("--json", action="store_true",
                        help="Emit decision + command as JSON instead of text")
    parser.add_argument("--no-fallback", action="store_true",
                        help="Refuse to fall back to frontier if local is down")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print routing decision + assembled prompt; do not call any backend")
    args = parser.parse_args()

    decision = decide("cli_translation", "low")
    log_decision(decision, args.prompt)

    if args.dry_run:
        local_alive = is_local_alive(decision.endpoint) if decision.backend in {"local-v2", "local-base"} else False
        print(json.dumps({
            "prompt": args.prompt,
            "decision": {
                "intent": decision.intent,
                "risk": decision.risk,
                "backend": decision.backend,
                "model_id": decision.model_id,
                "endpoint": decision.endpoint,
            },
            "local_alive": local_alive,
            "would_use": decision.backend if local_alive else "frontier-fallback",
            "system_prompt_chars": len(SYSTEM_PROMPT),
        }, indent=2))
        return 0

    used_backend = decision.backend
    if decision.backend in {"local-v2", "local-base"}:
        if is_local_alive(decision.endpoint):
            try:
                raw = call_local(
                    args.prompt, system=SYSTEM_PROMPT,
                    endpoint=decision.endpoint, model=decision.model_id,
                )
            except RuntimeError as e:
                if args.no_fallback:
                    print(f"[ask] local failed: {e}", file=sys.stderr)
                    return 1
                raw = call_frontier_fallback(args.prompt, SYSTEM_PROMPT)
                used_backend = "frontier-fallback"
        else:
            if args.no_fallback:
                print(f"[ask] local endpoint {decision.endpoint} unreachable. Start scripts/serve/start_v2.sh.",
                      file=sys.stderr)
                return 1
            raw = call_frontier_fallback(args.prompt, SYSTEM_PROMPT)
            used_backend = "frontier-fallback"
    else:
        raw = call_frontier_fallback(args.prompt, SYSTEM_PROMPT)
        used_backend = decision.backend

    cmd = extract_command(raw)

    if args.json:
        print(json.dumps({
            "prompt": args.prompt,
            "command": cmd,
            "backend": used_backend,
            "model_id": decision.model_id,
            "executed": False,
        }, indent=2))
    else:
        print(f"# [{used_backend}] ->")
        print(cmd)

    if args.execute:
        if not cmd.startswith("gad "):
            print(f"[ask] refusing to exec — translation does not start with 'gad ': {cmd!r}",
                  file=sys.stderr)
            return 2
        print("\n[ask] executing...\n", file=sys.stderr)
        # split on whitespace honoring simple quoting
        import shlex
        proc = subprocess.run(shlex.split(cmd, posix=False))
        return proc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
