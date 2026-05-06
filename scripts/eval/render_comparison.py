"""Render a comparative matrix JSON as a paste-ready markdown table.

Reads `experiments/comparative/matrix-*.json` produced by
`scripts/eval/run_comparative_matrix.py` and emits a markdown
document with one section per benchmark + an aggregate cost roll-up.

Usage:

    python scripts/eval/render_comparison.py \\
        --in experiments/comparative/matrix-2026-05-06T1811.json \\
        --out experiments/comparative/matrix-2026-05-06.md

    # Or stdout
    python scripts/eval/render_comparison.py \\
        --in experiments/comparative/matrix-2026-05-06T1811.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def render(matrix: dict) -> str:
    rows = matrix.get("rows", [])
    by_bench: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_bench[r["benchmark"]].append(r)

    lines: list[str] = []
    lines.append(f"# Comparative eval matrix — {matrix.get('ts', '')[:10]}")
    lines.append("")
    lines.append(f"Models: {matrix.get('n_models', '?')} · Benchmarks: {matrix.get('n_benchmarks', '?')}")
    lines.append("")
    lines.append(f"Decision refs: {', '.join(matrix.get('decision_refs', []))}")
    lines.append("")

    for bench, bench_rows in sorted(by_bench.items()):
        lines.append(f"## Benchmark: {bench}")
        lines.append("")
        lines.append("| Model | Tier | n | Score | p50 latency | Cost USD | Tier evidence |")
        lines.append("|---|---|---|---|---|---|---|")
        # Sort: highest score first; nulls/error states last
        bench_rows_sorted = sorted(
            bench_rows,
            key=lambda r: (r.get("score") is None, -(r.get("score") or 0)),
        )
        for r in bench_rows_sorted:
            score = (
                f"**{r['score']:.3f}**" if r.get("score") is not None
                else f"_{r.get('status', '?')}_"
            )
            n = r.get("n", "-")
            p50 = (f"{r['latency_p50_s']}s" if r.get("latency_p50_s") is not None
                   else "-")
            cost = (f"${r['cost_usd']:.4f}" if r.get("cost_usd") is not None
                    else "-")
            tier_ev = r.get("evidence_tier", "-")
            tier = r.get("tier", "-")
            lines.append(f"| `{r['model_id']}` | {tier} | {n} | {score} | {p50} | {cost} | {tier_ev} |")
        lines.append("")

    # Cost roll-up
    total_cost = sum((r.get("cost_usd") or 0) for r in rows)
    by_tier_cost: dict[str, float] = defaultdict(float)
    for r in rows:
        by_tier_cost[r.get("tier") or "?"] += r.get("cost_usd") or 0

    lines.append("## Cost roll-up")
    lines.append("")
    lines.append(f"Total: ${total_cost:.4f}")
    lines.append("")
    lines.append("| Tier | Cost |")
    lines.append("|---|---|")
    for tier, c in sorted(by_tier_cost.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {tier} | ${c:.4f} |")
    lines.append("")

    # Errors / unrunnable rows
    errors = [r for r in rows if r.get("score") is None]
    if errors:
        lines.append("## Unrunnable rows (status != ok)")
        lines.append("")
        lines.append("| Model | Benchmark | Status | Reason |")
        lines.append("|---|---|---|---|")
        for r in errors:
            lines.append(
                f"| `{r['model_id']}` | {r['benchmark']} | "
                f"{r.get('status', '?')} | "
                f"{(r.get('reason') or '')[:120]} |"
            )
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", "-i", dest="inp", type=Path, required=True)
    parser.add_argument("--out", "-o", type=Path, default=None)
    args = parser.parse_args()

    matrix = json.loads(args.inp.read_text(encoding="utf-8"))
    md = render(matrix)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
        print(f"[render] wrote {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
