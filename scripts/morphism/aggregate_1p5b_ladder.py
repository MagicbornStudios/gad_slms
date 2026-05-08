"""Aggregate 1.5B ladder eval results into reports/evals/morphism_1p5b_ladder_2026-05-08.md.

Per slm-learning-172: 4-arm ladder at 1.5B testing whether the 0.5B
falsification was capacity-driven, dataset-shape-driven, or
architecture-driven.

Inputs (local pulls from slm-models volume after eval runs):
  Arm 0: tmp/diag-2026-05-08/base_he_1p5b_full.json + base_mbpp_1p5b_full.json
  Arm 1 (LoRA hard): tmp/diag-2026-05-08/lora_1p5b_hard_he.json + _mbpp.json
  Arm 2 (LoRA hard+retain): tmp/diag-2026-05-08/lora_1p5b_hard_retain_he.json + _mbpp.json
  Arm 3 (Morphism A hard): tmp/diag-2026-05-08/morphism_a_1p5b_hard_he.json + _mbpp.json
  Arm 4 (Morphism B hard): tmp/diag-2026-05-08/morphism_b_1p5b_hard_he.json + _mbpp.json

Manifest inputs (training metadata):
  tmp/lora_1p5b_hard_MANIFEST.json
  tmp/lora_1p5b_hard_retain_MANIFEST.json
  tmp/morphism_a_1p5b_hard_MANIFEST.json
  tmp/morphism_b_1p5b_hard_MANIFEST.json

Outputs:
  reports/evals/morphism_1p5b_ladder_2026-05-08.md
  reports/evals/morphism_1p5b_ladder_2026-05-08.json
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
    except Exception as e:
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
    delta = (float(after) - float(before)) * 100
    arrow = "⬆" if delta > 0 else ("⬇" if delta < 0 else "—")
    return f"{delta:+.1f}pp {arrow}"


def cost_estimate(manifest: dict | None) -> float | None:
    if not manifest:
        return None
    target = (manifest.get("compute_target", "") or "").lower()
    wall_sec = manifest.get("wall_seconds") or 0
    rate = {
        "modal-a10g": 0.83,
        "modal-l4": 0.55,
        "modal-a100": 4.0,
        "modal-a100-40gb": 4.0,
        "modal-a100-80gb": 6.0,
    }.get(target, 1.0)
    return round(rate * (wall_sec / 3600), 4)


def build_arm_row(label: str, he: dict | None, mbpp: dict | None,
                   manifest: dict | None) -> dict:
    return {
        "label": label,
        "he_score": (he or {}).get("score"),
        "he_passed": (he or {}).get("passed"),
        "he_n": (he or {}).get("n"),
        "mbpp_score": (mbpp or {}).get("score"),
        "mbpp_passed": (mbpp or {}).get("passed"),
        "mbpp_n": (mbpp or {}).get("n"),
        "trainable_params_M": (manifest or {}).get("trainable_params_M"),
        "wall_seconds": (manifest or {}).get("wall_seconds"),
        "training_loss": (manifest or {}).get("training_loss"),
        "cost_usd_estimate": cost_estimate(manifest),
        "init_agreement": (manifest or {}).get("morphism", {}).get(
            "init_agreement_mean") if manifest else None,
        "n_train_rows": (manifest or {}).get("n_train_rows"),
    }


def render(rows: list[dict], summary: dict) -> str:
    base = rows[0]

    md = []
    md.append("# 1.5B Ladder: 4-arm fine-tuning under base-failure data")
    md.append("")
    md.append(f"**Date:** 2026-05-08")
    md.append("**Owner:** Dr. Stein")
    md.append("**Charter:** `reports/research/scaling_proof_charter.md`")
    md.append("**Decision refs:** slm-learning-126, slm-learning-130, "
              "slm-learning-158, slm-learning-165, slm-learning-170, "
              "slm-learning-171, slm-learning-172")
    md.append("")
    md.append(f"## Verdict: **{summary['verdict']}**")
    md.append("")
    md.append("## Eval rows")
    md.append("")
    md.append("| Arm | HE pass@1 | HE Δ vs base | MBPP pass@1 | MBPP Δ vs base |")
    md.append("|---|---|---|---|---|")
    for r in rows:
        is_base = r is base
        he_delta = "—" if is_base else fmt_delta(r["he_score"], base["he_score"])
        mbpp_delta = "—" if is_base else fmt_delta(r["mbpp_score"], base["mbpp_score"])
        md.append(f"| {r['label']} | {fmt_pct(r['he_score'])}"
                  f" ({r['he_passed'] or 0}/{r['he_n'] or 0}) | {he_delta}"
                  f" | {fmt_pct(r['mbpp_score'])}"
                  f" ({r['mbpp_passed'] or 0}/{r['mbpp_n'] or 0}) | {mbpp_delta} |")

    md.append("")
    md.append("## Training cost / wall / params / init")
    md.append("")
    md.append("| Arm | Wall (s) | Loss | Trainable (M) | Init agree | Cost USD est. | n_train |")
    md.append("|---|---|---|---|---|---|---|")
    for r in rows[1:]:  # skip base (no training)
        md.append(f"| {r['label']} | {r['wall_seconds'] or 'n/a'}"
                  f" | {r['training_loss'] or 'n/a':.4f}"
                  f" | {r['trainable_params_M'] or 'n/a'}"
                  f" | {r['init_agreement'] if r['init_agreement'] is not None else 'n/a'}"
                  f" | ${r['cost_usd_estimate'] or 'n/a'}"
                  f" | {r['n_train_rows'] or 'n/a'} |")

    md.append("")
    md.append("## Cross-scale matrix (gap-targeted recipe)")
    md.append("")
    md.append("| Base | Mechanism | Dataset | HE Δ | MBPP Δ | Verdict |")
    md.append("|---|---|---|---|---|---|")
    md.append("| 7B | LoRA r=16 (lr=2e-4, 3 ep) | 7B-hard 58 rows | **+3.1** ⬆ | **+1.8** ⬆ | LIFT (slm-learning-130) |")
    md.append("| 0.5B | LoRA r=16 (lr=2e-4, 3 ep) | 0.5B-hard 73 rows | -32.9 ⬇ | -9.1 ⬇ | catastrophic regress (slm-learning-170) |")
    md.append("| 0.5B | Morphism A (lr=2e-4) | 0.5B-hard 73 rows | -28.1 ⬇ | -14.0 ⬇ | catastrophic regress (slm-learning-170) |")
    md.append("| 0.5B | Morphism A (lr=5e-5) | 0.5B-hard 73 rows | -43.9 ⬇⬇ | -10.3 ⬇ | worse on HE (slm-learning-171) |")
    he_lora = rows[1]["he_score"]
    he_lora_retain = rows[2]["he_score"]
    he_morph_a = rows[3]["he_score"]
    he_morph_b = rows[4]["he_score"]
    mb_lora = rows[1]["mbpp_score"]
    mb_lora_retain = rows[2]["mbpp_score"]
    mb_morph_a = rows[3]["mbpp_score"]
    mb_morph_b = rows[4]["mbpp_score"]
    he_base = base["he_score"]
    mb_base = base["mbpp_score"]

    def d(a, b):
        return f"{(a-b)*100:+.1f}" if a is not None and b is not None else "n/a"

    md.append(f"| **1.5B** | **LoRA r=16 hard 74 rows** | 1.5B-hard 74 rows | **{d(he_lora, he_base)}** | **{d(mb_lora, mb_base)}** | this run |")
    md.append(f"| **1.5B** | **LoRA r=16 hard+retain 164 rows** | 1.5B retain-mix 30/70 | **{d(he_lora_retain, he_base)}** | **{d(mb_lora_retain, mb_base)}** | this run |")
    md.append(f"| **1.5B** | **Morphism A (identity proj.)** | 1.5B-hard 74 rows | **{d(he_morph_a, he_base)}** | **{d(mb_morph_a, mb_base)}** | this run |")
    md.append(f"| **1.5B** | **Morphism B (gated bottleneck)** | 1.5B-hard 74 rows | **{d(he_morph_b, he_base)}** | **{d(mb_morph_b, mb_base)}** | this run |")

    md.append("")
    md.append("## What this proves / falsifies")
    md.append("")
    md.append(summary.get("interpretation", ""))

    return "\n".join(md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diag-dir", default=str(REPO_ROOT / "tmp" / "diag-2026-05-08"))
    ap.add_argument("--manifest-dir", default=str(REPO_ROOT / "tmp"))
    ap.add_argument("--out-md",
                    default=str(REPO_ROOT / "reports" / "evals" /
                                "morphism_1p5b_ladder_2026-05-08.md"))
    ap.add_argument("--out-json",
                    default=str(REPO_ROOT / "reports" / "evals" /
                                "morphism_1p5b_ladder_2026-05-08.json"))
    args = ap.parse_args()

    diag = Path(args.diag_dir)
    mdir = Path(args.manifest_dir)
    base_he = load_json(diag / "base_he_1p5b_full.json")
    base_mbpp = load_json(diag / "base_mbpp_1p5b_full.json")
    lora_h_he = load_json(diag / "lora_1p5b_hard_he.json")
    lora_h_mbpp = load_json(diag / "lora_1p5b_hard_mbpp.json")
    lora_hr_he = load_json(diag / "lora_1p5b_hard_retain_he.json")
    lora_hr_mbpp = load_json(diag / "lora_1p5b_hard_retain_mbpp.json")
    morph_a_he = load_json(diag / "morphism_a_1p5b_hard_he.json")
    morph_a_mbpp = load_json(diag / "morphism_a_1p5b_hard_mbpp.json")
    morph_b_he = load_json(diag / "morphism_b_1p5b_hard_he.json")
    morph_b_mbpp = load_json(diag / "morphism_b_1p5b_hard_mbpp.json")

    m_lora_h = load_json(mdir / "lora_1p5b_hard_MANIFEST.json")
    m_lora_hr = load_json(mdir / "lora_1p5b_hard_retain_MANIFEST.json")
    m_morph_a = load_json(mdir / "morphism_a_1p5b_hard_MANIFEST.json")
    m_morph_b = load_json(mdir / "morphism_b_1p5b_hard_MANIFEST.json")

    rows = [
        build_arm_row("1.5B base", base_he, base_mbpp, None),
        build_arm_row("1.5B + LoRA r=16 hard (74)", lora_h_he, lora_h_mbpp, m_lora_h),
        build_arm_row("1.5B + LoRA r=16 hard+retain (164)", lora_hr_he, lora_hr_mbpp, m_lora_hr),
        build_arm_row("1.5B + Morphism A hard (74)", morph_a_he, morph_a_mbpp, m_morph_a),
        build_arm_row("1.5B + Morphism B hard (74)", morph_b_he, morph_b_mbpp, m_morph_b),
    ]

    base = rows[0]
    he_base = base["he_score"]
    mb_base = base["mbpp_score"]

    # Verdict
    any_lift = False
    any_regress = False
    interpretation_lines = []
    for r in rows[1:]:
        if r["he_score"] is None or r["mbpp_score"] is None:
            continue
        he_delta = (r["he_score"] - he_base) * 100
        mb_delta = (r["mbpp_score"] - mb_base) * 100
        if he_delta > 1 or mb_delta > 1:
            any_lift = True
        if he_delta < -2 or mb_delta < -2:
            any_regress = True

    if any_lift and not any_regress:
        verdict = "LIFT — at least one arm beats base on HE or MBPP without major regressions"
    elif any_lift:
        verdict = "MIXED — at least one arm lifts but at least one regresses; arm-by-arm story"
    elif any_regress:
        verdict = "REGRESS — no arm clears base; capacity floor still above 1.5B for this dataset shape"
    else:
        verdict = "NEUTRAL — no arm changed scores meaningfully"

    # Compose interpretation
    best_arm = max(rows[1:], key=lambda r: (r["he_score"] or 0) +
                                            (r["mbpp_score"] or 0))
    interpretation_lines.append(
        f"**Best arm by combined HE+MBPP**: {best_arm['label']} "
        f"(HE {fmt_pct(best_arm['he_score'])}, MBPP {fmt_pct(best_arm['mbpp_score'])})."
    )
    if any_lift:
        interpretation_lines.append(
            "At least one arm beat the bare 1.5B base — the 0.5B "
            "falsification did not generalize. Capacity matters."
        )
    if any_regress:
        interpretation_lines.append(
            "At least one arm regressed vs base. Recipe is still not "
            "universally safe at 1.5B; specific arm choice matters."
        )

    summary = {
        "ts": dt.datetime.utcnow().isoformat() + "Z",
        "report": "morphism_1p5b_ladder",
        "rows": rows,
        "verdict": verdict,
        "interpretation": "\n\n".join(interpretation_lines),
        "decision_refs": ["slm-learning-126", "slm-learning-130",
                          "slm-learning-158", "slm-learning-165",
                          "slm-learning-170", "slm-learning-171",
                          "slm-learning-172"],
    }

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render(rows, summary), encoding="utf-8")
    Path(args.out_json).write_text(json.dumps(summary, indent=2),
                                    encoding="utf-8")
    print(f"[aggregate] wrote {out_md}")
    print(f"[aggregate] wrote {args.out_json}")
    print(f"[aggregate] verdict: {verdict}")


if __name__ == "__main__":
    main()
