"""Rule-based codebase attention scorer.

Per concern `.planning/concerns/codebase-attention.md` and decision
`slm-learning-072`. Implements the score formula:

    attention_score =
       +0.30 if production_path
       +0.25 if dependency_centrality_high  (>= 5 inbound imports)
       +0.25 if recent_failures              (touched in failed run last 30d)
       +0.20 if active_phase_relevance       (named in current STATE.xml next-action)
       +0.20 if security_or_data_path        (auth / secret / billing / migration / deploy)
       +0.15 if low_test_coverage            (< 50% lines covered)
       +0.10 if recent_high_churn            (> 10 commits last 30d)
       -0.30 if tmp_or_prototype_or_museum
       -0.20 if skeleton_marked_prototype
       +0.50 if quarantined_or_dangerous     (with explicit warning)

Clamp to [0, 1]. Output the score plus the contributing reasons.

Lane mapping:
    0.00–0.20 free
    0.20–0.40 prototype
    0.40–0.65 dev
    0.65–0.85 integration
    0.85–1.00 production

Output: `.gad/attention/codebase-attention.json` — gitignored, rebuilt
on demand.

Per slm-learning-072: scorer experiments + eval fixtures live here in
slm-learning. Production CLI integration (gad snapshot --attention,
the gad CLI surface) lives in the gad-monorepo. Clean split per
ChatGPT directive 2026-05-06.

Usage:

    .venv/Scripts/python.exe scripts/attention/score.py \\
        --root . \\
        --out .gad/attention/codebase-attention.json

    # Score only the active phase's files:
    .venv/Scripts/python.exe scripts/attention/score.py \\
        --root . \\
        --filter-active-phase

Decision refs: slm-learning-072, slm-learning-061, slm-learning-058.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


ROOT_HINT = Path(__file__).resolve().parents[2]


# Path classifiers
PRODUCTION_PATTERNS = [
    r"^src/",
    r"^scripts/(?!tmp/|sandbox/|prototype/)",
    r"^packages/",
    r"^apps/(?!.*portfolio/)",  # apps/portfolio is deprecated
    r"^lib/",
    r"^bin/",
    r"^(?:src/)?slm_from_scratch/finetune/",
]

PROTOTYPE_PATTERNS = [
    r"^tmp/",
    r"^sandbox/",
    r"^prototype/",
    r"^scratch/",
    r"^\.tmp/",
    r"/prototype/",
    r"/scratch/",
]

MUSEUM_PATTERNS = [
    r"^tmp/museum/",
    r"^archive/",
    r"^.*/_old/",
    r"^.*/_legacy/",
    r"^.*\.skeleton\.",
]

ZOO_PATTERNS = [
    r"^tmp/zoo/",
    r"^.*\.deprecated\.",
]

SECURITY_PATTERNS = [
    r"auth",
    r"secret",
    r"credential",
    r"keychain",
    r"billing",
    r"payment",
    r"stripe",
    r"oauth",
    r"jwt",
    r"migration",
    r"deploy",
    r".env",
    r"webhook",
    r"crypto",
]

# Files to never score (large datasets, generated artifacts)
EXCLUDE_PATTERNS = [
    r"^node_modules/",
    r"^\.venv",
    r"^\.git/",
    r"^dist/",
    r"^build/",
    r"^\.next/",
    r"^__pycache__/",
    r"\.pyc$",
    r"\.lock$",
    r"^data/external/",
    r"^data/raw/",
    r"^data/processed/",
    r"^experiments/runs/.*\.log$",
    r"\.gml$",
    r"\.safetensors$",
    r"\.bin$",
    r"\.pt$",
]


def matches_any(path: str, patterns: list[str]) -> bool:
    for p in patterns:
        if re.search(p, path):
            return True
    return False


def lane_for_score(score: float) -> str:
    if score < 0.20:
        return "free"
    if score < 0.40:
        return "prototype"
    if score < 0.65:
        return "dev"
    if score < 0.85:
        return "integration"
    return "production"


def required_checks_for_lane(lane: str, security_hit: bool = False) -> list[str]:
    base: list[str] = []
    if lane == "free":
        return ["mark_as_prototype"]
    if lane == "prototype":
        return ["smoke_run"]
    if lane == "dev":
        base = ["unit_tests"]
    elif lane == "integration":
        base = ["unit_tests", "integration_tests", "diff_summary", "decision_log"]
    elif lane == "production":
        base = ["unit_tests", "integration_tests", "diff_summary", "decision_log",
                "rollback_plan", "regression_check"]
    if security_hit and lane in {"dev", "integration", "production"}:
        base.append("security_review")
    return base


def list_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if matches_any(rel, EXCLUDE_PATTERNS):
            continue
        files.append(p)
    return files


def git_recent_commits(root: Path, since_days: int = 30) -> dict[str, int]:
    """Return commit counts per file in the last N days."""
    since = (dt.datetime.utcnow() - dt.timedelta(days=since_days)).strftime("%Y-%m-%d")
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "log", f"--since={since}", "--name-only", "--pretty=format:"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError:
        return {}
    counts: Counter[str] = Counter()
    for line in out.splitlines():
        line = line.strip()
        if line:
            counts[line] += 1
    return dict(counts)


def read_active_phase_files(planning_root: Path) -> set[str]:
    """Extract file refs from STATE.xml next-action."""
    state = planning_root / "STATE.xml"
    if not state.exists():
        return set()
    txt = state.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<next-action>(.*?)</next-action>", txt, re.DOTALL)
    if not m:
        return set()
    body = m.group(1)
    paths = set(re.findall(r"\b([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)\b", body))
    return paths


def import_centrality(root: Path) -> dict[str, int]:
    """Approximate inbound-import count per file (Python + JS/TS).

    Cheap heuristic: grep `import ... <basename>` or `from <basename>`.
    """
    files = list_files(root)
    py_ts_files = [p for p in files if p.suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}]
    name_to_files: dict[str, list[Path]] = {}
    for p in py_ts_files:
        rel = p.relative_to(root).as_posix()
        stem = p.stem
        if stem in {"__init__", "index"}:
            continue
        name_to_files.setdefault(stem, []).append(p)

    counts: Counter[str] = Counter()
    for p in py_ts_files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Python imports
        for m in re.finditer(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
                             text, re.MULTILINE):
            mod = (m.group(1) or m.group(2) or "").rsplit(".", 1)[-1]
            if mod in name_to_files:
                for target in name_to_files[mod]:
                    if target != p:
                        counts[target.relative_to(root).as_posix()] += 1
        # JS/TS imports
        for m in re.finditer(r"""(?:import\s+[\w*{},\s]+\s+from|require)\s*\(?\s*["']([^"']+)["']""",
                             text):
            mod_path = m.group(1).rsplit("/", 1)[-1].split(".")[0]
            if mod_path in name_to_files:
                for target in name_to_files[mod_path]:
                    if target != p:
                        counts[target.relative_to(root).as_posix()] += 1
    return dict(counts)


def score_file(path_rel: str, ctx: dict) -> dict:
    score = 0.0
    reasons: list[str] = []

    if matches_any(path_rel, PRODUCTION_PATTERNS):
        score += 0.30
        reasons.append("production_path")

    centrality = ctx["centrality"].get(path_rel, 0)
    if centrality >= 5:
        score += 0.25
        reasons.append(f"dependency_centrality_high ({centrality} inbound)")

    if path_rel in ctx["recent_failure_paths"]:
        score += 0.25
        reasons.append("recent_failures")

    if any(s in path_rel for s in ctx["active_phase_files"]):
        score += 0.20
        reasons.append("active_phase_relevance")

    security_hit = matches_any(path_rel.lower(), SECURITY_PATTERNS)
    if security_hit:
        score += 0.20
        reasons.append("security_or_data_path")

    churn = ctx["churn"].get(path_rel, 0)
    if churn > 10:
        score += 0.10
        reasons.append(f"recent_high_churn ({churn} commits/30d)")

    if matches_any(path_rel, PROTOTYPE_PATTERNS):
        score -= 0.30
        reasons.append("tmp_or_prototype")

    if matches_any(path_rel, MUSEUM_PATTERNS):
        score -= 0.30
        reasons.append("museum_skeleton")

    if matches_any(path_rel, ZOO_PATTERNS):
        score -= 0.20
        reasons.append("zoo_deprecated")

    score = max(0.0, min(1.0, score))
    lane = lane_for_score(score)

    return {
        "path": path_rel,
        "attention_score": round(score, 3),
        "lane": lane,
        "reasons": reasons,
        "required_checks": required_checks_for_lane(lane, security_hit=security_hit),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path,
                        default=Path(".gad/attention/codebase-attention.json"))
    parser.add_argument("--top-n", type=int, default=50,
                        help="Print top-N highest-attention files to stdout")
    parser.add_argument("--filter-active-phase", action="store_true",
                        help="Only score files matching STATE.xml next-action")
    args = parser.parse_args()

    root = args.root.resolve()
    print(f"[attention] root = {root}")

    files = list_files(root)
    print(f"[attention] {len(files)} files in scope")

    centrality = import_centrality(root)
    print(f"[attention] {sum(centrality.values())} import edges; "
          f"{len(centrality)} files with inbound imports")

    churn = git_recent_commits(root, since_days=30)
    print(f"[attention] {len(churn)} files touched in last 30 days")

    active_phase_files = read_active_phase_files(root / ".planning")
    print(f"[attention] {len(active_phase_files)} file refs in STATE.xml next-action")

    # Recent failures: scan trace events for STRUCTURED failure signals only.
    # Loose grep for "error"/"failed" was matching prose-only events (e.g.,
    # planning notes that mention error handling). Tighten to events that
    # have a structured failure shape: kind/role contains "failed" /
    # "rejected" / "error", OR a non-zero exit_code field, OR an explicit
    # status="failed".
    recent_failure_paths: set[str] = set()
    trace = root / ".planning" / ".trace-events.jsonl"
    FAIL_KIND_RE = re.compile(r'"(?:kind|role|status|action)"\s*:\s*"[^"]*(fail|reject|error|fault)[^"]*"',
                               re.IGNORECASE)
    EXIT_NONZERO_RE = re.compile(r'"(?:exit_code|returncode)"\s*:\s*[1-9]\d*')
    if trace.exists():
        try:
            for line in trace.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]:
                if not line.strip():
                    continue
                if not (FAIL_KIND_RE.search(line) or EXIT_NONZERO_RE.search(line)):
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = json.dumps(e)
                # Only attribute to file paths that look like real source paths
                # (have a directory separator + a real extension).
                for m in re.finditer(r"([a-zA-Z0-9_\-./]+/[a-zA-Z0-9_\-]+\.[a-zA-Z]{1,4})\b", content):
                    p = m.group(1)
                    if not p.startswith(("http", "#", "<")):
                        recent_failure_paths.add(p)
        except OSError:
            pass

    ctx = {
        "centrality": centrality,
        "churn": churn,
        "active_phase_files": active_phase_files,
        "recent_failure_paths": recent_failure_paths,
    }

    scored: list[dict] = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        if args.filter_active_phase and rel not in active_phase_files:
            continue
        scored.append(score_file(rel, ctx))

    scored.sort(key=lambda r: r["attention_score"], reverse=True)

    lane_counts = Counter(r["lane"] for r in scored)
    summary = {
        "schema_v": 1,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "root": str(root),
        "n_files": len(scored),
        "lane_counts": dict(lane_counts),
        "top_n": scored[:args.top_n],
        "all": scored,
        "decision_refs": ["slm-learning-072"],
        "evidence_tier": "T1",
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n[attention] lane counts: {dict(lane_counts)}")
    print(f"[attention] top {min(10, len(scored))} highest-attention files:")
    for r in scored[:10]:
        print(f"  {r['attention_score']:.2f}  {r['lane']:<12}  {r['path']}  "
              f"({', '.join(r['reasons'])})")
    print(f"\n[attention] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
