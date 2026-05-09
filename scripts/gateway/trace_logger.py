"""JSONL trace writer for the GAD Gateway.

Per slm-learning-208. One JSONL row per model call attempt (not per
``router.route()`` call — fallbacks emit additional rows).

Storage: ``data/inference-traces/<YYYY-MM-DD>.jsonl``. Directory is
created on first write. Rotation is implicit: ``current_path()`` is
re-derived from current UTC date every call, so a new file appears
naturally at midnight UTC. ``rotate_if_needed()`` is exposed for
explicit pre-write rotation hooks (currently a no-op since rotation
is path-derived; reserved for future compression/ship-to-Modal logic
per the 7-day retention policy in slm-learning-105).

Required fields on every row (per
``schemas/inference_trace.schema.json``): ``timestamp``, ``task_shape``,
``used_model``. Auto-filled if missing: ``trace_id`` (uuid),
``timestamp`` (UTC ISO), ``gateway_version``.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import uuid
from pathlib import Path
from typing import Callable

from . import __version__ as GATEWAY_VERSION

# Allow tests/aggregator to override repo root via env without import-time effects.
_DEFAULT_ROOT = Path(__file__).resolve().parents[2]
TRACES_DIRNAME = "inference-traces"

REQUIRED_FIELDS = ("timestamp", "task_shape", "used_model")

# Injectable clock for test determinism.
_clock: Callable[[], _dt.datetime] = lambda: _dt.datetime.now(_dt.timezone.utc)


def set_clock(fn: Callable[[], _dt.datetime]) -> None:
    """Override the UTC clock (for tests). Pass ``None``-equivalent default to reset."""
    global _clock
    _clock = fn


def reset_clock() -> None:
    global _clock
    _clock = lambda: _dt.datetime.now(_dt.timezone.utc)


def _root() -> Path:
    override = os.environ.get("GAD_GATEWAY_TRACES_ROOT")
    if override:
        return Path(override)
    return _DEFAULT_ROOT / "data"


def current_path() -> Path:
    """Return today's JSONL path (UTC). Recomputed every call so rotation is implicit."""
    today = _clock().strftime("%Y-%m-%d")
    return _root() / TRACES_DIRNAME / f"{today}.jsonl"


def rotate_if_needed() -> None:
    """Rotation is path-derived; this is a no-op hook for future logic
    (e.g. gzip yesterday's file, ship to Modal volume after 7 days).
    """
    return None


def _validate(row: dict) -> None:
    missing = [k for k in REQUIRED_FIELDS if k not in row or row[k] in (None, "")]
    if missing:
        raise ValueError(f"trace row missing required fields: {missing}")


def write_trace(row: dict) -> str:
    """Write one trace row as a JSONL line. Returns the row's ``trace_id``.

    Mutates the input dict to fill in ``trace_id``, ``timestamp``,
    ``gateway_version`` if absent.
    """
    if "trace_id" not in row or not row["trace_id"]:
        row["trace_id"] = str(uuid.uuid4())
    if "timestamp" not in row or not row["timestamp"]:
        row["timestamp"] = _clock().isoformat()
    row.setdefault("gateway_version", GATEWAY_VERSION)

    _validate(row)

    path = current_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row["trace_id"]
