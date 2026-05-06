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

# (runtime_id, candidate-binaries, version-flag, provider_auth_envs, serving_modes)
# serving_modes documents which endpoints the CLI can target. When the CLI is
# pointed at OUR vLLM endpoint (serving_mode="own"), no provider auth is
# required — the auth check is informational, not a health gate.
RUNTIME_PROBES = [
    ("claude-code", ["claude"], "--version", ["ANTHROPIC_API_KEY"], ["own", "provider"]),
    ("codex-cli", ["codex"], "--version", ["OPENAI_API_KEY"], ["own", "provider"]),
    ("gemini-cli", ["gemini"], "--version", ["GEMINI_API_KEY"], ["own", "provider"]),
    ("opencode", ["opencode"], "--version", [], ["own", "provider"]),
    ("hf-jobs", ["hf", "huggingface-cli"], "--version", ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"], ["provider"]),
]


def _which_extensionless(name):
    """Windows-friendly PATH scan that accepts extensionless executables.

    shutil.which on Windows requires a PATHEXT match. Tools installed by
    pip/uv often land as bare-name shim scripts in .local/bin and never
    pick up an extension. We scan PATH directories explicitly and accept
    any of: name, name.exe, name.cmd, name.bat.
    """
    sep = os.pathsep
    extensions = ["", ".exe", ".cmd", ".bat", ".ps1"]
    for d in os.environ.get("PATH", "").split(sep):
        if not d:
            continue
        for ext in extensions:
            candidate = os.path.join(d, name + ext)
            if os.path.isfile(candidate):
                return candidate
    return None


def find_binary(candidates):
    for name in candidates:
        path = shutil.which(name) or _which_extensionless(name)
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


def python_module_health(runtime_id):
    """For runtimes whose binary is optional (hf-jobs uses huggingface_hub
    directly), check if the Python library is importable — that's a valid
    health signal independent of the binary shim."""
    if runtime_id == "hf-jobs":
        try:
            import huggingface_hub  # noqa: F401
            return True, getattr(huggingface_hub, "__version__", "unknown")
        except ImportError:
            return False, None
    return None, None


def probe_runtime(runtime_id, candidates, version_flag, provider_auth_envs, serving_modes):
    binary = find_binary(candidates)
    notes = []
    # Provider auth is OPTIONAL when the CLI is pointed at our own vLLM
    # endpoint (serving_mode="own"). We probe env vars informationally;
    # missing provider creds do not flag the runtime as unhealthy.
    provider_auth_ok = None
    if provider_auth_envs:
        provider_auth_ok = any(os.environ.get(e) for e in provider_auth_envs)
        if not provider_auth_ok:
            notes.append(
                f"no provider auth env ({'/'.join(provider_auth_envs)}); "
                f"OK if running in own-endpoint mode"
            )
    if binary is None:
        return {
            "runtime_id": runtime_id,
            "status": "missing",
            "binary": None,
            "version": None,
            "provider_auth_ok": provider_auth_ok,
            "serving_modes": serving_modes,
            "last_seen": last_seen_for(runtime_id),
            "cooldown_s": 0,
            "notes": notes + ["binary not on PATH"],
        }
    version = get_version(binary, version_flag)
    status = "ok"
    if version is None or (isinstance(version, str) and version.startswith("error:")):
        status = "degraded"
        notes.append(f"version probe: {version}")
        # Some runtimes (hf-jobs) ship as Python entry scripts that Windows
        # can't subprocess directly. Fall back to Python module import check.
        py_ok, py_version = python_module_health(runtime_id)
        if py_ok:
            status = "ok"
            version = f"python-module {py_version}"
            notes.append(
                "binary not invokable from subprocess; using Python module fallback"
            )
    return {
        "runtime_id": runtime_id,
        "status": status,
        "binary": binary,
        "version": version,
        "provider_auth_ok": provider_auth_ok,
        "serving_modes": serving_modes,
        "last_seen": last_seen_for(runtime_id),
        "cooldown_s": 0,
        "notes": notes,
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
    print("-" * 90)
    print(f"{'runtime':<14} {'status':<10} {'modes':<14} {'prov_auth':<10} {'binary':<28} {'version':<14}")
    print("-" * 90)
    for r in results:
        if r["provider_auth_ok"] is None:
            auth_disp = "n/a"
        else:
            auth_disp = "yes" if r["provider_auth_ok"] else "off"
        modes_disp = "/".join(r["serving_modes"]) or "-"
        binary_disp = (r["binary"] or "-")[-28:]
        version_disp = (r["version"] or "-")[:14]
        print(
            f"{r['runtime_id']:<14} {r['status']:<10} {modes_disp:<14} {auth_disp:<10} {binary_disp:<28} {version_disp:<14}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
