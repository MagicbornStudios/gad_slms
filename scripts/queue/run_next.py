"""Training queue runner — pick the next pending job, run it, record the verdict.

Per decision `slm-learning-081`: training factory shape with five
buckets. This script is the worker: it picks the oldest pending job,
atomically renames it to running, shells out to the trainer, captures
the verdict, atomically renames to evaluated.

Atomicity: same fs.rename pattern as `.planning/handoffs/`. Two
concurrent runners cannot pick the same job (the rename either
succeeds for one and fails for the other).

Usage:

    # Pick the next pending job that matches our compute target
    .venv-gpu/Scripts/python.exe scripts/queue/run_next.py \\
        --target local-1660ti

    # Dry-run (don't actually train, just validate + move job through buckets)
    .venv-gpu/Scripts/python.exe scripts/queue/run_next.py \\
        --target local-1660ti --dry-run

    # Run forever (re-pick after each completion; stop on empty pending)
    .venv-gpu/Scripts/python.exe scripts/queue/run_next.py \\
        --target local-1660ti --loop

NEVER auto-promotes. Per `slm-learning-051`. The runner only writes
verdict.json + moves spec from running/ to evaluated/. Promotion to
canonical/staging is a separate manual step via
`scripts/delta/promote_atomic.py`.

Decision refs: slm-learning-051, slm-learning-081, slm-learning-082.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "experiments" / "queue"
TRACE_PATH = ROOT / ".planning" / ".trace-events.jsonl"


def log_trace(payload: dict) -> None:
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload.setdefault("ts", dt.datetime.now(dt.timezone.utc).isoformat())
    payload.setdefault("source", "queue_runner")
    with TRACE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def list_pending(target: str | None) -> list[Path]:
    pending = QUEUE / "pending"
    if not pending.exists():
        return []
    candidates: list[tuple[float, Path]] = []
    for p in pending.glob("*.json"):
        try:
            spec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if spec.get("status") == "blocked-on-deps":
            continue
        if target and spec.get("compute_target") != target:
            continue
        # Order by created_at ascending; fall back to mtime
        ts = spec.get("created_at") or ""
        order = ts if ts else str(p.stat().st_mtime)
        candidates.append((order, p))
    candidates.sort()
    return [p for _, p in candidates]


def claim(job_path: Path, claimed_by: str) -> Path | None:
    """Atomic move pending/<id>.json -> running/<id>.json."""
    running = QUEUE / "running" / job_path.name
    running.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(job_path, running)
    except OSError:
        return None  # someone else got it
    spec = json.loads(running.read_text(encoding="utf-8"))
    spec["claimed_by"] = claimed_by
    spec["claimed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    running.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return running


def write_verdict(running_path: Path, verdict: dict) -> Path:
    """Move running/<id>.json -> evaluated/<id>.json + verdict.json beside it."""
    eval_dir = QUEUE / "evaluated"
    eval_dir.mkdir(parents=True, exist_ok=True)
    target = eval_dir / running_path.name
    spec = json.loads(running_path.read_text(encoding="utf-8"))
    spec["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    verdict_path = eval_dir / (running_path.stem + ".verdict.json")
    verdict_path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    spec["verdict_path"] = str(verdict_path)
    running_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    os.rename(running_path, target)
    return target


def run_trainer(spec: dict, dry_run: bool = False) -> dict:
    config_path = spec.get("config_path")
    if not config_path:
        return {"status": "error", "error": "no config_path in spec"}

    config_abs = ROOT / config_path
    if not config_abs.exists():
        return {"status": "error", "error": f"config not found: {config_path}"}

    # Choose interpreter — the trainer needs CUDA for real runs.
    target = spec.get("compute_target", "local-1660ti")
    if target.startswith("local-"):
        py = ROOT / ".venv-gpu" / "Scripts" / "python.exe"
    else:
        # Remote targets — we just emit the spec; runner script doesn't
        # actually invoke remote runners (that's a future hook).
        return {
            "status": "deferred-remote",
            "compute_target": target,
            "reason": "remote runner not implemented; remove --target=remote and run via HF Jobs CLI",
            "spec_summary": {k: spec.get(k) for k in ("job_id", "rank", "dataset", "evals")},
        }

    cmd = [str(py), str(ROOT / "scripts" / "18_stage25_finetune.py"),
           "--config", str(config_abs)]
    if dry_run:
        cmd.append("--dry-run")

    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")

    t0 = time.time()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    wall = time.time() - t0

    return {
        "status": "ok" if proc.returncode == 0 else "trainer_failed",
        "returncode": proc.returncode,
        "wall_seconds": wall,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }


def make_verdict(spec: dict, train_result: dict, *, target_name: str) -> dict:
    """Build the verdict envelope per slm-learning-071 (T1+ evidence tier).

    NOTE: This is deliberately conservative. Real eval scoring still
    happens via the trainer's eval_hook + scripts/delta/eval_candidate.py
    after training completes. This script only records that the train
    step ran — the council still has to score the candidate.
    """
    return {
        "schema_v": 1,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "job_id": spec.get("job_id"),
        "config_path": spec.get("config_path"),
        "compute_target": spec.get("compute_target"),
        "evidence_tier": "T1",
        "train_result": train_result,
        "next_step": (
            "Run scripts/delta/eval_candidate.py against the candidate dir + baseline. "
            "Verdict = verified|refuted|inconclusive. Do not promote without "
            "scripts/delta/promote_atomic.py and a slm-learning-NNN decision."
        ),
        "auto_promotion": False,
        "decision_refs": ["slm-learning-051", "slm-learning-081", "slm-learning-082"],
    }


def reject(running_path: Path, reason: str) -> Path:
    """Move running/<id>.json -> rejected/<id>.json with a reason."""
    rejected_dir = QUEUE / "rejected"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    target = rejected_dir / running_path.name
    spec = json.loads(running_path.read_text(encoding="utf-8"))
    spec["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    spec["rejection_reason"] = reason
    running_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    os.rename(running_path, target)
    return target


def run_one(target: str | None, dry_run: bool) -> str:
    pending = list_pending(target)
    if not pending:
        return "empty"

    job = pending[0]
    claimer = f"runner-{os.getpid()}-{dt.datetime.now(dt.timezone.utc).strftime('%H%M%S')}"
    running = claim(job, claimer)
    if running is None:
        return "race-lost"

    spec = json.loads(running.read_text(encoding="utf-8"))
    print(f"[runner] claimed {spec.get('job_id')} (compute_target={spec.get('compute_target')})")
    log_trace({"kind": "queue_claim", "job_id": spec.get("job_id"),
               "compute_target": spec.get("compute_target"), "dry_run": dry_run})

    train_result = run_trainer(spec, dry_run=dry_run)
    print(f"[runner] train_result.status = {train_result.get('status')}")

    if train_result.get("status") == "deferred-remote":
        # Remote target — leave as evaluated with the deferral note.
        verdict = make_verdict(spec, train_result, target_name="remote")
        evaluated = write_verdict(running, verdict)
        log_trace({"kind": "queue_deferred", "job_id": spec.get("job_id"),
                   "evaluated_path": str(evaluated)})
        return "deferred-remote"

    if train_result.get("status") in {"trainer_failed", "error"}:
        rejected = reject(running, json.dumps(train_result))
        log_trace({"kind": "queue_rejected", "job_id": spec.get("job_id"),
                   "rejected_path": str(rejected),
                   "reason": train_result.get("error") or "trainer_failed"})
        return "rejected"

    verdict = make_verdict(spec, train_result, target_name="local")
    evaluated = write_verdict(running, verdict)
    log_trace({"kind": "queue_evaluated", "job_id": spec.get("job_id"),
               "evaluated_path": str(evaluated)})
    return "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=None,
                        help="Filter to compute_target (default: any)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--loop", action="store_true",
                        help="Pick next when current finishes; stop on empty")
    parser.add_argument("--idle-sleep", type=int, default=60,
                        help="With --loop, sleep N seconds between empty polls "
                             "(default 60)")
    args = parser.parse_args()

    runs = 0
    while True:
        result = run_one(args.target, args.dry_run)
        runs += 1
        print(f"[runner] iteration {runs} -> {result}")
        if not args.loop:
            break
        if result == "empty":
            print(f"[runner] queue empty, exiting loop")
            break
        # Brief pause between successive jobs to let logs settle.
        time.sleep(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
