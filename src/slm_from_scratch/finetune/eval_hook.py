"""Post-train eval auto-runner.

Single concern: given a trained adapter directory, run a list of named
benchmarks against it and return a dict of {benchmark: score_dict}.

Each benchmark is a callable that takes (adapter_dir, base_model,
tokenizer, eval_settings) and returns a dict of metrics. The registry
makes it easy to add new ones (HumanEval, GSM8K, etc.) without changing
the orchestrator.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from slm_from_scratch.finetune.config import EvalSettings, FinetuneConfig


ROOT = Path(__file__).resolve().parents[3]


def _run_subprocess_eval(
    script: str, args: list[str], expected_out: Path
) -> dict:
    """Run a scripts/eval_*.py and return the parsed JSON it wrote."""
    python_exe = ROOT / ".venv-gpu" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = Path(sys.executable)
    cmd = [str(python_exe), str(ROOT / "scripts" / script), *args]
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        return {"error": f"eval script failed: rc={proc.returncode}"}
    if expected_out.exists():
        return json.loads(expected_out.read_text(encoding="utf-8"))
    return {"error": "eval ran but produced no output JSON"}


def eval_gad_tools(adapter_dir: Path, eval_settings: "EvalSettings") -> dict:
    """Score the GAD-tool eval against a PEFT adapter.

    Note: this assumes the eval script can load a PEFT adapter; for now
    we point at adapter_dir as if it were a checkpoint and require that
    the eval-side `DrSteinModel` knows what to do. If the adapter format
    isn't supported yet, returns a placeholder so the pipeline still
    completes and the human sees the gap.
    """
    out_path = adapter_dir.parent / "eval_gad_tools.json"
    return _run_subprocess_eval(
        "eval_checkpoint.py",
        [
            "--checkpoint", str(adapter_dir),
            "--out", str(out_path),
            "--name", adapter_dir.parent.name,
            "--max-new-tokens", str(eval_settings.max_new_tokens),
            "--temperature", str(eval_settings.temperature),
            "--device", "auto",
        ],
        out_path,
    )


REGISTRY: dict[str, Callable[[Path, "EvalSettings"], dict]] = {
    "gad_tools": eval_gad_tools,
}


def run_evals(adapter_dir: Path, cfg: "FinetuneConfig") -> dict:
    if not cfg.eval.run_after_train:
        return {}
    results: dict = {}
    for name in cfg.eval.benchmarks:
        runner = REGISTRY.get(name)
        if runner is None:
            results[name] = {"error": f"no runner registered for '{name}'"}
            continue
        results[name] = runner(adapter_dir, cfg.eval)
    return results
