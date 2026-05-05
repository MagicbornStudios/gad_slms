"""
Evaluate a single checkpoint against the GAD-tool prompts in
promptfoo-gad-tools.yaml. Pure Python, no promptfoo subprocess.

  .venv-gpu/Scripts/python.exe scripts/eval_checkpoint.py \
      --checkpoint runs/finetuned/dr_stein.pt \
      --eval promptfoo-gad-tools.yaml \
      --out runs/eval/dr_stein_gadtools.json

Score = passed / total. Each test from the YAML is interpreted via the
same (small) subset of assertion types we use in promptfoo:
   icontains, contains-any, is-json.

That subset is enough to score every existing GAD-tool test and avoids
pulling promptfoo into the Python venv. We also append a one-liner to
experiments/INDEX.md so cross-checkpoint comparison happens in one place.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

INDEX_MD = ROOT / "experiments" / "INDEX.md"


def load_eval_yaml(path: Path) -> dict:
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def run_assertion(assertion: dict, output: str) -> tuple[bool, str]:
    atype = assertion.get("type", "")
    value = assertion.get("value")
    out_lc = output.lower()
    if atype == "icontains":
        if not isinstance(value, str):
            return False, f"icontains needs string, got {type(value)}"
        return (value.lower() in out_lc), f"icontains '{value}'"
    if atype == "contains-any":
        if not isinstance(value, list):
            return False, f"contains-any needs list, got {type(value)}"
        for v in value:
            if str(v).lower() in out_lc:
                return True, f"contains-any matched '{v}'"
        return False, f"contains-any none of {value}"
    if atype == "is-json":
        try:
            json.loads(output)
            return True, "is-json parsed"
        except Exception as e:
            return False, f"is-json failed: {e}"
    return False, f"unknown assertion type: {atype}"


def score_test(test: dict, output: str) -> dict:
    asserts = test.get("assert", [])
    results = []
    for a in asserts:
        ok, why = run_assertion(a, output)
        results.append({"ok": ok, "why": why})
    passed = all(r["ok"] for r in results) if results else False
    return {
        "description": test.get("description", ""),
        "instruction": test.get("vars", {}).get("instruction", ""),
        "output": output,
        "asserts": results,
        "passed": passed,
    }


def append_index(name: str, summary: dict) -> None:
    INDEX_MD.parent.mkdir(parents=True, exist_ok=True)
    if not INDEX_MD.exists():
        INDEX_MD.write_text(
            "# Experiment Index\n\n"
            "| run | started | stage | epochs | lr | max_pairs | final_loss | elapsed | gad_tools_passed | notes |\n"
            "|-----|---------|-------|--------|----|-----------|-----------|---------|------------------|-------|\n",
            encoding="utf-8",
        )
    line = (
        f"| {name} EVAL "
        f"| {summary['evaluated_at']} "
        f"|  |  |  |  |  |  "
        f"| {summary['passed']}/{summary['total']} ({summary['pct']:.1f}%) "
        f"| {summary.get('notes', '')} |\n"
    )
    with INDEX_MD.open("a", encoding="utf-8") as f:
        f.write(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--eval", type=Path, default=ROOT / "promptfoo-gad-tools.yaml")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--name", default=None, help="Run name for INDEX.md row (default: checkpoint stem)")
    parser.add_argument("--max-new-tokens", type=int, default=50)
    parser.add_argument("--temperature", type=float, default=0.0,
                        help="0.0 = greedy (deterministic); >0 enables sampling")
    parser.add_argument("--device", default="auto",
                        help="auto | cuda | cpu (default: auto = cuda if available)")
    args = parser.parse_args()

    if not args.checkpoint.exists():
        print(f"checkpoint not found: {args.checkpoint}", file=sys.stderr)
        return 2

    eval_doc = load_eval_yaml(args.eval)
    tests = eval_doc.get("tests", [])
    if not tests:
        print(f"no tests in {args.eval}", file=sys.stderr)
        return 2

    # Load DrStein with the explicit checkpoint path
    from slm_from_scratch.models.dr_stein import DrSteinModel
    model = DrSteinModel(model_path=str(args.checkpoint), device=args.device)
    print(f"Loaded checkpoint: {args.checkpoint} (device={model.device}, temp={args.temperature})")

    started = time.time()
    results = []
    per_test_sec = []
    for i, t in enumerate(tests, start=1):
        prompt = t.get("vars", {}).get("instruction", "")
        if not prompt:
            continue
        t0 = time.time()
        try:
            out = model.generate(prompt, max_new_tokens=args.max_new_tokens, temperature=args.temperature)
        except Exception as e:
            out = f"<<error: {e}>>"
        dt = time.time() - t0
        per_test_sec.append(round(dt, 3))
        scored = score_test(t, out)
        scored["elapsed_sec"] = round(dt, 3)
        results.append(scored)
        marker = "[OK]" if scored["passed"] else "[FAIL]"
        print(f"  {marker} {i:02d}/{len(tests)} {scored['description']} ({dt:.2f}s)", flush=True)

    elapsed = time.time() - started
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    pct = 100.0 * passed / total if total else 0.0
    summary = {
        "checkpoint": str(args.checkpoint.relative_to(ROOT)) if args.checkpoint.is_relative_to(ROOT) else str(args.checkpoint),
        "eval": str(args.eval.relative_to(ROOT)) if args.eval.is_relative_to(ROOT) else str(args.eval),
        "device": str(model.device),
        "temperature": args.temperature,
        "max_new_tokens": args.max_new_tokens,
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_sec": round(elapsed, 1),
        "per_test_sec": per_test_sec,
        "passed": passed,
        "total": total,
        "pct": pct,
        "results": results,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    name = args.name or args.checkpoint.stem
    append_index(name, summary)

    print(f"\n{passed}/{total} passed ({pct:.1f}%) — wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
