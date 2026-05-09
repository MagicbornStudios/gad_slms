"""Daily aggregator for GAD Gateway trace JSONL files.

Reads ``data/inference-traces/*.jsonl`` rows in a window, rolls them up
by task_shape / tier / model, and emits a JSON aggregate document for
the AI-spend-ledger close. Decision refs: slm-learning-208.

Usage:

    python -m scripts.gateway.aggregate_traces \\
        --window 7d \\
        --out reports/costs/2026-05-08-trace-aggregate.json

    python -m scripts.gateway.aggregate_traces \\
        --window 30d \\
        --out reports/costs/2026-05-monthly-trace-aggregate.json \\
        --update-ledger reports/costs/ai_spend_ledger.md
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACES_DIR = ROOT / "data" / "inference-traces"

REPLACEMENT_THRESHOLD_DEFAULT = 20  # >= N successful local calls -> replacement-eligible


def _parse_window(spec: str) -> _dt.timedelta:
    """Parse '7d', '24h', '30d' style window strings."""
    m = re.fullmatch(r"(\d+)\s*([dhm])", spec.strip().lower())
    if not m:
        raise ValueError(f"--window must look like '7d', '24h', '30m'; got {spec!r}")
    n, unit = int(m.group(1)), m.group(2)
    if unit == "d":
        return _dt.timedelta(days=n)
    if unit == "h":
        return _dt.timedelta(hours=n)
    return _dt.timedelta(minutes=n)


def _iter_rows(traces_dir: Path, since: _dt.datetime) -> Iterable[dict]:
    if not traces_dir.exists():
        return
    for path in sorted(traces_dir.glob("*.jsonl")):
        # Quick file-name date filter so we don't open files older than the window.
        try:
            file_date = _dt.datetime.strptime(path.stem, "%Y-%m-%d").replace(tzinfo=_dt.timezone.utc)
        except ValueError:
            file_date = None
        if file_date is not None and file_date < since - _dt.timedelta(days=1):
            continue
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = row.get("timestamp")
                if ts:
                    try:
                        row_time = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        row_time = None
                    if row_time is not None and row_time < since:
                        continue
                yield row


def _is_local_model(model_id: str) -> bool:
    if not model_id:
        return False
    if model_id.startswith("claude-") or model_id.startswith("gpt-") or model_id.startswith("gemini"):
        return False
    return True


def aggregate(rows: Iterable[dict], replacement_threshold: int) -> dict:
    total_calls = 0
    total_cost = 0.0
    fallback_calls = 0
    successful_calls = 0
    by_task: dict[str, dict] = defaultdict(lambda: {"count": 0, "cost_usd": 0.0,
                                                     "successful_local_calls": 0})
    by_tier: dict[str, dict] = defaultdict(lambda: {"count": 0, "cost_usd": 0.0})
    by_model: dict[str, dict] = defaultdict(lambda: {"count": 0, "cost_usd": 0.0,
                                                      "latency_sum": 0.0, "latency_n": 0})

    for row in rows:
        total_calls += 1
        cost = float(row.get("cost") or 0.0)
        total_cost += cost
        if row.get("fallback_used"):
            fallback_calls += 1
        success = bool(row.get("success"))
        if success:
            successful_calls += 1

        task = row.get("task_shape") or "unknown"
        tier_key = str(row.get("tier", "?"))
        model = row.get("used_model") or "unknown"
        latency = float(row.get("latency_seconds") or 0.0)

        by_task[task]["count"] += 1
        by_task[task]["cost_usd"] += cost
        if success and _is_local_model(model):
            by_task[task]["successful_local_calls"] += 1

        by_tier[tier_key]["count"] += 1
        by_tier[tier_key]["cost_usd"] += cost

        by_model[model]["count"] += 1
        by_model[model]["cost_usd"] += cost
        by_model[model]["latency_sum"] += latency
        by_model[model]["latency_n"] += 1

    # Finalize avg latency.
    by_model_out: dict[str, dict] = {}
    for m, d in by_model.items():
        avg = (d["latency_sum"] / d["latency_n"]) if d["latency_n"] else 0.0
        by_model_out[m] = {
            "count": d["count"],
            "cost_usd": round(d["cost_usd"], 6),
            "avg_latency_seconds": round(avg, 4),
        }

    fallback_rate = (fallback_calls / total_calls) if total_calls else 0.0

    replacement_eligible = sorted(
        t for t, d in by_task.items()
        if d["successful_local_calls"] >= replacement_threshold
    )

    return {
        "total_calls": total_calls,
        "successful_calls": successful_calls,
        "total_cost_usd": round(total_cost, 6),
        "fallback_calls": fallback_calls,
        "fallback_rate": round(fallback_rate, 4),
        "by_task_shape": {
            t: {"count": d["count"],
                "cost_usd": round(d["cost_usd"], 6),
                "successful_local_calls": d["successful_local_calls"]}
            for t, d in sorted(by_task.items())
        },
        "by_tier": {k: {"count": d["count"], "cost_usd": round(d["cost_usd"], 6)}
                    for k, d in sorted(by_tier.items())},
        "by_model": {k: by_model_out[k] for k in sorted(by_model_out)},
        "replacement_eligible_task_shapes": replacement_eligible,
        "replacement_threshold": replacement_threshold,
    }


def _append_ledger(ledger_path: Path, summary: dict, window_spec: str, since: _dt.datetime,
                   until: _dt.datetime) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if not ledger_path.exists():
        ledger_path.write_text(
            "# AI Spend Ledger\n\n"
            "Append-only close rows from `scripts/gateway/aggregate_traces.py`.\n"
            "Decision refs: slm-learning-208.\n\n",
            encoding="utf-8",
        )
    line = (
        f"- **{until.strftime('%Y-%m-%d')}** window={window_spec} "
        f"calls={summary['total_calls']} "
        f"cost=${summary['total_cost_usd']} "
        f"fallback_rate={summary['fallback_rate']} "
        f"replacement_eligible={summary['replacement_eligible_task_shapes']}\n"
    )
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.gateway.aggregate_traces",
        description="Roll up gateway JSONL traces into a cost-ledger aggregate.",
    )
    p.add_argument("--window", default="7d", help="Lookback window: '7d', '24h', '30d'.")
    p.add_argument("--out", required=True, help="Output JSON path for the aggregate document.")
    p.add_argument("--update-ledger", default=None,
                   help="Optional: append a close row to this Markdown ledger.")
    p.add_argument("--replacement-threshold", type=int,
                   default=REPLACEMENT_THRESHOLD_DEFAULT,
                   help="Min successful local calls to mark task_shape replacement-eligible.")
    p.add_argument("--traces-dir", default=str(DEFAULT_TRACES_DIR),
                   help="Where to read JSONL trace files from.")
    args = p.parse_args(argv)

    delta = _parse_window(args.window)
    until = _dt.datetime.now(_dt.timezone.utc)
    since = until - delta

    rows = _iter_rows(Path(args.traces_dir), since)
    summary = aggregate(rows, args.replacement_threshold)
    summary["window"] = args.window
    summary["since"] = since.isoformat()
    summary["until"] = until.isoformat()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[aggregate] wrote {out_path}  calls={summary['total_calls']}  "
          f"cost=${summary['total_cost_usd']}")

    if args.update_ledger:
        _append_ledger(Path(args.update_ledger), summary, args.window, since, until)
        print(f"[aggregate] appended close row to {args.update_ledger}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
