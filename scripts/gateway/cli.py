"""CLI wrapper for the GAD Gateway router.

Usage:

    python -m scripts.gateway.cli --task-shape gad_decision --prompt "..."
    python -m scripts.gateway.cli --task-shape gad_decision --prompt "..." --dry-run
    python -m scripts.gateway.cli --task-shape gad_decision --prompt "..." --tier 2 --json

By default emits a human-readable summary; with ``--json`` emits the
full RouterResult dict. Decision refs: slm-learning-208.
"""
from __future__ import annotations

import argparse
import json
import sys

from .router import route


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m scripts.gateway.cli",
        description="Route a prompt by task_shape through the GAD Gateway.",
    )
    p.add_argument("--task-shape", required=True,
                   help="Logical task shape (e.g. gad_note, code_repair).")
    p.add_argument("--prompt", required=True, help="Prompt to forward to the routed model.")
    p.add_argument("--tier", choices=["0", "1", "2", "3"], default=None,
                   help="Force a tier hint (v1: logged but not yet enforced).")
    p.add_argument("--dry-run", action="store_true",
                   help="Log routing decision only — no model call, no trace row written.")
    p.add_argument("--json", action="store_true", dest="emit_json",
                   help="Emit machine-readable RouterResult dict instead of human text.")
    p.add_argument("--context", default=None,
                   help="Optional JSON dict of structured context to attach to the trace.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    context = None
    if args.context:
        try:
            context = json.loads(args.context)
        except json.JSONDecodeError as exc:
            print(f"[gateway-cli] --context must be valid JSON: {exc}", file=sys.stderr)
            return 2

    try:
        result = route(
            args.task_shape,
            args.prompt,
            context=context,
            tier_hint=args.tier,
            dry_run=args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[gateway-cli] route failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if args.emit_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print(f"[gateway] task_shape={result.task_shape}  route={result.route_id}  tier={result.tier}")
    print(f"[gateway] model_id={result.model_id}  accepted_by={result.accepted_by}")
    print(f"[gateway] latency={result.latency_seconds}s  cost_usd={result.cost_usd}")
    if result.dry_run:
        print(f"[gateway] DRY RUN — no model called, no trace written.")
    print(f"[gateway] fallback_chain={result.fallback_chain}")
    print(f"[gateway] trace_row_id={result.trace_row_id}")
    print()
    print(result.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
