# Big-Run Cost Plan — first big-base experiment

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Decision refs:** slm-learning-097, 100, 103, 105, 188, 197, 199, 207,
208, 210, 213
**Companion docs:** `reports/research/big_base_replacement_track.md`,
`benchmarks/frontier_open_replacement_matrix.yaml`,
`schemas/replacement_eval_trace.schema.json`

This plan operationalizes Phase 3 of the Big-Base Replacement Track —
the first big-base LoRA SFT experiment — within the $100-300 budget
envelope authorized by slm-learning-213.

## 1. Budget envelope

| Item | Value |
|---|---|
| Authorized envelope (slm-learning-213) | $100 - $300 |
| Recommended first-fire target | ≤ $150 |
| Hard cap | $300 |
| Abort threshold | 50% over plan ($225 if Candidate B; $120 if Candidate A) |
| Charter alignment (slm-learning-097) | "first big-base" — second fire authorized only if first clears Phase 3 gates |

The envelope covers data prep + LoRA SFT compute + replacement-matrix
eval + comparator costs. It does **not** cover Phase 4 (DPO/GRPO),
which is a separate budget ask gated on Gateway production data
(slm-learning-208).

## 2. Phase 3 cost breakdown

| Line | Detail | Cost |
|---|---|---|
| Data prep | Operator-side traces + existing Kael-house corpus + GAD delta packets — already exist | $0 |
| Teacher correction pass | Opus over remaining 50-150 unlabeled rows (Kael packets + GAD trace overflow); avg ~3K tokens in / 1K tokens out per row at $5/$25 per Mtok = ~$0.04/row × 150 rows | $5 - $30 |
| LoRA SFT compute (Candidate A — Modal A100 BF16 on 32B) | ~30M tokens × 3 epochs at A100 throughput; ~10-20 hr A100-80GB at $2/hr | $30 - $60 |
| LoRA SFT compute (Candidate B — Together hosted on Qwen3-Coder-Next 80B-A3B) | Together LoRA SFT pricing for 70-100B class: $2.90/Mtok input. 30M tokens = $87 | ~$90 |
| Replacement matrix eval | Per `benchmarks/frontier_open_replacement_matrix.yaml` cost_containment block: bounded at $30 across pending cells | $10 - $30 |
| Comparator (Opus calls in the matrix) | Capped row count; ~15 owned-domain rows × $0.40 each + ~5 SWE rows × $4 each = $26 | ~$25 |
| Buffer | 20% safety margin on training | $20 - $40 |
| **Total Candidate A** | | **$55 - $100** |
| **Total Candidate B** | | **$105 - $150** |

Both candidates fit the envelope. Candidate A leaves headroom for
a second Phase 3 fire within budget if the first regresses on a
specific task family.

## 3. Two recommended candidates

### Candidate A — 32B LoRA SFT via Modal

- **Body:** `Qwen/Qwen2.5-Coder-32B-Instruct` (Apache-2.0)
- **Compute:** Modal A100-80GB BF16, ~10-20 hr at $2/hr
- **Recipe:** LoRA r=32, target_modules `[q_proj, v_proj, k_proj, o_proj]`
  (attention only — based on slm-learning-202 hypothesis that MLP
  changes destroy reasoning at smaller scales), lr=1e-4, 3 epochs,
  warmup 100 steps
- **Data:** ~30M tokens of Kael-house corrections + GAD delta packets
  + Opus teacher labels with `accepted_by: verifier` provenance per
  `schemas/teacher_policy.schema.json` §6
- **Cost:** $55 - $100 total
- **Pro:** Fully owned (Modal volume); we can quantize for serving
  later; same family as Stein-house 7B canonical for adapter portability.
- **Con:** Lower effective capacity than 80B-A3B; we don't get the
  256K context advantage; serving cost is GPU-hours not API tokens.

### Candidate B — Qwen3-Coder-Next 80B-A3B LoRA SFT via Together

- **Body:** `Qwen3-Coder-Next-80B-A3B` (Apache-2.0; 3B active per token)
- **Compute:** Together hosted LoRA SFT at $2.90/Mtok input
- **Recipe:** Together's default LoRA recipe (r=16, target_modules
  attention + MLP per their hosted defaults), lr=1e-4, 3 epochs
- **Data:** Same 30M-token corpus as Candidate A
- **Cost:** $105 - $150 total
- **Pro:** Strongest published owned-domain potential — 74.2% SWE-bench
  Verified with SWE-Agent (Qwen team release notes; verify); 256K
  context fits multi-file repo packs natively; 3B active per token
  means inference cost-per-call is competitive with 7B.
- **Con:** Adapter lives at Together — to self-host we'd need to
  pull the LoRA weights and run our own vLLM with the 80B-A3B body
  on H100; that's a separate ~$8/eval cost and capacity dependent;
  recipe is opaque (their hosted defaults, not ours).

## 4. Pre-fire gates

Per slm-learning-097, this fire does NOT proceed without ALL of:

1. **Phase 1 base evals complete.** All three rungs in
   `data/registry/scaling_ladder_gates.json` have landed (or formally
   absent rungs are documented). The smallest-passing rung informs
   whether Candidate A's body should stay at 32B or shift to 14B.
2. **Clean SFT corpus exists.** ≥200 high-quality rows with
   `accepted_by` metadata present. Concretely:
   - ≥100 Kael-house correction rows (slm-learning-167)
   - ≥50 GAD-tools owned-domain repair rows
   - ≥50 Opus-labeled novel-research synthesis rows (Tier 3)
   - All rows pass `schemas/teacher_policy.schema.json` §6 contract
3. **Holdout-gate thresholds pre-registered.** New file
   `data/registry/big_base_phase3_gates.json` with the same shape as
   `scaling_ladder_gates.json` — gates on humaneval, mbpp, gad_tools,
   bfcl_tool_action, kael_code_task — frozen before training.
   Threshold list anchored to
   `benchmarks/frontier_open_replacement_matrix.yaml` cells.
4. **Operator authorization for the specific candidate.** Operator
   chooses A or B explicitly before fire. Default recommendation is A
   (cheaper, lets us do a second Phase 3 fire within envelope if
   needed).
5. **Modal/Together pricing reconfirmed.** Drift in Modal A100 or
   Together $/Mtok within ±20% of the line items above. Larger drift
   pauses the fire for re-spec.

## 5. Failure modes + cost containment

| Failure | Detection | Action | Sunk cost |
|---|---|---|---|
| LoRA SFT regresses base on epoch-1 holdout | mid-training holdout eval at epoch 1 boundary | abort training; preserve adapter checkpoint; recipe diagnostic | ~$30 (Candidate A) / ~$45 (Candidate B) |
| Regresses base only on owned-domain row | epoch-3 final eval on `gad_tools` cell | rule out that recipe + dataset combo for owned-domain; consider data balance change | full Phase 3 fire cost |
| Together API outage / rate limit (Candidate B only) | live monitoring during training | fallback to Modal-direct H100 with the same adapter recipe; this adds ~$25-40 cost | none if caught early |
| Eval comparator (Opus) over budget | row-budget tracked per matrix run | cap eval row count at the cost-containment block (`$30`); drop low-priority cells | bounded by matrix cost cap |
| Data corpus contamination (Opus rows leak HumanEval/MBPP solutions) | pre-fire dedup pass against eval datasets | contaminated rows REMOVED before training; if discovered post-fire, the resulting candidate is flagged tainted and not promoted | full fire cost — quarantine candidate, don't promote |

The hardest containment line is **abort within first 3 epochs**.
Candidate A allows abort at ~$30 sunk; Candidate B at ~$45. Both are
recoverable within the $300 hard cap.

## 6. Success ledger format

On Phase 3 success, append a row to
`experiments/INDEX.md` and create:

- `data/registry/deltas/<delta_id>.json` per `schemas/delta_packet.schema.json`-adjacent
  registry shape (the delta-graph node per slm-learning-100), with:
  - `delta_id`, `base`, `parents[]`, `dataset`, `rank`, `merge_method:
    lora_sft`, `training_method`, `evals.public`, `evals.private`,
    `cost_usd`, `wall_hours`, `compute_target`, `status: promoted`,
    `regression_journal_uri`, `outputs_corpus_uri`, `decision_refs`
- `data/processed/<run_id>/outputs_corpus.jsonl` — the 200-row outputs
  bank per slm-learning-096 ("3 reusable artifacts" rule)
- `data/processed/<run_id>/regression_journal.md` — what failed, even
  on a successful run; feeds Phase 4 corpus
- A row per matrix cell in
  `benchmarks/frontier_open_replacement_matrix.yaml`-shaped JSON that
  matches `schemas/replacement_eval_trace.schema.json`

On Phase 3 failure, the same artifacts are produced with `status:
failed_promotion`, the regression_journal carries the negative
finding, and the outputs corpus is retained for Phase 4 input.

Per slm-learning-096: lost training is structurally impossible.

## 7. Composition with slm-learning-097 (Two-shot $50)

slm-learning-097 reserves "training shots" (the proper SFT/DPO/RL
runs) at $50 ladder cost. Phase 3 here is a **big-base** run, not a
**big-training** run on the saturated 7B canonical recipe. The
relationship:

- **Two-shot $50 still applies** to subsequent fires at the SAME
  body (e.g. another LoRA SFT on 32B with a different recipe). Second
  shot only fires if first cleared a measurable gate.
- **Phase 3 first fire** is the entry to the larger budget envelope
  ($100-300). It's gated more strictly (4-rule pre-fire gate above)
  in exchange for the higher cost.
- **Subsequent Phase 3 fires** at 32B (e.g. recipe variants) reset to
  the $50 ladder discipline. Only the first big-base run gets the
  envelope-level budget. After that, scope-creeping training spend
  pauses for re-spec.

## 8. Dependency on Gateway (slm-learning-208)

Phase 4 (DPO/KTO/GRPO) cannot fire without Gateway producing
production traces. Specifically:

- Phase 4 needs ≥30 days of Gateway data with `accepted_by` rows.
- Preference pairs come from Gateway `inference_trace.schema.json`
  rows where the operator (or downstream verifier) flagged the
  initial Big-Base output as accepted vs the fallback-to-Opus output
  as rejected, OR vice versa.
- Together pricing for Qwen3-235B-A22B DPO is $15/Mtok; a 10M-token
  preference run is ~$150 — separate budget ask, NOT rolled into
  Phase 3.
- GRPO/RLVR fires only after the verifier loop (test-runner
  signal) is wired into Gateway. That's a wiring task, not a
  training task.

Until Gateway ships and accumulates data, Phase 4 is a placeholder
in the master plan, not a work item.

## 9. Open questions before Phase 3 fire

1. **Same-family teacher hypothesis.** Per
   `reports/research/teacher_species_policy.md` §4, the question of
   whether Qwen-32B teacher beats Opus teacher on Kael-7B student
   is unsettled. For Phase 3 we should NOT split the corpus across
   teachers in the first fire; use Opus exclusively (per
   slm-learning-197). The same-family arm becomes a separate
   experiment after Phase 3 lands.
2. **Adapter ownership for Candidate B.** Together hosts the LoRA
   weights; do we have license + portability to pull them onto Modal
   for self-serving? Verify before fire — if no, Candidate A is
   strictly preferred (we keep ownership of the artifact).
3. **Eval corpus completeness.** Several owned-domain corpora
   (`gad_tools-eval`, `kael-house-eval`, `gad-decisions-eval`) need
   row-count audits before fire. Bottom line: a $100 SFT against an
   un-audited eval is a vibe, not a measurement.

## 10. Recommendation

**Fire Candidate A first.** $55-100 total. Same-family with Stein
canonical + Kael body. Adapter ownership stays with us. Leaves $50+
in the envelope for a second Phase 3 fire if needed (e.g. recipe
adjustment after a partial regression on owned-domain). If Candidate
A clears the Phase 3 gates strongly, Candidate B becomes a follow-on
experiment in the next budget ask, NOT an alternative to A.

Operator authorization required at the four-gate checklist before
Modal/Together fire.

— Dr. Stein, big-run cost plan, 2026-05-08
