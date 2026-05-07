"""Aggregate HumanEval + MBPP eval logs into the public-benchmark row.

Reads experiments/runs/_eval_*_n164.log files, extracts the JSON result
printed by modal_app/eval_adapter.py at completion, and emits a single
comparator-matrix markdown report.

Per slm-learning-103 the public row is one of four required rows for
candidate promotion. This script produces the markdown that goes into
.planning/notes/<date>-comparator-matrix-public-row.md and a one-line
append per (model, benchmark) into experiments/INDEX.md.

Run:
    .venv/Scripts/python.exe scripts/eval/aggregate_public_matrix.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "experiments" / "runs"
INDEX_MD = REPO_ROOT / "experiments" / "INDEX.md"
NOTES_DIR = REPO_ROOT / ".planning" / "notes"


# Map log-file stems to (model_label, benchmark)
LOG_TO_MODEL = {
    "_eval_humaneval_7b_n164": ("7B coder LoRA", "humaneval"),
    "_eval_mbpp_7b_n164": ("7B coder LoRA", "mbpp"),
    "_eval_humaneval_3b_n164": ("3B coder LoRA", "humaneval"),
    "_eval_mbpp_3b_n164": ("3B coder LoRA", "mbpp"),
    "_eval_humaneval_7b_base_n164": ("7B base (no LoRA)", "humaneval"),
    "_eval_mbpp_7b_base_n164": ("7B base (no LoRA)", "mbpp"),
}


def extract_result_json(log_path: Path) -> Optional[dict]:
    """Pull the trailing `result = json.dumps(...)` block from a modal log.

    Returns the parsed dict, or None if the log didn't complete or
    failed before the summary block.
    """
    if not log_path.exists():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")

    # The summary is printed by main() as `print(json.dumps(result, indent=2)[:3000])`
    # The result has top-level keys: schema_v, ts, adapter_id, base_model,
    # benchmark, n, passed, score, results (list).
    # The print is preceded by a blank line. We anchor on `"schema_v": 1`.
    m = re.search(r'\{\s*"schema_v":\s*1.*?"results":\s*\[', text, re.DOTALL)
    if not m:
        return None

    # Best-effort: find a balanced JSON object starting at m.start().
    start = m.start()
    depth = 0
    end = None
    for i, c in enumerate(text[start:], start=start):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        # Truncated by the [:3000] cap. Hand-parse the easy fields.
        easy = {}
        for key in ("schema_v", "n", "passed"):
            mm = re.search(rf'"{key}":\s*(\d+)', text[start:start+3000])
            if mm:
                easy[key] = int(mm.group(1))
        for key in ("score",):
            mm = re.search(rf'"{key}":\s*([0-9.]+)', text[start:start+3000])
            if mm:
                easy[key] = float(mm.group(1))
        for key in ("ts", "adapter_id", "base_model", "benchmark"):
            mm = re.search(rf'"{key}":\s*"([^"]+)"', text[start:start+3000])
            if mm:
                easy[key] = mm.group(1)
        return easy or None

    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None


def detect_status(log_path: Path) -> str:
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    if "[eval] DONE" in text:
        return "ok"
    if "Stopping app - uncaught exception" in text or "Traceback" in text:
        return "error"
    if "[main] firing eval" in text:
        return "running"
    return "missing"


def main() -> None:
    rows: list[dict] = []
    for stem, (label, benchmark) in LOG_TO_MODEL.items():
        log = RUNS_DIR / f"{stem}.log"
        status = detect_status(log)
        result = extract_result_json(log)
        rows.append({
            "model": label,
            "benchmark": benchmark,
            "status": status,
            "result": result,
            "log_path": str(log.relative_to(REPO_ROOT)),
        })

    today = dt.date.today().isoformat()
    out_md = NOTES_DIR / f"{today}-comparator-matrix-public-row.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# Public-benchmark row — {today}")
    lines.append("")
    lines.append("Aggregated from `experiments/runs/_eval_*_n164.log`. Per "
                 "decision `slm-learning-103` this is the public-leaderboard "
                 "row of the comparator matrix; pair with the frontier-comparator, "
                 "owned-domain, and lineage rows before promoting any candidate.")
    lines.append("")
    lines.append("## Scores (n=164 each)")
    lines.append("")
    lines.append("| Model | HumanEval | MBPP | Notes |")
    lines.append("|---|---|---|---|")

    # Group by model
    by_model: dict[str, dict[str, dict]] = {}
    for row in rows:
        by_model.setdefault(row["model"], {})[row["benchmark"]] = row

    for model in ["7B coder LoRA", "7B base (no LoRA)", "3B coder LoRA"]:
        m = by_model.get(model, {})
        cells = []
        for bench in ("humaneval", "mbpp"):
            r = m.get(bench)
            if r and r["status"] == "ok" and r.get("result"):
                res = r["result"]
                passed = res.get("passed", "?")
                n = res.get("n", "?")
                score = res.get("score", 0.0)
                cells.append(f"**{passed}/{n} ({score:.1%})**")
            elif r and r["status"] == "running":
                cells.append("running")
            elif r and r["status"] == "error":
                cells.append(f"error ([log]({r['log_path']}))")
            else:
                cells.append("missing")
        notes = ""
        if model == "7B coder LoRA":
            notes = "Qwen2.5-Coder-7B-Instruct + LoRA r=16 on OpenCodeReasoning n=5000, 1 epoch, A100 (training)"
        elif model == "7B base (no LoRA)":
            notes = "Qwen2.5-Coder-7B-Instruct base — control row to measure LoRA delta"
        elif model == "3B coder LoRA":
            notes = "Qwen2.5-Coder-3B-Instruct + LoRA r=16 same recipe as 7B"
        lines.append(f"| {model} | {cells[0]} | {cells[1]} | {notes} |")

    lines.append("")
    lines.append("## LoRA delta vs base (HumanEval + MBPP combined)")
    lines.append("")

    base_he = by_model.get("7B base (no LoRA)", {}).get("humaneval", {}).get("result")
    base_mb = by_model.get("7B base (no LoRA)", {}).get("mbpp", {}).get("result")
    lora_he = by_model.get("7B coder LoRA", {}).get("humaneval", {}).get("result")
    lora_mb = by_model.get("7B coder LoRA", {}).get("mbpp", {}).get("result")

    if base_he and lora_he:
        delta_he = (lora_he.get("score", 0) - base_he.get("score", 0)) * 100
        lines.append(f"- HumanEval delta: **{delta_he:+.1f}pp** "
                     f"({base_he.get('score', 0):.1%} → {lora_he.get('score', 0):.1%})")
    if base_mb and lora_mb:
        delta_mb = (lora_mb.get("score", 0) - base_mb.get("score", 0)) * 100
        lines.append(f"- MBPP delta: **{delta_mb:+.1f}pp** "
                     f"({base_mb.get('score', 0):.1%} → {lora_mb.get('score', 0):.1%})")

    lines.append("")
    lines.append("## Lineage (per slm-learning-100 Delta Graph schema)")
    lines.append("")
    lines.append("| Model | base | parents | rank | dataset | training | adapter | manifest |")
    lines.append("|---|---|---|---|---|---|---|---|")
    lines.append("| 7B coder LoRA | Qwen2.5-Coder-7B-Instruct | base | 16 | OpenCodeReasoning n=5000 | 1 epoch, lr=2e-4, A100 34min ($1.58) | `/models/runs/ladder-7b-coder-2026-05-08/adapter` | `MANIFEST.json` |")
    lines.append("| 3B coder LoRA | Qwen2.5-Coder-3B-Instruct | base | 16 | OpenCodeReasoning n=5000 | 1 epoch, lr=2e-4, A10G 53min ($0.97) | `/models/runs/ladder-3b-coder-2026-05-08/adapter` | `MANIFEST.json` |")

    lines.append("")
    lines.append("## Frontier comparator (claude-cli on owned-domain)")
    lines.append("")
    lines.append("Existing data from `experiments/runs/comparator_*_gad_tools_v2.json`:")
    lines.append("")
    lines.append("| Model | gad_tools_v2 (owned domain) | Cost |")
    lines.append("|---|---|---|")
    lines.append("| ours-via-modal-v2 | 30/30 (100.0%) | $0.00 |")
    lines.append("| claude-cli (frontier) | 24/30 (80.0%) | $0.0048 |")
    lines.append("")
    lines.append("**Owned-domain win on `gad_tools_v2`: +20pp over claude-cli at $0/call.** "
                 "The public-benchmark row above complements this with the standard coder benchmarks.")
    lines.append("")
    lines.append("## Decision refs")
    lines.append("")
    lines.append("- `slm-learning-094` — composition-of-specialists path")
    lines.append("- `slm-learning-097` — two-shot $50 discipline (32B shot gate)")
    lines.append("- `slm-learning-100` — Delta Graph schema")
    lines.append("- `slm-learning-103` — compare-and-compete mandatory (4 rows per candidate)")
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[matrix] wrote {out_md.relative_to(REPO_ROOT)}")

    # Append to INDEX.md
    if INDEX_MD.exists():
        index_text = INDEX_MD.read_text(encoding="utf-8")
    else:
        index_text = ""

    appended = []
    for row in rows:
        if row["status"] != "ok" or not row.get("result"):
            continue
        res = row["result"]
        ts = res.get("ts", dt.datetime.now(dt.timezone.utc).isoformat())
        passed = res.get("passed", "?")
        n = res.get("n", "?")
        score = res.get("score", 0.0)
        # adapter_id may be a long path; collapse to a label
        adapter_id = res.get("adapter_id", "?")
        if adapter_id and adapter_id != "BASE":
            adapter_id = adapter_id.rsplit("/", 2)[-2]  # extract run_id
        line = f"| {adapter_id} EVAL ({row['benchmark']}) | {ts} |  |  |  |  |  |  | {passed}/{n} ({score:.1%}) | n={n} temp=0.0 device=cuda gpu=A10G/L4 modal-public-row |"
        # Avoid duplicates
        if line not in index_text:
            appended.append(line)

    if appended:
        with INDEX_MD.open("a", encoding="utf-8") as fh:
            fh.write("\n")
            fh.write("\n".join(appended))
            fh.write("\n")
        print(f"[matrix] appended {len(appended)} rows to {INDEX_MD.relative_to(REPO_ROOT)}")
    else:
        print(f"[matrix] no completed eval rows ready to append")


if __name__ == "__main__":
    main()
