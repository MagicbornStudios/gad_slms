#!/usr/bin/env python3
"""
Skill Pressure Correlation Analysis

Correlates skill invocations with downstream learning signals:
- eval score deltas
- decisions logged
- commits created
- handoffs completed
- state_log entries with positive tags

Reads from:
- .planning/.gad-log/*.jsonl (command log)
- .planning/.provenance/*.jsonl (tool use + outcome)
- .planning/.trace-events.jsonl (system events)

Outputs:
- reports/research/skill_pressure_correlation.json (per-skill correlation table)
- reports/research/skill_pressure_correlation.md (markdown report)

Exit codes:
- 0: Success
- 1: Script error
- 2: Missing telemetry (suggests `gad telemetry export`)
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import re


def find_telemetry_files(project_root: Path) -> dict:
    """Locate telemetry sources."""
    sources = {
        "gad_log": [],
        "provenance": [],
        "trace_events": None,
    }

    planning_dir = project_root / ".planning"
    if not planning_dir.exists():
        return sources

    # GAD log files
    gad_log_dir = planning_dir / ".gad-log"
    if gad_log_dir.exists():
        sources["gad_log"] = sorted(gad_log_dir.glob("*.jsonl"))

    # Provenance files
    prov_dir = planning_dir / ".provenance"
    if prov_dir.exists():
        sources["provenance"] = sorted(prov_dir.glob("*.jsonl"))

    # Trace events
    trace_file = planning_dir / ".trace-events.jsonl"
    if trace_file.exists():
        sources["trace_events"] = trace_file

    return sources


def parse_timestamp(ts_str):
    """Parse ISO 8601 timestamp to datetime."""
    try:
        # Handle both formats: with/without microseconds and timezone
        ts_str = ts_str.replace("+00:00", "")
        if "." in ts_str:
            return datetime.fromisoformat(ts_str.split("+")[0])
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None


def extract_skill_invocations(provenance_files: list) -> list:
    """
    Extract skill invocation events from provenance logs.

    Looks for:
    - Tool use with "trigger_skill" field
    - Any mention of skill in metadata
    """
    invocations = []

    for fpath in provenance_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    event = json.loads(line)

                    # Extract skill from tool use events
                    if event.get("tool") and event.get("ts"):
                        ts = parse_timestamp(event["ts"])
                        if not ts:
                            continue

                        skill_id = event.get("trigger_skill")
                        if skill_id:
                            invocations.append({
                                "ts": ts,
                                "skill_id": skill_id,
                                "tool": event.get("tool"),
                                "file_path": event.get("file_path"),
                                "event_id": event.get("event_id"),
                                "project": event.get("project", {}).get("id"),
                            })
        except (json.JSONDecodeError, IOError):
            pass

    return sorted(invocations, key=lambda x: x["ts"])


def extract_downstream_signals(trace_files: list, gad_log_files: list,
                                  skill_ts: datetime, window_minutes: int = 30) -> dict:
    """
    Find downstream events within window_minutes of skill invocation.

    Returns: dict with keys for eval_lift, decisions, commits, etc.
    """
    signals = {
        "eval_lift": 0,
        "decisions_logged": [],
        "commits": [],
        "handoffs_completed": [],
        "state_log_entries": [],
    }

    window_end = skill_ts + timedelta(minutes=window_minutes)

    # Check GAD logs for commits and decisions
    for fpath in gad_log_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    event_ts = parse_timestamp(event.get("ts"))

                    if not event_ts or event_ts < skill_ts or event_ts > window_end:
                        continue

                    cmd = event.get("cmd", "")
                    if "commit" in cmd.lower():
                        signals["commits"].append(event.get("cmd"))
                    elif "decision" in cmd.lower():
                        signals["decisions_logged"].append(event.get("cmd"))
        except (json.JSONDecodeError, IOError):
            pass

    # Check trace events for system-level signals
    for fpath in trace_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    event_ts = parse_timestamp(event.get("ts"))

                    if not event_ts or event_ts < skill_ts or event_ts > window_end:
                        continue

                    event_type = event.get("type", "").lower()
                    kind = event.get("kind", "").lower()

                    if "commit" in event_type or "commit" in kind:
                        signals["commits"].append(str(event)[:100])
                    elif "decision" in event_type or "decision" in kind:
                        signals["decisions_logged"].append(str(event)[:100])
                    elif "eval" in kind and "completed" in kind:
                        # Try to extract score delta
                        if "score" in str(event).lower():
                            signals["eval_lift"] += 1
        except (json.JSONDecodeError, IOError):
            pass

    return signals


def compute_skill_correlation(invocations: list, project_root: Path,
                              telemetry_files: dict) -> dict:
    """
    Compute per-skill correlation metrics.

    Returns: dict mapping skill_id -> {invocations, signals, net_score}
    """
    skill_stats = defaultdict(lambda: {
        "invocations": 0,
        "downstream_eval_lift": 0,
        "decisions_logged": 0,
        "commits": 0,
        "handoffs_completed": 0,
        "state_log_entries": 0,
        "net_signal_score": 0.0,
    })

    trace_files = [telemetry_files["trace_events"]] if telemetry_files["trace_events"] else []
    gad_log_files = telemetry_files.get("gad_log", [])

    for inv in invocations:
        skill_id = inv["skill_id"]
        skill_stats[skill_id]["invocations"] += 1

        # Extract downstream signals
        signals = extract_downstream_signals(
            trace_files, gad_log_files, inv["ts"], window_minutes=30
        )

        # Accumulate signals
        skill_stats[skill_id]["downstream_eval_lift"] += signals["eval_lift"]
        skill_stats[skill_id]["decisions_logged"] += len(signals["decisions_logged"])
        skill_stats[skill_id]["commits"] += len(signals["commits"])
        skill_stats[skill_id]["handoffs_completed"] += len(signals["handoffs_completed"])
        skill_stats[skill_id]["state_log_entries"] += len(signals["state_log_entries"])

    # Compute net signal score (weighted sum)
    for skill_id, stats in skill_stats.items():
        invocations = stats["invocations"]
        if invocations == 0:
            continue

        # Weights: eval_lift (0.4), decisions (0.3), commits (0.2), handoffs (0.1)
        signal_value = (
            stats["downstream_eval_lift"] * 0.4 +
            stats["decisions_logged"] * 0.3 +
            stats["commits"] * 0.2 +
            stats["handoffs_completed"] * 0.1
        )

        # Normalize by invocations to get per-invocation signal
        stats["net_signal_score"] = signal_value / invocations

    return dict(skill_stats)


def flag_eviction_candidates(skill_stats: dict, threshold: float = 0.1) -> list:
    """
    Identify skills with signal < threshold for potential shedding.

    Per slm-learning-128: "if we learn nothing new that is useful, then
    those skills are meaningless"
    """
    candidates = []
    for skill_id, stats in skill_stats.items():
        if stats["invocations"] > 0 and stats["net_signal_score"] < threshold:
            candidates.append({
                "skill_id": skill_id,
                "invocations": stats["invocations"],
                "net_signal_score": stats["net_signal_score"],
                "reason": "Below correlation threshold",
            })

    return sorted(candidates, key=lambda x: x["net_signal_score"])


def write_json_report(output_path: Path, skill_stats: dict,
                     eviction_candidates: list) -> None:
    """Write JSON correlation table."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Sort by net_signal_score descending
    sorted_skills = sorted(
        skill_stats.items(),
        key=lambda x: x[1]["net_signal_score"],
        reverse=True
    )

    report = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "decision_ref": "slm-learning-128",
            "methodology": "Skill invocations correlated with 30-min downstream signals (eval, decision, commit, handoff)",
            "signal_weights": {
                "eval_lift": 0.4,
                "decisions_logged": 0.3,
                "commits": 0.2,
                "handoffs_completed": 0.1,
            },
        },
        "skills": [
            {
                "skill_id": skill_id,
                **stats
            }
            for skill_id, stats in sorted_skills
        ],
        "eviction_candidates": eviction_candidates,
        "summary": {
            "total_skills_monitored": len(skill_stats),
            "total_invocations": sum(s["invocations"] for s in skill_stats.values()),
            "eviction_candidates_count": len(eviction_candidates),
        }
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"[OK] JSON report: {output_path}")


def write_markdown_report(output_path: Path, skill_stats: dict,
                         eviction_candidates: list) -> None:
    """Write markdown correlation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sorted_skills = sorted(
        skill_stats.items(),
        key=lambda x: x[1]["net_signal_score"],
        reverse=True
    )

    md = f"""# Skill Pressure Correlation Report

**Generated**: {datetime.utcnow().isoformat()}
**Decision Ref**: slm-learning-128
**Principle**: "If we learn nothing new that is useful, then those skills are meaningless."

## Summary

- **Total skills monitored**: {len(skill_stats)}
- **Total invocations**: {sum(s["invocations"] for s in skill_stats.values())}
- **Eviction candidates** (signal < 0.1): {len(eviction_candidates)}

## Methodology

Each skill invocation is correlated with downstream events in a 30-minute window:
- **eval_lift** (0.4 weight): Eval completion events with score deltas
- **decisions_logged** (0.3 weight): Decision added events
- **commits** (0.2 weight): Git commits created
- **handoffs_completed** (0.1 weight): Handoff completion events

Net signal score = (eval_lift × 0.4 + decisions × 0.3 + commits × 0.2 + handoffs × 0.1) / invocations

## High-Signal Skills

Top performers by net signal score:

| Skill ID | Invocations | Eval Lift | Decisions | Commits | Net Score |
|----------|-------------|-----------|-----------|---------|-----------|
"""

    for skill_id, stats in sorted_skills[:20]:
        if stats["invocations"] > 0:
            md += f"| `{skill_id}` | {stats['invocations']} | {stats['downstream_eval_lift']} | {stats['decisions_logged']} | {stats['commits']} | {stats['net_signal_score']:.3f} |\n"

    md += f"""

## Eviction Candidates (Low-Signal Skills)

These skills were invoked but produced minimal downstream learning signals.
Consider shedding per `gad evolution shed` (ref: slm-learning-103).

"""

    if eviction_candidates:
        for cand in eviction_candidates[:30]:
            md += f"- `{cand['skill_id']}` ({cand['invocations']} invocations, score {cand['net_signal_score']:.3f})\n"
    else:
        md += "None identified.\n"

    md += f"""

## Next Steps

1. **Investigate zero-signal skills**: Why were they invoked if they produce no signals?
   - May be infrastructure/setup (valid but invisible in event stream)
   - May be truly unused (candidate for removal)

2. **Skill catalog audit**: Cross-reference against `~/.claude/skills/` and external catalogs
   - skills.sh
   - agentskills
   - openclaw skills

3. **Integration work** (cross-project handoff, slm-learning → gad CLI):
   - Extend telemetry export to emit `skill_invoke` events with explicit envelope
   - Add skill event fields: skill_id, skill_module, adapter_context
   - Populate outcome signal in skill completion event

4. **External skill evaluation**: Apply same correlation lens to external skill catalogs before installation
   - Require MCP-equivalent telemetry from new skills
   - Phase-gate on demonstrated learning signal in controlled eval

## Notes

- Phase-1 analysis uses local provenance + GAD logs only (no remote event aggregation yet)
- 30-minute correlation window is conservative; may need tuning based on skill execution profile
- Missing skill telemetry envelope means many skills fly blind; integration work unblocks visibility

---

**Decision**: slm-learning-128 (Skills must generate measurable learning signal)
**Scope**: Experimental; phase-1 local correlation only
**Refs**: slm-learning-103 (evolution shed), slm-learning-101 (research tracks)
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"[OK] Markdown report: {output_path}")


def main() -> int:
    project_root = Path(__file__).parent.parent.parent

    # Find telemetry sources
    telemetry_files = find_telemetry_files(project_root)

    # Check if telemetry exists
    has_telemetry = bool(
        telemetry_files["gad_log"] or
        telemetry_files["provenance"] or
        telemetry_files["trace_events"]
    )

    if not has_telemetry:
        print(
            "[MISSING] No telemetry files found.\n"
            "\nTo generate telemetry export:\n"
            "  gad telemetry export --projectid slm-learning --output data/raw/telemetry\n"
            "\nThen re-run this script.",
            file=sys.stderr
        )
        return 2

    # Extract skill invocations
    invocations = extract_skill_invocations(telemetry_files["provenance"])

    if not invocations:
        print(
            "[INFO] No skill invocations found in telemetry.\n"
            "This is expected if skills have not been invoked with explicit trigger_skill metadata.\n"
            "See decision slm-learning-128 for integration roadmap.",
            file=sys.stderr
        )
        # Still generate empty reports for infrastructure
        invocations = []

    # Compute correlation
    skill_stats = compute_skill_correlation(invocations, project_root, telemetry_files)
    eviction_candidates = flag_eviction_candidates(skill_stats, threshold=0.1)

    # Write reports
    json_out = project_root / "reports" / "research" / "skill_pressure_correlation.json"
    md_out = project_root / "reports" / "research" / "skill_pressure_correlation.md"

    write_json_report(json_out, skill_stats, eviction_candidates)
    write_markdown_report(md_out, skill_stats, eviction_candidates)

    print(f"\n[SUMMARY]")
    print(f"  Skills monitored: {len(skill_stats)}")
    print(f"  Total invocations: {sum(s['invocations'] for s in skill_stats.values())}")
    print(f"  Eviction candidates: {len(eviction_candidates)}")
    print(f"  Highest-signal skill: {max((s for s in skill_stats.values()), key=lambda x: x['net_signal_score'] or 0, default={}).get('net_signal_score', 0):.3f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
