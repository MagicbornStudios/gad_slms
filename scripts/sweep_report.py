"""
Aggregate every experiment in experiments/runs/ into a single human-readable
markdown report. Intended as the "morning recap" after an overnight sweep.

  .venv-gpu/Scripts/python.exe scripts/sweep_report.py

Writes experiments/REPORT.md and prints a SITREP table to stdout.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "experiments" / "runs"
REPORT = ROOT / "experiments" / "REPORT.md"


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def format_pct(passed: int | None, total: int | None) -> str:
    if passed is None or total is None or total == 0:
        return "—"
    return f"{passed}/{total} ({100.0 * passed / total:.1f}%)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-eval", type=Path,
                        default=ROOT / "runs" / "eval" / "gad_tools_baseline_dr_stein.json",
                        help="Reference baseline eval JSON for context")
    args = parser.parse_args()

    if not RUNS_DIR.exists():
        print(f"No runs directory at {RUNS_DIR}")
        return 1

    rows = []
    for run_dir in sorted(RUNS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        manifest = load_json(run_dir / "MANIFEST.json")
        eval_doc = load_json(run_dir / "eval_gad_tools.json")
        if not manifest:
            continue
        cfg = manifest.get("config", {})
        metrics = manifest.get("metrics", {})
        rows.append({
            "name": run_dir.name,
            "started_at": manifest.get("started_at", "?"),
            "stage": cfg.get("stage", "reasoning"),
            "epochs": cfg.get("epochs", "?"),
            "lr": cfg.get("lr", "?"),
            "max_pairs": cfg.get("max_pairs", "?"),
            "block_size": cfg.get("block_size", "?"),
            "final_loss": metrics.get("final_loss"),
            "elapsed_sec": metrics.get("elapsed_sec"),
            "exit_code": manifest.get("exit_code"),
            "eval_passed": eval_doc.get("passed") if eval_doc else None,
            "eval_total": eval_doc.get("total") if eval_doc else None,
            "notes": manifest.get("notes") or cfg.get("notes", ""),
        })

    baseline = load_json(args.baseline_eval)

    lines = []
    lines.append(f"# Overnight Sweep Report — {time.strftime('%Y-%m-%d %H:%M')}\n")
    if baseline:
        ref = format_pct(baseline.get("passed"), baseline.get("total"))
        lines.append(f"**Reference baseline (pre-sweep dr_stein.pt):** {ref} on {baseline.get('eval', 'gad_tools')}")
        lines.append("")
    lines.append(f"## Sweep results — {len(rows)} run(s)\n")
    lines.append("| run | started | epochs | lr | pairs | block | final_loss | wall_s | exit | gad_tools | notes |")
    lines.append("|-----|---------|--------|----|-------|-------|-----------|--------|------|-----------|-------|")
    for r in rows:
        lines.append(
            f"| {r['name']} | {r['started_at']} | {r['epochs']} | {r['lr']} | {r['max_pairs']} "
            f"| {r['block_size']} | {r['final_loss']} | {r['elapsed_sec']} | {r['exit_code']} "
            f"| {format_pct(r['eval_passed'], r['eval_total'])} | {r['notes']} |"
        )

    lines.append("")
    lines.append("## Reading this table\n")
    lines.append("- `final_loss` is the avg cross-entropy at the last epoch (lower = better fit).")
    lines.append("- `gad_tools` is `passed/total` on the 30-case GAD-tool-call eval.")
    lines.append("- `wall_s` is training wall time (eval is separate, ~3-4 min CPU per checkpoint).")
    lines.append("")

    # Pick a "best" by eval pass count, ties broken by lower loss
    completed = [r for r in rows if r["eval_passed"] is not None and r["final_loss"] is not None]
    if completed:
        best = max(completed, key=lambda r: (r["eval_passed"], -float(r["final_loss"] or 999)))
        lines.append("## Best run\n")
        lines.append(
            f"- **{best['name']}** — gad_tools={format_pct(best['eval_passed'], best['eval_total'])}, "
            f"final_loss={best['final_loss']}, wall={best['elapsed_sec']}s"
        )
        lines.append(f"- Notes: {best['notes']}")
        lines.append("")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
