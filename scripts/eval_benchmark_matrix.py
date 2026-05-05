"""
Run HumanEval + GSM8K against every available checkpoint.

  .venv-gpu/Scripts/python.exe scripts/eval_benchmark_matrix.py

By default scores:
  - dr_stein.pt (Phase 02 final)
  - sft_model.pt (Phase 02 stage 1) if it exists
  - reasoning_model.pt (Phase 02 stage 2) if it exists
  - every experiments/runs/<name>/checkpoint.pt

Writes per-(checkpoint,benchmark) JSON next to each checkpoint, and
appends a single-line summary to experiments/INDEX.md keyed by the
checkpoint name.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "experiments" / "runs"
PHASE02_DIR = ROOT / "runs" / "finetuned"
INDEX_MD = ROOT / "experiments" / "INDEX.md"


def discover_checkpoints() -> list[tuple[str, Path]]:
    """Return [(name, target_path), ...] for every eval target.

    Two shapes are supported:
      - .pt file       (MiniLlama state_dict) -> Phase 02 + early sweep
      - adapter/ dir   (PEFT adapter)         -> Stage 2.5+ TRL/PEFT runs
    """
    targets: list[tuple[str, Path]] = []
    for stem in ("sft_model", "reasoning_model", "dr_stein"):
        p = PHASE02_DIR / f"{stem}.pt"
        if p.exists():
            targets.append((stem, p))
    if RUNS_DIR.exists():
        for run_dir in sorted(RUNS_DIR.iterdir()):
            if not run_dir.is_dir():
                continue
            ckpt = run_dir / "checkpoint.pt"
            adapter = run_dir / "adapter"
            if ckpt.exists():
                targets.append((run_dir.name, ckpt))
            elif (adapter / "adapter_config.json").exists():
                targets.append((run_dir.name, adapter))
    return targets


def run_eval(script: str, checkpoint: Path, out: Path, name: str,
             n: int, max_new_tokens: int, temperature: float, device: str,
             python_exe: Path) -> tuple[int, float]:
    """Run a single eval subprocess. Returns (returncode, elapsed_sec)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(python_exe), str(ROOT / "scripts" / script),
        "--checkpoint", str(checkpoint),
        "--out", str(out),
        "--name", name,
        "--n", str(n),
        "--max-new-tokens", str(max_new_tokens),
        "--temperature", str(temperature),
        "--device", device,
    ]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env)
    return proc.returncode, time.time() - t0


def parse_score(out_path: Path, key: str) -> tuple[int, int, float] | None:
    if not out_path.exists():
        return None
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data.get("passed", 0), data.get("total", 0), float(data.get(key, 0.0))


def append_index(name: str, kind: str, score: tuple[int, int, float], when: str, note: str) -> None:
    INDEX_MD.parent.mkdir(parents=True, exist_ok=True)
    if not INDEX_MD.exists():
        INDEX_MD.write_text(
            "# Experiment Index\n\n"
            "| run | started | stage | epochs | lr | max_pairs | final_loss | elapsed | gad_tools_passed | notes |\n"
            "|-----|---------|-------|--------|----|-----------|-----------|---------|------------------|-------|\n",
            encoding="utf-8",
        )
    passed, total, pct = score
    line = (
        f"| {name} EVAL ({kind}) | {when} |  |  |  |  |  |  "
        f"| {passed}/{total} ({pct:.1f}%) | {note} |\n"
    )
    with INDEX_MD.open("a", encoding="utf-8") as f:
        f.write(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--humaneval-n", type=int, default=20,
                        help="Number of HumanEval problems (0 = all 164)")
    parser.add_argument("--gsm8k-n", type=int, default=100,
                        help="Number of GSM8K problems (0 = all 1319)")
    parser.add_argument("--humaneval-max-tokens", type=int, default=128)
    parser.add_argument("--gsm8k-max-tokens", type=int, default=200)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--skip-humaneval", action="store_true")
    parser.add_argument("--skip-gsm8k", action="store_true")
    parser.add_argument("--rerun", action="store_true",
                        help="Re-eval even if output JSON exists")
    parser.add_argument("--only", default=None,
                        help="Comma-separated checkpoint names (e.g. dr_stein,higher_lr)")
    args = parser.parse_args()

    python_exe = ROOT / ".venv-gpu" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    targets = discover_checkpoints()
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        targets = [t for t in targets if t[0] in wanted]
    if not targets:
        print("No checkpoints discovered.", file=sys.stderr)
        return 1

    print(f"Benchmark matrix over {len(targets)} checkpoint(s) "
          f"(HumanEval n={args.humaneval_n}, GSM8K n={args.gsm8k_n})")

    matrix: dict[str, dict[str, tuple[int, int, float] | None]] = {}
    for i, (name, ckpt) in enumerate(targets, start=1):
        out_dir = ckpt.parent
        matrix[name] = {}

        # HumanEval
        if not args.skip_humaneval:
            he_out = out_dir / "eval_humaneval.json"
            if he_out.exists() and not args.rerun:
                print(f"\n[{i}/{len(targets)}] {name} HumanEval — already present, skipping")
            else:
                print(f"\n[{i}/{len(targets)}] {name} HumanEval...")
                rc, dt = run_eval("eval_humaneval.py", ckpt, he_out, name,
                                  args.humaneval_n, args.humaneval_max_tokens,
                                  args.temperature, args.device, python_exe)
                print(f"  -> rc={rc} in {dt:.1f}s")
            score = parse_score(he_out, "pass_at_1")
            matrix[name]["humaneval"] = score
            if score is not None:
                append_index(name, "humaneval", score,
                             time.strftime("%Y-%m-%dT%H:%M:%S"),
                             f"n={args.humaneval_n} temp={args.temperature} device={args.device}")

        # GSM8K
        if not args.skip_gsm8k:
            gs_out = out_dir / "eval_gsm8k.json"
            if gs_out.exists() and not args.rerun:
                print(f"\n[{i}/{len(targets)}] {name} GSM8K — already present, skipping")
            else:
                print(f"\n[{i}/{len(targets)}] {name} GSM8K...")
                rc, dt = run_eval("eval_gsm8k.py", ckpt, gs_out, name,
                                  args.gsm8k_n, args.gsm8k_max_tokens,
                                  args.temperature, args.device, python_exe)
                print(f"  -> rc={rc} in {dt:.1f}s")
            score = parse_score(gs_out, "accuracy")
            matrix[name]["gsm8k"] = score
            if score is not None:
                append_index(name, "gsm8k", score,
                             time.strftime("%Y-%m-%dT%H:%M:%S"),
                             f"n={args.gsm8k_n} temp={args.temperature} device={args.device}")

    print("\n" + "=" * 60)
    print(f"{'checkpoint':<30} {'humaneval':<14} {'gsm8k':<14}")
    print("-" * 60)
    for name in matrix:
        he = matrix[name].get("humaneval")
        gs = matrix[name].get("gsm8k")
        he_str = f"{he[0]}/{he[1]} ({he[2]:.1f}%)" if he else "-"
        gs_str = f"{gs[0]}/{gs[1]} ({gs[2]:.1f}%)" if gs else "-"
        print(f"{name:<30} {he_str:<14} {gs_str:<14}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
