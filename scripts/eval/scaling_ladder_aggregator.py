"""Aggregate scaling-ladder eval JSONs into a combined cost-per-success report.

Reads per-rung eval JSONs (schema_v=2 summaries written by
modal_app/eval_adapter.py::main when --persist-run-id is set) for the
1.5B / 3B / 7B / 14B / 32B / 80B-A3B rungs and computes per-rung
HE / MBPP / gad_tools pass rates, cost-per-successful-task,
delta-vs-7B-Stein, and a knee pick (smallest rung beating 7B Stein
by >=2pp on HE AND MBPP). Read-only — does not fire Modal jobs.

Run:
    .venv/Scripts/python.exe scripts/eval/scaling_ladder_aggregator.py \\
        --rungs 1.5b,3b,7b,14b,32b,80b-a3b \\
        --out reports/research/scaling_ladder_aggregate_2026-05-09.md

Decision refs: slm-learning-097, 100, 103, 105, 202, 207, 210.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_RUN_DIRS = [
    REPO_ROOT / "data" / "eval-runs",
    REPO_ROOT / "experiments" / "eval-runs",
    REPO_ROOT / "tmp" / "eval-runs",
    Path("/models/eval-runs"),
]


# 7B Stein canonical anchor per slm-learning-168 / teacher_species_policy.md
ANCHOR_7B_STEIN = {"humaneval": 0.848, "mbpp": 0.823}

# Knee thresholds — slm-learning-210
KNEE_HE_DELTA_PP = 2.0
KNEE_MBPP_DELTA_PP = 2.0


# Per-rung metadata for cost lookup. estimated_cost_usd matches the
# spec JSONs at experiments/configs/scaling_ladder/.
RUNG_META = {
    "1.5b": {
        "label": "1.5B Stein",
        "base_model": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
        "estimated_cost_usd_per_run": 0.30,
        "gpu": "A10G",
    },
    "3b": {
        "label": "3B base",
        "base_model": "Qwen/Qwen2.5-Coder-3B-Instruct",
        "estimated_cost_usd_per_run": 0.50,
        "gpu": "A10G",
    },
    "7b": {
        "label": "7B Stein canonical",
        "base_model": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "estimated_cost_usd_per_run": 1.00,
        "gpu": "A100",
    },
    "14b": {
        "label": "14B base",
        "base_model": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "estimated_cost_usd_per_run": 2.00,
        "gpu": "A100",
    },
    "32b": {
        "label": "32B base",
        "base_model": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "estimated_cost_usd_per_run": 4.00,
        "gpu": "A100",
    },
    "80b-a3b": {
        "label": "80B-A3B base",
        "base_model": "Qwen/Qwen3-Next-80B-A3B-Instruct",
        "estimated_cost_usd_per_run": 8.00,
        "gpu": "H100",
    },
}


BENCHMARKS = ("humaneval", "mbpp", "gad_tools")


def _candidate_dirs(extra: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for d in extra + DEFAULT_EVAL_RUN_DIRS:
        if d in seen:
            continue
        seen.add(d)
        out.append(d)
    return out


def _find_eval_json(rung: str, benchmark: str, search_dirs: list[Path]) -> Optional[Path]:
    """Look for a persisted eval JSON for the rung + benchmark.

    Match either:
    - eval-base-*<rung-token>*-*/<benchmark>_chat_base_n*.json
    - any json under eval-base-* that contains base_model match.

    Returns the most recent matching file by mtime, or None.
    """
    candidates: list[Path] = []
    rung_token = rung.replace(".", "p")  # 1.5b -> 1p5b
    rung_alt_tokens = {rung, rung_token, rung.replace("-", "_")}

    for base in search_dirs:
        if not base.exists():
            continue
        for run_dir in base.iterdir():
            if not run_dir.is_dir():
                continue
            name = run_dir.name.lower()
            if not any(tok in name for tok in rung_alt_tokens):
                continue
            for f in run_dir.glob(f"{benchmark}_*_n*.json"):
                candidates.append(f)

    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _load_summary(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[warn] could not parse {path}: {exc}", file=sys.stderr)
        return None


def _compute_rung_row(
    rung: str, search_dirs: list[Path]
) -> dict:
    meta = RUNG_META.get(rung)
    if meta is None:
        return {"rung": rung, "status": "unknown_rung"}

    row: dict = {
        "rung": rung,
        "label": meta["label"],
        "base_model": meta["base_model"],
        "gpu": meta["gpu"],
        "estimated_cost_usd_per_run": meta["estimated_cost_usd_per_run"],
        "scores": {},
        "n": {},
        "passed": {},
        "source_paths": {},
        "deltas_vs_7b_stein_pp": {},
        "cost_per_successful_task_usd": {},
    }
    total_cost = 0.0
    found_any = False
    for bench in BENCHMARKS:
        path = _find_eval_json(rung, bench, search_dirs)
        if path is None:
            row["scores"][bench] = None
            row["n"][bench] = None
            row["passed"][bench] = None
            row["source_paths"][bench] = None
            continue
        summary = _load_summary(path)
        if summary is None:
            continue
        found_any = True
        score = float(summary.get("score") or 0.0)
        n = int(summary.get("n") or 0)
        passed = int(summary.get("passed") or 0)
        row["scores"][bench] = score
        row["n"][bench] = n
        row["passed"][bench] = passed
        row["source_paths"][bench] = str(path)

        anchor = ANCHOR_7B_STEIN.get(bench)
        if anchor is not None:
            row["deltas_vs_7b_stein_pp"][bench] = round((score - anchor) * 100.0, 2)

        # Cost-per-successful-task: assume the rung cost is split
        # roughly evenly across the 3 benchmarks. Conservative.
        per_bench_cost = meta["estimated_cost_usd_per_run"] / max(1, len(BENCHMARKS))
        total_cost += per_bench_cost
        if passed > 0:
            row["cost_per_successful_task_usd"][bench] = round(per_bench_cost / passed, 4)
        else:
            row["cost_per_successful_task_usd"][bench] = None

    row["status"] = "found" if found_any else "missing"
    row["estimated_total_cost_usd"] = round(total_cost, 2)
    return row


def _knee_pick(rows: list[dict]) -> Optional[str]:
    """Smallest rung beating 7B Stein by >=2pp on HE AND MBPP."""
    order = ["1.5b", "3b", "7b", "14b", "32b", "80b-a3b"]
    by_rung = {r["rung"]: r for r in rows}
    for rung in order:
        if rung not in by_rung:
            continue
        r = by_rung[rung]
        if r["status"] != "found":
            continue
        he = r["scores"].get("humaneval")
        mb = r["scores"].get("mbpp")
        if he is None or mb is None:
            continue
        he_pp = (he - ANCHOR_7B_STEIN["humaneval"]) * 100.0
        mb_pp = (mb - ANCHOR_7B_STEIN["mbpp"]) * 100.0
        if he_pp >= KNEE_HE_DELTA_PP and mb_pp >= KNEE_MBPP_DELTA_PP:
            return rung
    return None


def _format_score_cell(score: Optional[float], n: Optional[int], passed: Optional[int]) -> str:
    if score is None or n is None:
        return "—"
    return f"{passed}/{n} ({score:.1%})"


def _format_delta_cell(delta_pp: Optional[float]) -> str:
    if delta_pp is None:
        return "—"
    sign = "+" if delta_pp >= 0 else ""
    return f"{sign}{delta_pp:.2f}pp"


def render_markdown(rows: list[dict], knee: Optional[str], today: str) -> str:
    lines = [
        f"# Scaling-ladder aggregate — {today}",
        "",
        "Aggregated per-rung HumanEval / MBPP / gad_tools scores with "
        "cost-per-successful-task and delta-vs-7B-Stein. Per "
        "`slm-learning-103`, this report is the public-leaderboard "
        "subset of the comparator matrix; pair with the frontier-"
        "comparator + owned-domain + lineage rows before promoting any rung.",
        "",
        "## Per-rung scores (n=164 each, chat mode)",
        "",
        "| Rung | Base model | HE | MBPP | gad_tools | HE Δ vs 7B | MBPP Δ vs 7B |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r["status"] != "found":
            lines.append(
                f"| {r.get('label', r['rung'])} | "
                f"`{r.get('base_model', '?')}` | — | — | — | — | — |"
            )
            continue
        he = _format_score_cell(
            r["scores"].get("humaneval"), r["n"].get("humaneval"), r["passed"].get("humaneval")
        )
        mb = _format_score_cell(
            r["scores"].get("mbpp"), r["n"].get("mbpp"), r["passed"].get("mbpp")
        )
        gt = _format_score_cell(
            r["scores"].get("gad_tools"), r["n"].get("gad_tools"), r["passed"].get("gad_tools")
        )
        he_d = _format_delta_cell(r["deltas_vs_7b_stein_pp"].get("humaneval"))
        mb_d = _format_delta_cell(r["deltas_vs_7b_stein_pp"].get("mbpp"))
        lines.append(
            f"| {r['label']} | `{r['base_model']}` | {he} | {mb} | {gt} | {he_d} | {mb_d} |"
        )

    lines.append("")
    lines.append("## Cost per successful task (USD)")
    lines.append("")
    lines.append("| Rung | GPU | $/run | $/HE-pass | $/MBPP-pass | $/gad_tools-pass |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        cps = r.get("cost_per_successful_task_usd", {}) or {}
        he = cps.get("humaneval")
        mb = cps.get("mbpp")
        gt = cps.get("gad_tools")
        lines.append(
            f"| {r.get('label', r['rung'])} | {r.get('gpu', '?')} | "
            f"${r.get('estimated_cost_usd_per_run', 0):.2f} | "
            f"{('$' + format(he, '.4f')) if he else '—'} | "
            f"{('$' + format(mb, '.4f')) if mb else '—'} | "
            f"{('$' + format(gt, '.4f')) if gt else '—'} |"
        )

    lines.append("")
    lines.append("## Knee detection")
    lines.append("")
    lines.append(
        f"**Criterion:** smallest rung beating 7B Stein canonical "
        f"({ANCHOR_7B_STEIN['humaneval']:.3f} HE / "
        f"{ANCHOR_7B_STEIN['mbpp']:.3f} MBPP) by >= "
        f"{KNEE_HE_DELTA_PP:.1f}pp on HE AND >= "
        f"{KNEE_MBPP_DELTA_PP:.1f}pp on MBPP."
    )
    lines.append("")
    if knee is None:
        lines.append(
            "**Result:** NO RUNG MEETS THE KNEE CRITERION. Recommendation: "
            "stay at 7B Stein canonical; do not fire training above 7B."
        )
    else:
        meta = RUNG_META.get(knee, {})
        lines.append(
            f"**Result:** **{meta.get('label', knee)}** is the smallest "
            f"passing rung. Recommendation: train at this rung if budget "
            f"allows, with holdout-gate thresholds written before "
            f"training (`slm-learning-097`)."
        )

    lines.append("")
    lines.append("## Source files")
    lines.append("")
    for r in rows:
        if r["status"] != "found":
            continue
        for bench, path in r.get("source_paths", {}).items():
            if path:
                lines.append(f"- {r['label']} / {bench}: `{path}`")
    lines.append("")
    lines.append(
        "_Generated by `scripts/eval/scaling_ladder_aggregator.py`. "
        "Decision refs: slm-learning-097, 100, 103, 105, 202, 207, 210._"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rungs",
        default="1.5b,3b,7b,14b,32b,80b-a3b",
        help="Comma-separated rung ids (default: 1.5b,3b,7b,14b,32b,80b-a3b)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output markdown path (default: reports/research/"
             "scaling_ladder_aggregate_<today>.md)",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional JSON sidecar path",
    )
    parser.add_argument(
        "--eval-dir",
        action="append",
        default=[],
        help="Extra directories to search for persisted eval JSONs "
             "(repeatable)",
    )
    args = parser.parse_args()

    rungs = [r.strip().lower() for r in args.rungs.split(",") if r.strip()]
    search_dirs = _candidate_dirs([Path(d) for d in args.eval_dir])

    rows = [_compute_rung_row(rung, search_dirs) for rung in rungs]
    knee = _knee_pick(rows)
    today = dt.date.today().isoformat()

    out_md = (
        Path(args.out)
        if args.out
        else REPO_ROOT / "reports" / "research" / f"scaling_ladder_aggregate_{today}.md"
    )
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(rows, knee, today), encoding="utf-8")
    print(f"[aggregator] wrote {out_md}")

    json_out = (
        Path(args.json_out)
        if args.json_out
        else out_md.with_suffix(".json")
    )
    payload = {
        "schema_v": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "anchor_7b_stein": ANCHOR_7B_STEIN,
        "knee_thresholds_pp": {
            "humaneval": KNEE_HE_DELTA_PP,
            "mbpp": KNEE_MBPP_DELTA_PP,
        },
        "knee_pick": knee,
        "rows": rows,
        "decision_refs": [
            "slm-learning-097",
            "slm-learning-100",
            "slm-learning-103",
            "slm-learning-105",
            "slm-learning-202",
            "slm-learning-207",
            "slm-learning-210",
        ],
    }
    json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[aggregator] wrote {json_out}")

    n_found = sum(1 for r in rows if r["status"] == "found")
    print(f"[aggregator] rungs_found={n_found}/{len(rows)} knee={knee or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
