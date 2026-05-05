"""Magnitude-prune a saved PEFT adapter and write the pruned variant.

  .venv-gpu/Scripts/python.exe scripts/prune_adapter.py \
      --adapter experiments/runs/stage25_gad_tools_lora/adapter \
      --sparsity 0.3 \
      --out experiments/runs/stage25_gad_tools_lora_pruned30/adapter

The pruned adapter can then be re-trained via scripts/18_stage25_finetune.py
with --base-adapter (future flag) or used as-is for eval.

Per decision slm-learning-014, the iterative train -> prune -> retrain
loop is the core development cycle; this is the prune step.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True,
                        help="Source PEFT adapter directory")
    parser.add_argument("--out", type=Path, required=True,
                        help="Where to write the pruned adapter")
    parser.add_argument("--sparsity", type=float, default=0.3,
                        help="Fraction of smallest-magnitude weights to zero (0,1)")
    parser.add_argument("--base-model", default=None,
                        help="Override base model (default: read from adapter_config.json)")
    args = parser.parse_args()

    if not (args.adapter / "adapter_config.json").exists():
        print(f"not a PEFT adapter: {args.adapter}", file=sys.stderr)
        return 2

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    from slm_from_scratch.finetune.pruning import magnitude_prune, measure_sparsity

    cfg = json.loads((args.adapter / "adapter_config.json").read_text(encoding="utf-8"))
    base = args.base_model or cfg.get("base_model_name_or_path")
    if not base:
        print("base_model_name_or_path missing in adapter_config.json", file=sys.stderr)
        return 2

    print(f"Loading {base} + adapter {args.adapter} ...")
    model = AutoModelForCausalLM.from_pretrained(base, dtype=torch.bfloat16, device_map="auto")
    model = PeftModel.from_pretrained(model, str(args.adapter))

    pre = measure_sparsity(model)
    print(f"Sparsity before: {pre:.3%}")
    report = magnitude_prune(model, sparsity=args.sparsity)
    post = measure_sparsity(model)
    print(f"Sparsity after:  {post:.3%}  (target {args.sparsity:.0%}, "
          f"layers={report['layers_pruned']}, "
          f"zeroed={report['params_zeroed']:,}/{report['params_total']:,})")

    args.out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(args.out))
    try:
        AutoTokenizer.from_pretrained(str(args.adapter)).save_pretrained(str(args.out))
    except Exception:
        AutoTokenizer.from_pretrained(base).save_pretrained(str(args.out))

    (args.out.parent / "PRUNE_REPORT.json").write_text(
        json.dumps(
            {
                "source": str(args.adapter),
                "sparsity_target": args.sparsity,
                "actual_sparsity": post,
                "report": report,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote pruned adapter -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
