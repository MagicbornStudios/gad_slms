# Scaling Decisions — when params vs data vs training

## Status

`active`

## Owned by

Dr. Stein

## The question

When a model isn't good enough, is the bottleneck **parameters**,
**data**, or **training procedure**? Spend on the right axis.

This concern codifies the diagnostic flow + the empirical evidence
we have so far. Locks the answer in writing so future sessions don't
re-litigate.

## Diagnostic flow

Before increasing rank or pulling more data, ANSWER THESE in order:

| # | Question | If yes → axis is | Action |
|---|---|---|---|
| 1 | Does the model emit syntactically valid output (JSON parseable, command starts with `gad `, code compiles)? | **format learned, content not** | check axes 2-5; rank/data may help |
| 2 | Did adding more rank just lift one metric? | **PARAM was bottleneck** | scale rank again if more headroom; else go to data |
| 3 | Are some output classes/shapes never produced (e.g. unknown F1=0.000)? | **DATA imbalance** | augment minority class via haiku synthetic + per-class oversampling |
| 4 | Does the model produce wrong-but-plausible content (hallucinated functions, wrong API)? | **DATA out-of-distribution** | corpus needs the right shape; more rank won't fix |
| 5 | Does loss converge cleanly but holdout plateaus? | **DATA exhausted** | dedupe / augment / pull external corpus |
| 6 | Does loss not converge or oscillates? | **TRAINING** issue | LR / warmup / batch / epochs; not params or data |
| 7 | Is the eval set saturated (every adapter scores 100%)? | **EVAL** is the bottleneck | harder eval first, no more training until measurable |

## Empirical evidence from this session

| Run | What changed | Result | Axis confirmed |
|---|---|---|---|
| multi-task LoRA (r=16, 6572 mixed) vs v2 (r=16, 783 CLI) | combined corpora into one LoRA | catastrophic forgetting: GAD-tools 30/30 → 25/30, GSM8K 25/50 → 5/50 | **DATA shape** — cohort separation needed, not param |
| doc-verifier r=8 → r=16 | rank 8 → 16, same data | F1 0.533 → 0.720; **unknown F1 0.000 → 0.462** | **PARAM** unlocked 3rd-class boundary |
| doc-verifier r=16 at 0.720 (gate 0.85) | next experiment? | unknown F1=0.462 still weakest; only 70 unknown training examples (16% of 442) | **DATA imbalance** — augment unknown class first; r=32 likely diminishing returns |
| doc-verifier r=16 augmented (442→592, unknown 70→220) | deterministic fake-parent-prefix synthesis with single reason template | F1 **REGRESSED** 0.720 → 0.599; unknown F1 0.462 → **0.167** | **DATA imbalance hypothesis CONFIRMED, but FIX SHAPE was wrong** — uniform reason template caused overfit to template phrasing; model memorized the template as the unknown signal and missed real unknowns with varied reasons. See slm-learning-093. |
| HumanEval 0/10 across all adapters | trained on CLI/math/tool-use, no code | bare base also 0/10 | **DATA absence** — 233 code envelopes globally (audit-2026-05-07), no ladder of any rank fixes this |
| v2 CLI specialist (1.5B + 783 pairs) | proven 30/30 GAD-tools | gad_tools_v2 manifest marks eval SATURATED | **EVAL** is the bottleneck for further CLI work |

## Decision rules

Per `slm-learning-087` + this session's empirical evidence:

| Bottleneck | Symptom | Cheapest first move | Last resort |
|---|---|---|---|
| **PARAM** | one metric lifts when rank doubles, others flat; minority class binary at 0.000 → non-zero | r ×2 (8→16, 16→32) | base scale-up (1.5B → 3B → 7B) |
| **DATA imbalance** | some classes / task shapes never produced; F1 at 0.000 for one class while others are fine | augment minority class WITH SURFACE-FORM VARIANCE (haiku paraphrase REQUIRED — uniform templates regress, see slm-learning-093) | external corpus pull |
| **DATA absence** | bare base + every specialist scores ~0 on a benchmark | external corpus (starcoderdata, MultiPL-T, OpenMathInstruct) OR haiku synthesis at scale | accept that capability is out-of-scope; document gap |
| **DATA shape mismatch** | combined corpora regress vs separate specialists | per-cohort training + adapter stacking / TIES merge | abandon multi-task framing |
| **TRAINING** | loss oscillates / NaN / doesn't converge | LR sweep / warmup tweak / batch reduction | gradient checkpointing / different optimizer |
| **EVAL** | every candidate scores 100% on a suite | harder eval (n=164 HumanEval; full SWE-bench Verified) | new eval entirely |

## When to train BIGGER MODELS (1.5B → 3B → 7B → 14B → 20B)

Per `slm-learning-087`, scale only when:

1. r=32 (or r=64 if VRAM allows) STILL underfits the same shape, AND
2. The failure is **composition** not **formatting** (model emits valid output of the wrong logical shape), AND
3. We have content_type-tagged data per `slm-learning-079` so the bigger base sees the right cohort, AND
4. Held-out eval shows plateau over ≥2 rank-doublings, AND
5. The shape we're scaling for is one of our locked use cases per
   `slm-learning-054` (sprite/landing/marketing/PA) — NOT a generic
   "we wanted a bigger model"

If failure is bad data, no rank or scale fixes it (audit-2026-05-07).

## Specific guidance for current candidates

| Candidate | Bottleneck (per this session evidence) | Right next move |
|---|---|---|
| doc-verifier r=16 (0.720) | DATA imbalance — but augmentation must include SURFACE-FORM VARIANCE per slm-learning-093 | (1) re-run augment with HAIKU-PARAPHRASED reasons (scripts/distill/paraphrase_doc_verifier_reasons.py — already scaffolded); (2) retrain r=16 on diverse-reason corpus; (3) if still <0.85 after diverse augmentation, try r=32 on the diverse-reason corpus |
| multi-task generalist (rejected) | DATA shape — single LoRA can't hold 3 task shapes | switch to PEFT multi-adapter stacking (SL-T-04-02), or TIES merge of the 3 specialists |
| HumanEval 0/10 | DATA absence — 233 code envelopes total | starcoderdata Python subset OR haiku-generated function-completion pairs |
| GAD-tools at 30/30 | EVAL saturation | harder eval (200 cases? composition-of-commands?) before claiming more lift |
| Planning specialist (queued) | corpus is BIG (117k) but hasn't trained yet | go: r=16 first per ChatGPT directive; this is the per-domain ladder's first real test |

## References

- `.planning/codebase/audit-2026-05-07-data-quality-honest.md` — what we have
- decisions `slm-learning-087` (scaling ladder), `slm-learning-088` (multi-task falsified), `slm-learning-089` (r=8 reject), `slm-learning-090` (r=16 partial-win), `slm-learning-093` (template-uniformity regression — augment must include variance)
- ChatGPT directive 2026-05-06: "rank=8 first, rank=16 only if underfit"
- `models/REGISTRY.json` — empirical scores per lane
