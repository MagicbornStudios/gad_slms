"""Aggregate morphism prototype eval results into reports/evals/morphism_0p5b_variant_a.md.

Inputs (read from local copies pulled via `modal volume get slm-models eval-runs/...`):
  - Arm A (base, 0.5B): tmp/diag-2026-05-08/base_he_0p5b_full.json + base_mbpp_0p5b_full.json
  - Arm B (LoRA): tmp/diag-2026-05-08/lora_0p5b_he_full.json + lora_0p5b_mbpp_full.json
  - Arm C (morphism Variant A): tmp/diag-2026-05-08/morphism_0p5b_he_full.json + morphism_0p5b_mbpp_full.json

Outputs:
  - reports/evals/morphism_0p5b_variant_a_2026-05-08.md
  - reports/evals/morphism_0p5b_variant_a_2026-05-08.json (machine-readable)

Decision refs: slm-learning-103, slm-learning-130, slm-learning-165, slm-learning-169.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[WARN] {path}: {e}", file=sys.stderr)
        return None


def fmt_pct(score) -> str:
    if score is None:
        return "n/a"
    if isinstance(score, (int, float)):
        return f"{100 * float(score):.1f}%"
    return str(score)


def fmt_delta(after, before) -> str:
    if after is None or before is None:
        return "n/a"
    delta_pp = (float(after) - float(before)) * 100
    arrow = "⬆" if delta_pp > 0 else ("⬇" if delta_pp < 0 else "—")
    return f"{delta_pp:+.1f} pp {arrow}"


def render(args, base_he, base_mbpp, lora_he, lora_mbpp, morph_he, morph_mbpp,
           train_manifest_lora, train_manifest_morph) -> tuple[str, dict]:
    rows = []
    for label, he, mbpp in [
        ("0.5B base (Arm A)", base_he, base_mbpp),
        ("0.5B + LoRA r=16 (Arm B, control)", lora_he, lora_mbpp),
        ("0.5B + morphism Variant A (Arm C)", morph_he, morph_mbpp),
    ]:
        rows.append({
            "label": label,
            "he_n": he.get("n") if he else None,
            "he_passed": he.get("passed") if he else None,
            "he_score": he.get("score") if he else None,
            "mbpp_n": mbpp.get("n") if mbpp else None,
            "mbpp_passed": mbpp.get("passed") if mbpp else None,
            "mbpp_score": mbpp.get("score") if mbpp else None,
        })

    # init agreement (from morphism manifest)
    init_agree = None
    if train_manifest_morph:
        init_agree = (train_manifest_morph
                      .get("morphism", {})
                      .get("init_agreement_mean"))

    # trainable params
    morph_trainable = (train_manifest_morph or {}).get("trainable_params_M")
    lora_trainable = (train_manifest_lora or {}).get("trainable_params_M")

    # wall + cost (cost is computed below)
    morph_wall = (train_manifest_morph or {}).get("wall_seconds")
    lora_wall = (train_manifest_lora or {}).get("wall_seconds")

    # Cost from wall: A10G ~ $0.83/hr (Modal pricing, public), A100 ~ $4/hr.
    # Use per-manifest compute_target if present.
    def cost_estimate(manifest):
        if not manifest:
            return None
        target = (manifest.get("compute_target", "") or "").lower()
        wall_sec = manifest.get("wall_seconds") or 0
        rate_per_hour = {
            "modal-a10g": 0.83,
            "modal-l4": 0.55,
            "modal-a100": 4.0,
            "modal-a100-40gb": 4.0,
            "modal-a100-80gb": 6.0,
        }.get(target, 1.0)
        return round(rate_per_hour * (wall_sec / 3600), 4)

    morph_cost = cost_estimate(train_manifest_morph)
    lora_cost = cost_estimate(train_manifest_lora)

    pass_init = "PASS" if (init_agree is not None and init_agree >= 0.99) else (
        "FAIL" if init_agree is not None else "n/a")

    # Pass/fail vs charter Arm 2 criteria
    arm_a_he = rows[0]["he_score"]
    arm_b_he = rows[1]["he_score"]
    arm_c_he = rows[2]["he_score"]
    arm_b_mbpp = rows[1]["mbpp_score"]
    arm_c_mbpp = rows[2]["mbpp_score"]

    def within_2pp(a, b):
        if a is None or b is None:
            return None
        return abs(float(a) - float(b)) * 100 <= 2.0

    he_within = within_2pp(arm_c_he, arm_b_he)
    mbpp_within = within_2pp(arm_c_mbpp, arm_b_mbpp)

    if pass_init == "FAIL":
        verdict = "FAIL — init agreement broke the patch"
    elif he_within is None or mbpp_within is None:
        verdict = "INCOMPLETE — missing arm result"
    elif he_within and mbpp_within:
        verdict = "PASS — morphism Variant A within ±2pp of LoRA control on HE+MBPP"
    elif he_within or mbpp_within:
        verdict = "MIXED — within tolerance on one benchmark, not the other"
    else:
        verdict = "FAIL — morphism regresses vs LoRA control by >2pp on both"

    summary = {
        "ts": dt.datetime.utcnow().isoformat(),
        "report": "morphism_0p5b_variant_a",
        "init_agreement_mean": init_agree,
        "init_check_pass": pass_init,
        "rows": rows,
        "training": {
            "morphism": {
                "wall_seconds": morph_wall,
                "trainable_params_M": morph_trainable,
                "cost_usd_estimate": morph_cost,
            },
            "lora_control": {
                "wall_seconds": lora_wall,
                "trainable_params_M": lora_trainable,
                "cost_usd_estimate": lora_cost,
            },
        },
        "verdict": verdict,
        "decision_refs": ["slm-learning-103", "slm-learning-130",
                          "slm-learning-165", "slm-learning-169"],
    }

    md = []
    md.append("# Morphism Variant A on Qwen2.5-Coder-0.5B-Instruct")
    md.append("")
    md.append(f"**Date:** {dt.date.today().isoformat()}")
    md.append("**Owner:** Dr. Stein")
    md.append("**Charter arm:** Arm 2 of `reports/research/scaling_proof_charter.md`")
    md.append("**Decision refs:** slm-learning-103, slm-learning-130, "
              "slm-learning-165, slm-learning-169")
    md.append("")
    md.append(f"## Verdict: **{verdict}**")
    md.append("")
    md.append("## Init agreement check")
    md.append("")
    md.append(f"Mean token agreement (greedy decode, n=8 prompts, max_new=16): "
              f"**{init_agree:.4f}**" if init_agree is not None
              else "Mean agreement: not recorded.")
    md.append(f"Threshold: 0.99. Verdict: **{pass_init}**")
    md.append("")
    md.append("## Eval rows")
    md.append("")
    md.append("| Arm | HE pass@1 | HE Δ vs base | MBPP pass@1 | MBPP Δ vs base |")
    md.append("|---|---|---|---|---|")
    for r in rows:
        he_delta = (fmt_delta(r["he_score"], rows[0]["he_score"])
                    if r is not rows[0] else "—")
        mbpp_delta = (fmt_delta(r["mbpp_score"], rows[0]["mbpp_score"])
                      if r is not rows[0] else "—")
        md.append(f"| {r['label']} | {fmt_pct(r['he_score'])}"
                  f" ({r['he_passed'] or 0}/{r['he_n'] or 0}) | {he_delta}"
                  f" | {fmt_pct(r['mbpp_score'])}"
                  f" ({r['mbpp_passed'] or 0}/{r['mbpp_n'] or 0}) | {mbpp_delta} |")
    md.append("")
    md.append("## Training cost / wall / params")
    md.append("")
    md.append("| Arm | Wall (s) | Trainable params (M) | Cost USD est. |")
    md.append("|---|---|---|---|")
    md.append(f"| LoRA r=16 (Arm B) | {lora_wall or 'n/a'} | "
              f"{lora_trainable or 'n/a'} | "
              f"${lora_cost if lora_cost is not None else 'n/a'} |")
    md.append(f"| Morphism Variant A (Arm C) | {morph_wall or 'n/a'} | "
              f"{morph_trainable or 'n/a'} | "
              f"${morph_cost if morph_cost is not None else 'n/a'} |")
    md.append("")
    md.append("## Charter Arm-2 pass criteria")
    md.append("")
    md.append(f"- Init agreement = 100% on 8 prompts: **{pass_init}**")
    md.append(f"- Post-train HE within ±2pp of LoRA control: "
              f"**{'YES' if he_within else 'NO' if he_within is False else 'n/a'}**")
    md.append(f"- Post-train MBPP within ±2pp of LoRA control: "
              f"**{'YES' if mbpp_within else 'NO' if mbpp_within is False else 'n/a'}**")
    md.append("")

    return "\n".join(md), summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diag-dir", default=str(REPO_ROOT / "tmp" / "diag-2026-05-08"))
    ap.add_argument("--manifest-morph",
                    default="C:/Users/benja/Documents/slm_learning/tmp/morphism-0p5b-variant-a-MANIFEST.json")
    ap.add_argument("--manifest-lora",
                    default="C:/Users/benja/Documents/slm_learning/tmp/morphism-0p5b-lora-control-MANIFEST.json")
    ap.add_argument("--out-md",
                    default=str(REPO_ROOT / "reports" / "evals" /
                                "morphism_0p5b_variant_a_2026-05-08.md"))
    ap.add_argument("--out-json",
                    default=str(REPO_ROOT / "reports" / "evals" /
                                "morphism_0p5b_variant_a_2026-05-08.json"))
    args = ap.parse_args()

    diag = Path(args.diag_dir)
    base_he = load_json(diag / "base_he_0p5b_full.json")
    base_mbpp = load_json(diag / "base_mbpp_0p5b_full.json")
    lora_he = load_json(diag / "lora_0p5b_he_full.json")
    lora_mbpp = load_json(diag / "lora_0p5b_mbpp_full.json")
    morph_he = load_json(diag / "morphism_0p5b_he_full.json")
    morph_mbpp = load_json(diag / "morphism_0p5b_mbpp_full.json")
    manifest_lora = load_json(Path(args.manifest_lora))
    manifest_morph = load_json(Path(args.manifest_morph))

    md, summary = render(args, base_he, base_mbpp, lora_he, lora_mbpp,
                          morph_he, morph_mbpp, manifest_lora, manifest_morph)
    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md, encoding="utf-8")
    Path(args.out_json).write_text(json.dumps(summary, indent=2),
                                    encoding="utf-8")
    print(f"[aggregate] wrote {out_md}")
    print(f"[aggregate] wrote {args.out_json}")
    print(f"[aggregate] verdict: {summary['verdict']}")


if __name__ == "__main__":
    main()
