# Scaling-ladder extension plan — 14B / 32B / 80B-A3B base evals

**Date:** 2026-05-09
**Owner:** Dr. Stein (slm-learning)
**Decision refs:** slm-learning-097, 100, 103, 105, 197, 202, 207, 210
**Spec sources:** `experiments/configs/scaling_ladder/{14b,32b,80b-a3b}_base_eval.json`
**Status:** plan-only, not authorized to fire

## 1. Goal

Measure unmodified base capability at **14B**, **32B**, and **Qwen3-Next-80B-A3B**
on HumanEval (n=164) + MBPP (n=164) + gad_tools (owned-domain) before
any training spend is authorized at those sizes. The current ladder
(`1.5B → 3B → 7B`) saturates at 7B Stein canonical (HE 84.8 / MBPP 82.3).
Operator pushed back on capping at 7B per slm-learning-210 — extending
the ladder is required to honestly answer "where is the quality knee?"

## 2. Why now

- **3B regression closure (slm-learning-202).** The 3B + LoRA r=16 +
  retain-ratio sweep falsified across 15/85, 50/50, 70/30 — every arm
  regressed on HE. That was a *recipe* failure, not a *base* failure;
  3B base scores 83.5 / 73.2.
- **Operator push (slm-learning-210).** "We are building novel shit."
  Honest scaling requires base rungs at 14B/32B/80B-A3B, not assumed.
- **Charter Row 1 + 2 obligation (slm-learning-103).** Compare-and-
  compete demands public-leaderboard + frontier-comparator rows on
  every promotion candidate. Adding rungs without base-row data is
  vibes, not research.

## 3. Hardware + cost table

| Rung | Base model | BF16 VRAM | GPU (Modal) | Cost/run | Wall (HE+MBPP+gad_tools) |
|---|---|---|---|---|---|
| 14B | Qwen2.5-Coder-14B-Instruct | ~32 GB | A100 (80GB) | ~$2 | ~35 min |
| 32B | Qwen2.5-Coder-32B-Instruct | ~70 GB | A100 (80GB) | ~$4 | ~60 min |
| 80B-A3B | Qwen3-Next-80B-A3B-Instruct | ~180 GB | H100 | ~$8 | ~75 min |
| **Total** | | | | **~$14** | ~3 hr serial |

(Modal pricing assumed at ~$3/hr A100-80GB, ~$4-5/hr H100. Reconfirm
before fire.)

INT4 for 14B fits A10G (~12 GB) at ~$0.50/run, but introduces a quant
skew that breaks the comparison. **Reject INT4 for the ladder rows.**
INT4 is the operator-emergency fallback only.

## 4. Predicted curves (priors, not promises)

The Qwen team's published scores for Qwen2.5-Coder family on HumanEval
(pass@1, paper) anchor the priors below. **These are public-card
predictions, not measurements.** Real base scores can differ by ±5pp
when run under our chat-mode harness vs the upstream completion harness.

| Rung | Predicted HE pass@1 | Predicted MBPP pass@1 | Source |
|---|---|---|---|
| 1.5B base | ~70.1 | ~69.3 | Qwen2.5-Coder model card |
| 3B base | 83.5 (measured) | 73.2 (measured) | slm-learning local eval |
| 7B base (no LoRA) | ~88.4 | ~76.8 | Qwen2.5-Coder model card |
| 7B Stein canonical | **84.8** | **82.3** | slm-learning local (LoRA-lifted) |
| 14B base | ~89.6 | ~82.3 | Qwen2.5-Coder model card (cross-check needed) |
| 32B base | ~92.7 | ~83.5 | Qwen2.5-Coder model card (cross-check needed) |
| 80B-A3B base | unmeasured upstream on HE | unmeasured upstream on MBPP | flag — Qwen3-Next has no published HE pass@1 in same harness |

**Predicted shape:** diminishing returns on HE between 14B and 32B
(+3pp), and unknown above 32B. MBPP is likely flat from 14B onward —
public Qwen cards suggest MBPP saturates earlier than HE. The 80B-A3B
row is the open-research one; we do not assume it beats 32B-dense on
HE because MoE active-param cost (3.9B) is a different curve than
total-param cost.

**Cost-per-Mtok caveat:** these are open weights, so cost is dominated
by hosting (Modal hourly). Compared to Opus ($5/$25 per Mtok in/out),
even 32B BF16 on H100 at ~$5/hr is meaningfully cheaper if Kael's
serving tier amortizes the load. The cost row only moves the needle
when we own the inference, not just the training.

## 5. Pass / fail criteria — knee detection

A rung is the **new training target** if:

1. HE pass@1 ≥ 7B Stein +2pp (>= 0.870), AND
2. MBPP pass@1 ≥ 7B Stein +2pp (>= 0.840), AND
3. gad_tools owned-domain delta vs 7B Stein ≥ 0 (no regression on the
   moat), AND
4. inference cost-per-successful-task ≤ 1/4 of Opus on the owned-
   domain row.

A rung is **rejected** if HE delta vs the next-smaller measured rung
is < +1pp (14B) / < +2pp (32B, 80B-A3B). No clear lift = not worth
the training spend.

The smallest passing rung wins. If no rung passes, the recommendation
is: **stay at 7B Stein canonical, refine recipe, don't burn $50 on a
larger rung that doesn't move the moat.**

## 6. Comparator-row design (slm-learning-103 alignment)

| Charter Row | Filled by base evals? | Notes |
|---|---|---|
| Row 1 — public leaderboard | Yes (HE + MBPP n=164) | LiveCodeBench is a follow-on, not in this fire |
| Row 2 — frontier comparator | Partial — base subset only | Pair with `claude-cli` + Big Pickle + OpenRouter free-tier rows already on file |
| Row 3 — owned-domain | Partial (gad_tools only) | doc-verifier + tooluse follow if a rung is promoted to training target |
| Row 4 — lineage | Not yet | Lineage is filled when a TRAINED adapter exists; base evals are pre-lineage data |

Per slm-learning-103, base evals **do not promote a candidate** on
their own. They populate the pre-flight comparator that decides
whether training spend is justified at the larger size.

## 7. Decision tree after base evals

```
14B base measured + 32B base measured + 80B-A3B base measured
  |
  +-- if 14B passes knee criteria
  |     -> train at 14B (recipe TBD; do NOT reuse 3B-failed LoRA recipe)
  |     -> stop ladder, 14B is the new workhorse target
  |
  +-- elif 32B passes knee criteria
  |     -> train at 32B if budget allows OR escalate to BTM/SERA
  |     -> 14B not promoted (no lift)
  |
  +-- elif 80B-A3B passes knee criteria AND active-param latency holds
  |     -> bulk_labeler + comparator role only (per teacher_species_policy.md)
  |     -> NOT a Kael backbone candidate (deployment cost too high)
  |
  +-- else (no rung passes)
        -> 7B Stein canonical remains the target
        -> log negative result; do not fire training above 7B
```

## 8. Risks

- **Quant skew.** INT4 fallback would break the comparison; rejected
  except as last resort. If A100-80GB capacity is constrained, defer
  the rung — don't degrade the measurement.
- **H100 availability on Modal.** Bursty. The 80B-A3B fire may need
  to wait for capacity; do not let it block the 14B + 32B fires.
- **Eval-set leakage.** HE + MBPP have known leakage at the 32B+ scale
  for code-tuned bases. Treat HE/MBPP scores at 32B and above as a
  *floor*, not a *ceiling*. Pair with LiveCodeBench (post-2024 problems)
  before promoting any rung.
- **Architecture support.** Qwen3-Next-80B-A3B is hybrid Transformer-
  Mamba MoE; verify the Modal eval image's `transformers>=4.50` pin
  actually loads the architecture before firing or burn $8 finding out.
- **Disk on slm-models volume.** 80B-A3B BF16 weights are ~160 GB.
  Confirm volume free space before kicking the download.

## 9. Two-shot $50 discipline alignment (slm-learning-097)

These are **pre-flight comparator** evals, not training shots. They
do NOT trigger the $50 ladder by themselves. The total ~$14 base-eval
spend is bounded and decision-shaped — its purpose is to inform
whether a $50 training shot at a larger size is justified.

If all three rungs pass the knee criteria, the decision-ready output
is: "fire the next training shot at the smallest passing rung; budget
$50 with the holdout-gate threshold written before training."

If no rung passes: log the negative result, stay at 7B, and the
training $50 stays unspent.

## 10. Cost ledger row format

```
| Date | Rung | GPU | Wall (min) | Cost | HE n=164 | MBPP n=164 | gad_tools | Knee? |
|---|---|---|---|---|---|---|---|---|
| 2026-05-?? | 14B base | A100 | 35 | $2.00 | ?? | ?? | ?? | tbd |
| 2026-05-?? | 32B base | A100 | 60 | $4.00 | ?? | ?? | ?? | tbd |
| 2026-05-?? | 80B-A3B base | H100 | 75 | $8.00 | ?? | ?? | ?? | tbd |
```

Append to `experiments/INDEX.md` after fire, with persist_run_id and
the raw eval JSON path on the slm-models volume.

## 11. Fire-readiness checklist (operator authorization)

Before Dr. Stein authorizes the spend:

- [ ] Modal A100-80GB pricing reconfirmed (drift since 2026-05)
- [ ] Modal H100 capacity verified live (bursty)
- [ ] slm-models volume free space ≥ 250 GB (covers 14B + 32B + 80B-A3B downloads)
- [ ] `modal_app/eval_adapter.py` confirmed to handle `--gpu A100` and `--gpu H100` (currently has score_l4/score_a10g/score_a100; H100 routing may need a `score_h100` function added before fire)
- [ ] `transformers` pin in eval image verified to load Qwen3-Next-80B-A3B-Instruct (hybrid Transformer-Mamba MoE)
- [ ] Holdout-gate thresholds for each rung written into `data/registry/scaling_ladder_gates.json` (does not yet exist; create before fire)
- [ ] Aggregator dry-run on existing 1.5B/3B/7B eval JSONs returns sane numbers
- [ ] `MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8` prefix included in fire commands per CLAUDE.md Windows gotcha

— Dr. Stein, scaling-ladder extension plan, 2026-05-09
