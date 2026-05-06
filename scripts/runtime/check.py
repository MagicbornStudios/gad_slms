"""Runtime health probe for the GAD substrate.

Emits per-runtime health JSON: {runtime_id, status, version, last_seen, cooldown_s, errors}.

This is the slm-learning-side counterpart to gad-monorepo phase 138's
`gad runtime check --json`. The contract is: identical JSON shape so the
downstream router (SL-T-04-08) can consume either source.

Usage:
    python scripts/runtime/check.py --json
    python scripts/runtime/check.py --runtimes claude-code,codex-cli --json

Decision context: slm-learning-042 step 1.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GAD_LOG_DIR = REPO_ROOT / ".planning" / ".gad-log"

# (runtime_id, candidate-binaries, version-flag, auth-env-var-or-None)
RUNTIME_PROBES = [
    ("claude-code", ["claude"], "--version", "ANTHROPIC_API_KEY"),
    ("codex-cli", ["codex"], "--version", "OPENAI_API_KEY"),
    ("gemini-cli", ["gemini"], "--version", "GEMINI_API_KEY"),
    ("opencode", ["opencode"], "--version", None),
    ("hf-jobs", ["hf"], "--version", "HF_TOKEN"),
]


def find_binary(candidates):
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None


def get_version(binary, flag):
    try:
        result = subprocess.run(
            [binary, flag],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
        line = (result.stdout.strip() or result.stderr.strip()).splitlines()
        return line[0] if line else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return f"error: {exc.__class__.__name__}"


def last_seen_for(runtime_id):
    """Scan .planning/.gad-log/*.jsonl for the most recent ts where runtime.id == runtime_id."""
    if not GAD_LOG_DIR.exists():
        return None
    latest = None
    for log in sorted(GAD_LOG_DIR.glob("*.jsonl"), reverse=True)[:7]:
        try:
            with log.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rt = (rec.get("runtime") or {}).get("id")
                    if rt == runtime_id:
                        ts = rec.get("ts")
                        if ts and (latest is None or ts > latest):
                            latest = ts
        except OSError:
            continue
        if latest:
            break
    return latest


def probe_runtime(runtime_id, candidates, version_flag, auth_env):
    binary = find_binary(candidates)
    errors = []
    auth_ok = None
    if auth_env:
        auth_ok = bool(os.environ.get(auth_env))
        if not auth_ok:
            errors.append(f"missing env: {auth_env}")
    if binary is None:
        return {
            "runtime_id": runtime_id,
            "status": "missing",
            "binary": None,
            "version": None,
            "auth_ok": auth_ok,
            "last_seen": last_seen_for(runtime_id),
            "cooldown_s": 0,
            "errors": errors + ["binary not on PATH"],
        }
    version = get_version(binary, version_flag)
    status = "ok"
    if version is None or (isinstance(version, str) and version.startswith("error:")):
        status = "degraded"
        errors.append(f"version probe: {version}")
    return {
        "runtime_id": runtime_id,
        "status": status,
        "binary": binary,
        "version": version,
        "auth_ok": auth_ok,
        "last_seen": last_seen_for(runtime_id),
        "cooldown_s": 0,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Probe runtime health for the GAD substrate.")
    parser.add_argument(
        "--runtimes",
        type=str,
        default=None,
        help="Comma-separated runtime ids; defaults to all known runtimes.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON to stdout (default human table).",
    )
    args = parser.parse_args()

    if args.runtimes:
        wanted = {r.strip() for r in args.runtimes.split(",") if r.strip()}
        probes = [p for p in RUNTIME_PROBES if p[0] in wanted]
    else:
        probes = RUNTIME_PROBES

    results = [probe_runtime(*p) for p in probes]
    payload = {
        "schema_version": "slm-learning-runtime-check@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtimes": results,
    }

    if args.json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print(f"Runtime health @ {payload['generated_at']}")
    print("-" * 80)
    print(f"{'runtime':<14} {'status':<10} {'auth':<6} {'binary':<32} {'version':<20}")
    print("-" * 80)
    for r in results:
        auth_disp = "—" if r["auth_ok"] is None else ("yes" if r["auth_ok"] else "NO")
        binary_disp = (r["binary"] or "-")[-32:]
        version_disp = (r["version"] or "-")[:20]
        print(
            f"{r['runtime_id']:<14} {r['status']:<10} {auth_disp:<6} {binary_disp:<32} {version_disp:<20}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
