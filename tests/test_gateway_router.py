"""Tests for the GAD Gateway router + trace_logger + cli.

Decision refs: slm-learning-208.

Runs under pytest if available; otherwise the ``__main__`` block at the
bottom executes the same assertions. Uses an isolated traces root via
the ``GAD_GATEWAY_TRACES_ROOT`` env var so the real
``data/inference-traces/`` is never touched. Mocks the trace_logger
clock for the rotation-on-date-change test (freezegun not required).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure repo root is importable.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Fixtures (manual; pytest fixtures would just duplicate this).
# ---------------------------------------------------------------------------

def _setup_isolated_traces() -> Path:
    """Point trace_logger at a tempdir; reset cached routes; return the tempdir."""
    tmp = Path(tempfile.mkdtemp(prefix="gateway_test_"))
    os.environ["GAD_GATEWAY_TRACES_ROOT"] = str(tmp)
    # Reset router caches between tests so a stale routes.json doesn't leak.
    from scripts.gateway import router as _router
    _router._ROUTES_CACHE = None  # type: ignore[attr-defined]
    return tmp


def _reset_clock() -> None:
    from scripts.gateway import trace_logger
    trace_logger.reset_clock()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_route_gad_note_resolves_to_qwen_1p5b():
    _setup_isolated_traces()
    _reset_clock()
    from scripts.gateway.router import route

    result = route("gad_note", "test prompt")
    assert result.model_id == "qwen2.5-coder-1.5b-instruct", result.model_id
    assert result.tier == 0, result.tier
    assert result.route_id == "gad_note", result.route_id
    assert result.accepted_by == "unverified"
    assert result.output.startswith("[ROUTED:")
    assert result.trace_row_id  # non-empty
    assert result.attempts and result.attempts[0]["success"] is True


def test_unknown_task_shape_falls_back_to_default_general():
    _setup_isolated_traces()
    _reset_clock()
    from scripts.gateway.router import route

    result = route("totally_made_up_shape_xyz", "x")
    assert result.route_id == "default_general", result.route_id
    assert result.task_shape == "totally_made_up_shape_xyz"  # original task is preserved
    assert result.model_id == "qwen2.5-coder-32b-instruct", result.model_id
    assert result.tier == 2, result.tier


def test_trace_row_written_and_validates():
    tmp = _setup_isolated_traces()
    _reset_clock()
    from scripts.gateway.router import route
    from scripts.gateway.trace_logger import current_path, REQUIRED_FIELDS

    route("gad_decision", "Should we close Variant C?")
    path = current_path()
    assert path.exists(), f"trace file not created at {path}"
    lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines, "no trace rows written"
    row = lines[-1]
    for field in REQUIRED_FIELDS:
        assert field in row and row[field], f"required field missing or empty: {field}"
    # Spot-check schema-relevant fields.
    assert row["task_shape"] == "gad_decision"
    assert row["used_model"] == "qwen2.5-coder-1.5b-instruct"
    assert row["success"] is True
    assert row["fallback_used"] is False

    # If jsonschema is available, validate against the registered schema.
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return
    schema_path = _REPO_ROOT / "schemas" / "inference_trace.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(row, schema)


def test_dry_run_does_not_write_trace_row():
    tmp = _setup_isolated_traces()
    _reset_clock()
    from scripts.gateway.router import route
    from scripts.gateway.trace_logger import current_path

    result = route("gad_note", "dry run prompt", dry_run=True)
    assert result.dry_run is True
    assert result.output == ""
    # No traces directory should have been created — write_trace was never called.
    assert not current_path().exists(), \
        f"dry_run should not write a trace, found {current_path()}"


def test_cli_json_round_trip():
    """Spawn the CLI as a subprocess and parse its --json output."""
    tmp = _setup_isolated_traces()
    _reset_clock()

    env = os.environ.copy()
    env["GAD_GATEWAY_TRACES_ROOT"] = str(tmp)
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.run(
        [sys.executable, "-m", "scripts.gateway.cli",
         "--task-shape", "gad_note",
         "--prompt", "hello from cli test",
         "--json"],
        capture_output=True, text=True, env=env, cwd=str(_REPO_ROOT),
    )
    assert proc.returncode == 0, f"cli failed: stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout)
    assert payload["task_shape"] == "gad_note"
    assert payload["model_id"] == "qwen2.5-coder-1.5b-instruct"
    assert payload["tier"] == 0
    assert payload["accepted_by"] == "unverified"
    assert payload["output"].startswith("[ROUTED:")


def test_trace_rotation_on_date_change():
    """Mock the clock; rows on different dates land in different files."""
    tmp = _setup_isolated_traces()
    from scripts.gateway import trace_logger

    day1 = _dt.datetime(2026, 5, 8, 23, 59, 0, tzinfo=_dt.timezone.utc)
    day2 = _dt.datetime(2026, 5, 9, 0, 0, 30, tzinfo=_dt.timezone.utc)

    trace_logger.set_clock(lambda: day1)
    p1 = trace_logger.current_path()
    trace_logger.write_trace({"task_shape": "rot_test", "used_model": "m"})

    trace_logger.set_clock(lambda: day2)
    p2 = trace_logger.current_path()
    trace_logger.write_trace({"task_shape": "rot_test", "used_model": "m"})

    trace_logger.reset_clock()

    assert p1 != p2, f"expected different paths across midnight: {p1} vs {p2}"
    assert p1.exists() and p2.exists(), "both daily files should exist"
    assert "2026-05-08" in p1.name
    assert "2026-05-09" in p2.name


# ---------------------------------------------------------------------------
# Bare-Python runner (when pytest isn't installed).
# ---------------------------------------------------------------------------

def _run_all():
    tests = [
        test_route_gad_note_resolves_to_qwen_1p5b,
        test_unknown_task_shape_falls_back_to_default_general,
        test_trace_row_written_and_validates,
        test_dry_run_does_not_write_trace_row,
        test_cli_json_round_trip,
        test_trace_rotation_on_date_change,
    ]
    failed = []
    for t in tests:
        name = t.__name__
        try:
            t()
            print(f"PASS  {name}")
        except AssertionError as exc:
            failed.append((name, f"AssertionError: {exc}"))
            print(f"FAIL  {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"ERROR {name}: {type(exc).__name__}: {exc}")
    print()
    print(f"{len(tests) - len(failed)}/{len(tests)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
