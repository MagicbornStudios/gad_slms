# Scaling-proof charter

**Date:** 2026-05-08
**Author:** Dr. Stein
**Status:** Pre-registered. Draft 1.
**Operating constitution:** `.planning/concerns/research-program-charter.md`
**Decision refs (existing):** `slm-learning-097`, `slm-learning-103`,
`slm-learning-119`, `slm-learning-122`, `slm-learning-125`,
`slm-learning-126`, `slm-learning-130`, `slm-learning-153`,
`slm-learning-157`, `slm-learning-158`, `slm-learning-160`
**Decision refs (proposed):** `slm-learning-164` (this charter)

---

## Why pre-register

Operator goal: produce a **paper-shaped public claim** that low-cost
iterative growth can substitute for one-shot large-model training.
Pre-registering the falsifiable claims, the metrics, the success
thresholds, and the experimental matrix BEFORE running the
experiments is the discipline that keeps the result honest. Once
data is in hand, goalposts are easy to move; before then, they are
not. This charter freezes the goalposts.

Companion: `reports/research/morphism_qwen2_arch_review.md` (gates
the morphism arm).

---

## The honest framing — "growth" defined

We do **not** pretrain bases from scratch. We stand on
open-source pretraining (Qwen2.5-Coder-{0.5B, 1.5B, 3B, 7B}) and
"grow" capability on top via four mechanisms:

1. **Adapter growth** — LoRA / QLoRA on a frozen base
2. **Adapter stacking** — multiple specialists routed at inference
3. **Architectural morphism** — identity-init expansion
   (Net2Net-style); the only mechanism where we add parameters
4. **Gap-targeted data** — `slm-learning-130` recipe; cheap data
   that beats large data on strong bases

This is exactly the framing the operator asked for: "we just
'grow' ours." The grown thing is **deployed capability** measured
by benchmark and trajectory metrics, not the parameter count of a
fresh base. The paper claim must hold to this definition; any
audience confusion between "we trained a 3B from scratch" and "we
grew capability on top of an open 3B" must be killed in the
abstract.

---

## Three tiered claims

### Claim 1 (proven; headline) — $/successful-task

> **Cheap gap-targeted adapters on existing open bases reach
> scores that retraining a same-or-larger base from scratch would
> have to spend at least 1000× more to match.**

Status: **partially proven.** The 7B + hard_fn_norm canonical
assembly cost $0.94 of our money (training + eval, A100 wall) and
scores 84.8% HE / 82.3% MBPP, beating both Qwen 7B-base
(81.7/80.5) and Qwen 3B-base (83.5/74.4). Qwen2.5-Coder pretraining
costs are not public, but a comparable open 7B coder pretrain is
≥ $50k in GPU-hours; 1000× ≈ $940. We are well under that floor
already.

Needed for full proof:
- One additional rung where the same recipe lifts (3B + hard
  transfer test, $1, lane 2 in P0 program)
- A frontier-comparator row per `slm-learning-103` (claude-cli +
  Big Pickle + OpenRouter free tier on the same eval)
- A trajectory-completion row on escape-the-dungeon

Failure mode: if the 3B + hard transfer regresses, the recipe is
7B-only and the claim collapses to "narrow lift on one rung."

### Claim 2 (testable cheaply) — morphism preserves and lifts

> **Identity-initialized architectural expansion (Variant A in
> the morphism plan) preserves base output exactly at
> initialization, and after training on a 58-row hard_fn_norm
> dataset reaches at-least-parity with a LoRA r=16 of equivalent
> trainable mass on the same eval suite.**

Status: **untested.** Architecture review (today) returned GREEN.
Implementation is ~50 LOC. Cost ≤$2 end-to-end.

Falsifiable cleanly:
- Init invariant: `model_expanded(x) == model_base(x)` for 20
  prompts greedy decode. **0% tolerance.** If this fails the patch
  is broken.
- Post-train: HE / MBPP n=164 within ±2pp of LoRA r=16 control.

Failure mode: if the identity layer fails to learn (e.g., all
gradient flows around it through the residual), the expanded
model is just the base + dead weight. We treat that as a *clean
falsification*: morphism Variant A doesn't work in this regime,
and we either move to Variant B or abandon morphism for the next
cycle. Either way the result is publishable.

### Claim 3 (stretch; multi-shot) — stacked-adapter parity

> **A 1.5B base + N stacked gap-targeted adapters (routed via
> static router) reaches within 5pp of the 7B base on HE+MBPP.**

Status: **not proven, likely falsifiable.** Current 1.5B +
fn_norm is at 61.6% HE vs 7B base 81.7% — a 20pp gap. Closing
20pp at 1.5B with adapter stacks is the radical version of "grow
ours." Probably requires 3+ specialists + adapter-MoE routing
(lane 5).

Cost to test: $5–10 across multiple training/routing experiments.

If it falsifies cleanly (1.5B is genuinely capacity-limited at
some smaller gap), we publish the *capacity ceiling* — also a
useful result. The interesting outcome is finding where the
ceiling sits.

---

## Eight measurement metrics — what we publish

Every candidate that qualifies for promotion must produce these
eight rows (per `slm-learning-103` extended). Rows that are N/A
for a candidate must be marked `n/a` with reason; missing rows
are treated as failure.

| # | Metric | Definition | Source / harness |
|---|---|---|---|
| 1 | **HE pass@1 (greedy, n=164)** | HumanEval, temp=0.0, EOS early-stop, 10s subprocess timeout | `scripts/eval_humaneval.py` |
| 2 | **MBPP pass@1 (greedy, n=164)** | MBPP, same harness conventions | `scripts/eval_humaneval.py` (mbpp variant) |
| 3 | **$/successful-task** (`slm-learning-125`) | (training_usd + eval_usd) / (#correct − base_correct), only counts net-new correct vs the bare base | computed from rows 1–2 + cost log |
| 4 | **$/pp-lift** | (training_usd) / max(0, Δpp). Inf if regress. | computed from rows 1–2 + cost log |
| 5 | **active vs total params** (`slm-learning-160`) | active_params (per call), total_params (resident), trainable_params (this run) | scaling ledger |
| 6 | **owned-domain row** | gad_tools, doc-verifier, tooluse — pick the one(s) the candidate is positioned to lift | `scripts/eval_*.py` per domain |
| 7 | **trajectory-completion composite** | Existing rubric defined in `escape-the-dungeon/REQUIREMENTS.xml` v1..v5: weighted score across requirement coverage (40% — gates G1 no-softlock, G2 forge+ingenuity, G3 UI quality, G4 pressure mechanics), planning quality (30%), per-task discipline (25%), skill accuracy (25%), time efficiency (20%), and a human-review playability score 0.0–1.0. v4 (claude-cli, no framework) anchors the strongest baseline at 0.916. | `evals/escape-the-dungeon/species/gad/v*/SCORE.md` |
| 8 | **frontier comparator** | Same eval suite (rows 1, 2, 7) run against claude-cli + Big Pickle (OpenCode Zen) + OpenRouter free tier (Llama-3.3-70B-Instruct:free) + bare Qwen 7B-Instruct | `scripts/eval_comparator.py` (TBD) |

**Promotion gate (per candidate):**
- Row 1 OR Row 2 lift ≥ +2pp vs bare base — required
- Row 3 ≤ $1 / new-correct — required
- Row 4 ≤ $1 / pp — required
- Row 7 ≥ bare-species rate — required (otherwise we're losing on the agentic axis)
- Rows 5, 6, 8 — must be filled, no specific threshold

Missing any required row blocks promotion. This is the
non-negotiable floor.

---

## Four-arm experimental matrix

Each candidate proof points at **one** of these arms. All four
arms share the same eval suite (rows 1–8 above) and the same
fixed harness mode.

### Arm 1 — Adapter growth (Claim 1 proof)

| Field | Value |
|---|---|
| Bases | Qwen2.5-Coder-{1.5B, 3B, 7B}-Instruct |
| Method | Hard_fn_norm LoRA r=16, gap-targeted to each base's own failures |
| Datasets | 7B-hard (existing 58 rows) + 3B-hard (to-build, ~25 rows) + 1.5B-hard (to-build, ~74 rows) |
| Cost cap | $5 across all rungs |
| Wall cap | 30 min total training + 60 min eval |
| Pass | All three rungs lift on HE OR MBPP, none regresses >5pp |
| Fail | Any rung regresses on both axes |
| Gate it unblocks | 32B + hard shot (`slm-learning-097` $50 budget) |

### Arm 2 — Morphism (Claim 2 proof)

| Field | Value |
|---|---|
| Base | Qwen2.5-Coder-0.5B-Instruct |
| Method | Variant A from `morphism_qwen2_arch_review.md` (identity projection layer inserted between layers 7 and 8) |
| Dataset | **0.5B-base-failure rows (to-build)** — operator-locked 2026-05-08; the existing 7B-hard rows are NOT correct because they were built from 7B's failure distribution, which differs from 0.5B's. |
| Prerequisite | Eval Qwen2.5-Coder-0.5B-Instruct base on HumanEval n=164 to identify 0.5B's actual failure cases (~$0.40, ~5 min); then run `scripts/data/build_hard_fn_norm_dataset.py` (already exists) targeting 0.5B failures (~$0 local). |
| Reporting | Per `morphism_prototype_plan.md` four-arm study: (A) 0.5B baseline eval only, (B) LoRA r=16 control on same data, (C) morphism Variant A trained on same data, (D) optional Variant B if budget allows. Each arm reports: init token-agreement vs base, trainable params, train wall, train cost, post-train HE/MBPP n=164 pass@1. |
| Cost cap | $3 (0.5B eval $0.40 + LoRA control $0.30 + morphism train $0.30 + 4× eval $1.60 + 10% overhead) |
| Wall cap | 5 min 0.5B eval + 5 min ×2 trains + 30 min 4× evals = ~50 min |
| Pass | Init token-agreement = 100% on 20 prompts (broken patch otherwise); post-train HE/MBPP within ±2pp of LoRA r=16 control on the same 0.5B-base-failure rows |
| Fail | Init agreement < 100% (broken patch) OR morphism trained-arm regresses vs LoRA control by >2pp |
| Gate it unblocks | Variant B (block duplication), 1.5B → 3B morphism ladder, and the "we grow ours" headline of Claim 2 |

### Arm 3 — Adapter stacking (Claim 3 proof)

| Field | Value |
|---|---|
| Base | Qwen2.5-Coder-1.5B-Instruct |
| Method | 3 LoRA r=16 specialists (code, reasoning, tool-use) + static domain router |
| Datasets | OpenCodeReasoning + OpenMathInstruct + tooluse-v2-filtered |
| Cost cap | $10 |
| Wall cap | 60 min train + 60 min eval |
| Pass | Combined system within 5pp HE of 7B-base; per-domain accuracy ≥ best-single-adapter |
| Fail | Combined system regresses on any domain vs single best adapter |
| Gate it unblocks | Lane 5 productionization (vLLM router, adapter-MoE serving) |

### Arm 4 — escape-the-dungeon row 7 anchor

**Important framing issue surfaced 2026-05-08:** the existing
v1..v12 species runs on escape-the-dungeon are all **claude-cli
driving the framework**, not Qwen / slm-learning models doing the
implementation directly. The eval is currently a *framework
benchmark*, not a model benchmark. To get an SLM row, we have a
choice (see Open Questions, "row-7 framing") — until that is
decided, Arm 4 splits into two sub-arms:

#### Arm 4a — anchor against existing v4 / v5 runs (free)

| Field | Value |
|---|---|
| Source | `species/gad/v4` (claude-cli + GAD 1.32.0, TRACE.json composite **0.916**, 38 min wall, 136.9k tokens, 19 tasks, all 12 reqs met, skill accuracy 80%) |
| Source | `species/gad/v5` (claude-cli + GAD 1.32.0, baseline = v4, TRACE.json composite **0.8123** with human_review 0.0 "blank screen, no UI renders", 18 min, 92.3k tokens, 12 tasks, full coverage by count but unplayable) |
| Cost | $0 (existing data) |
| Pass | n/a — these are the **anchors** every other arm must report against on row 7 |
| Output | published baseline numbers |

#### Arm 4b — slm-learning row on escape-the-dungeon (paid, requires operator decision)

| Field | Value |
|---|---|
| Method (Option I, hybrid) | claude-cli driving framework + our adapter served via vLLM as the code-completion backend ("does our adapter help a real CLI ship a real game?") |
| Method (Option II, pure SLM) | Modify the eval harness so an SLM checkpoint can drive trajectory directly. Cross-repo change in custom_portfolio/vendor/get-anything-done. |
| Method (Option III, deferred) | Skip Arm 4b for v1 of the paper; rely on Arm 4a + HE/MBPP for the published claim. Add Arm 4b in v2. |
| Cost cap | $5–10 (Option I) / $20+ (Option II) / $0 (Option III) |
| Pass | Trajectory composite ≥ v5's 0.812 with lower token cost — would directly demonstrate adapter value |
| Decision needed | See Open Questions |

Without Arm 4b in some form, the paper's headline claim is
defensible only on HE/MBPP/$ — a real but narrow benchmark. With
Arm 4b in some form, the paper has a **real-world end-to-end
result** that frontier comparators struggle to dismiss.

---

## Gating sequence (what fires in what order)

```
                               START
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
     ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
     │  Arm 4: bare │    │  Arm 1: 3B + │   │  Arm 2:      │
     │  on escape-  │    │  hard transf.│   │  morphism    │
     │  the-dungeon │    │  ($1)        │   │  Variant A   │
     │  ($5)        │    └──────┬───────┘   │  ($2)        │
     └──────┬───────┘           │           └──────┬───────┘
            │                   ▼                  │
            │           ┌──────────────┐           │
            │           │ 7B + MBPP-   │           │
            │           │ hard ($1)    │           │
            │           └──────┬───────┘           │
            │                   │                   │
            └───────────────────┼───────────────────┘
                                ▼
                       ┌─────────────────┐
                       │ 7B + hard re-run│
                       │ on escape-the-  │
                       │ dungeon ($5)    │
                       └────────┬────────┘
                                ▼
                       ┌─────────────────┐
                       │ frontier        │
                       │ comparator row  │
                       │ ($3)            │
                       └────────┬────────┘
                                ▼
                       ┌─────────────────┐
                       │ paper draft     │
                       │ ($0)            │
                       └────────┬────────┘
                                ▼
                       Decision: 32B shot?
                       gated by Arm 1 + Row 8
```

Total budget for the proof: **~$22** (within remaining $15
Modal + a small top-up). The 32B shot stays a separate
authorization and is not part of this charter.

---

## What v1..v12 already tells us (free anchor data)

Subagent reading 2026-05-08 of
`custom_portfolio/vendor/get-anything-done/evals/escape-the-dungeon/species/gad/`:

| Version | Runtime | Outcome | Wall | Tokens | Composite | Notes |
|---|---|---|---|---|---|---|
| v1 | claude-cli (GAD 1.32.0) | snapshot only, aborted | 1 min | — | — | no implementation |
| v2 | claude-cli (GAD 1.32.0) | partial; manual scaffold | 174 min | — | 0.285 | no framework discipline |
| v3 | claude-cli (GAD 1.32.0) | prompt-only | — | — | — | no execution |
| **v4** | **claude-cli + GAD 1.32.0** | **complete; all 12 reqs met** | **38 min** | **136.9k** | **0.916** | human_review n/a; "All 12 success criteria met. 20 source files, full content pack." |
| **v5** | **claude-cli + GAD 1.32.0** | **counted-coverage 100%, blank-screen gate-fail** | **18 min** | **92.3k** | **0.8123** | **human_review 0.0** — blank screen, no UI renders, no main menu |
| v6 | claude-cli + GAD 1.32.0 | counted-coverage 0%, ES module load failure | 20 min | — | 0.347 | human_review 0.0 — same failure mode as v5; needs web server |
| v7 | claude-cli + GAD 1.32.0 | partial; combat softlock | 24 min | 93.6k | 0.668 | human_review 0.30 — game loop broken post-combat |
| v8 | claude-cli + GAD 1.32.0 | rate-limited at 1291 tokens | 16 min | 1.3k | 0.177 | human_review 0.20 — crafting broke game; ASCII text |
| v9 | claude-cli + GAD 1.32.0 | rate-limited at 81 tool uses | 14 min | 3.2k | null | only phase 01 + task 02-01; coverage 0.208 |
| v10 | claude-cli + GAD 1.32.0 | API 529 overload at 55 tool uses | 9 min | 1.2k | null | phases 01–02 done, no scenes; coverage 0.083 |
| v11 | claude-cli + GAD 1.38.0 | incomplete trace | 24 min | 107k | null | greenfield, unscored |
| v12 | claude-cli + GAD 1.32.0 | execute-ready, not run | — | — | — | **open slot for our adapter** |

(All composite + human_review numbers verified directly from each
version's `TRACE.json` 2026-05-08 via
`scripts/eval/check_trace_score_consistency.py`.)

### Beyond gad/: bare and emergent species playable rows

The cross-species check found additional anchor data we did not
have before. The `bare/` and `emergent/` species also produced
playable runs with non-zero human-review scores:

| Species/version | Tokens | Composite | Human review | Notes |
|---|---|---|---|---|
| bare/v2 | 87,661 | 0.601 | **0.50** | "Game renders, title works, New Game works, room navigation works, combat works, dialogue works, menus work. Very playable vertical slice. Missing: rune forge, icons, visual polish." |
| bare/v3 | — | 0.526 | **0.70** | Playable but no floor progression after boss |
| emergent/v2 | — | 0.478 | **0.50** | Playable but no floor progression |
| **emergent/v4** | — | null | **0.885** | **Strongest human-review score in the dataset.** Run was rate-limited so composite is null, but the playable artifact ranks higher than any gad/ run. |

**Implication for the charter.** The strongest "did it produce a
playable game" results are NOT in the gad/ species — they are in
bare/ and emergent/. emergent/v4's human_review 0.885 sets a
ceiling that gad/v4's human_review (n/a) and gad/v7's
human_review 0.30 are far below. Any "GAD framework helps the
agent ship a game" claim has to acknowledge that the strongest
playable runs in the dataset use less framework, not more.

This does not undermine GAD's value — GAD wins on discipline,
planning, and reproducibility, all of which are paper-relevant
for downstream training data — but the row-7 *playability*
metric is currently dominated by less-frameworked species. The
hybrid Arm 4b experiment is the cleanest way to test whether our
SLM-in-the-loop closes that gap.

### Cost-backfill estimates (Q3 — token-count method, verified 2026-05-08)

Per Q3 above, USD estimates derived from `total_tokens` ×
estimated claude-cli pricing at run date. Two columns: lower
bound assumes Sonnet-class pricing (~$8/M blended,
$3/$15 input/output × 70/30 mix); upper bound assumes
Opus-class pricing (~$30/M blended, $15/$75 × 70/30 mix). The
true cost lies somewhere in this range; a single bound requires
knowing which model claude-cli was using on each run date.
Going forward, real cost logging is added to row-7 traces per
Q3.

All numbers below verified directly from each version's
TRACE.json on 2026-05-08 (same source as composite +
human_review). Tool-uses included to anchor budget-discipline
analysis (the v8/v9/v10 runs were all cut short by tool-use
limits, not token limits).

| Species/version | Tokens | Tool uses | Wall (min) | $ at $8/M (Sonnet) | $ at $30/M (Opus) | Composite | Human-review | Status |
|---|---|---|---|---|---|---|---|---|
| gad/v4 | 136,930 | n/a | 38 | $1.10 | $4.11 | 0.916 | n/a | complete |
| gad/v5 | 92,278 | 110 | 18 | $0.74 | $2.77 | 0.8123 | 0.00 | blank-screen gate-fail |
| gad/v6 | 138,835 | 150 | 20 | $1.11 | $4.17 | 0.347 | 0.00 | blank-screen gate-fail |
| gad/v7 | 93,632 | 137 | 24 | $0.75 | $2.81 | 0.668 | 0.30 | combat softlock |
| gad/v8 | 1,291 | 62 | 16 | $0.010 | $0.039 | 0.177 | 0.20 | crafting broke game (low-token; aborted) |
| gad/v9 | 3,238 | 81 | 14 | $0.026 | $0.097 | null | 0.05 | rate-limited at tool_uses=81 |
| gad/v10 | 1,216 | 55 | 9 | $0.010 | $0.036 | null | 0.02 | API 529 overload at tool_uses=55 |
| gad/v11 | 107,228 | 70 | 24 | $0.86 | $3.22 | null | null | unscored / incomplete trace |
| bare/v2 | 87,661 | 110 | n/a | $0.70 | $2.63 | 0.601 | 0.50 | playable vertical slice |

**Best $/playable-game to date** (using composite ≥ 0.6 + human-
review > 0 as "ships a game" floor):

| Run | Composite | Human-review | $ (Sonnet–Opus) | Notes |
|---|---|---|---|---|
| **bare/v2** | **0.601** | **0.50** | **$0.70–$2.63** | playable, framework-light |
| gad/v4 | 0.916 | n/a | $1.10–$4.11 | composite-only, no human-playability score |
| gad/v7 | 0.668 | 0.30 | $0.75–$2.81 | partly playable, combat softlock |

**Direct comparison.** Within paired benchmark cost, bare/v2
beats gad/v7 on human-review playability (0.50 vs 0.30) at
similar cost. The hybrid Arm 4b experiment (claude-cli + GAD +
our adapter via vLLM) needs to beat bare/v2's
$0.70–$2.63-per-playable-vertical-slice baseline OR gad/v7's
0.30-playability-at-$0.75–$2.81 to be a real win.

**v8/v9/v10 are tool-use-limited, not token-limited.** All three
spent <$0.10 on tokens but burned tool-use quota on planning XML
authoring before reaching scene implementation. This is the
"GAD framework overhead consumes budget" failure mode the
charter Q1 hybrid arm is designed to test against — an adapter
that cuts per-task tokens has direct row-7 leverage on these
budget-constrained runs.

**Source-of-truth note (corrected 2026-05-08):** the
authoritative composite + human-review score lives in each
version's `TRACE.json`, not in `SCORE.md`. `SCORE.md` is auto-
derived from git/planning-doc discipline metrics and excludes the
human-review playability deduction. An earlier draft of this
charter cited v5 composite as 0.935 from SCORE.md; that figure
reflects only the discipline-weighted score before the human
playability review. The verified TRACE.json composite for v5 is
**0.8123** with human_review 0.0. All numbers in the table above
are now sourced from TRACE.json.

**Conclusions for the charter (verified):**

1. **v4 is the strongest existing anchor** on row 7
   (TRACE.json composite 0.916, all 12 reqs met, 38 min,
   136.9k tokens). Every framework-or-model addition must show
   it doesn't regress below v4.
2. **v5 is the framework-only treatment** (TRACE.json composite
   0.8123, human_review 0.0 "blank screen"). v5 won on
   discipline + speed but the human reviewer scored 0 on
   playability. The composite drop of 0.104 vs v4 is the cost of
   framework overhead in *this sample*. This trade-off is
   exactly what an adapter that drives down per-task token cost
   could close.
3. **v6 reproduced the v5 blank-screen failure mode** — both
   shipped systems-only code with no rendered UI. This is a
   recurring failure pattern, not a one-off.
4. **v7 was the closest-to-playable run** with a non-zero human
   score (0.30) — combat works but loop is broken post-combat.
5. **v8, v9, v10 demonstrate token budget is a hard constraint.**
   Three consecutive runs hit rate limits or API overloads
   before completing. An adapter that drives down per-task token
   cost has direct row-7 leverage.
6. **v11 is unscored** — preserved trace but no
   composite/coverage values. Don't cite as a baseline.
7. **v12 is execute-ready but not run** — natural slot for
   "claude-cli + our 7B+hard_fn_norm via vLLM" once Q1 is
   answered.
8. **Gap: no USD cost in any TRACE.json or SCORE.md.** Backfill
   needed (Q3 above).

---

## What we own as durable artifacts

Per `slm-learning-096` and `slm-learning-122`, every arm must
produce three durable artifacts that survive past the run:

1. **Weights** — adapter or expanded checkpoint, on HF Hub
   (small) or Modal volume (large)
2. **Outputs corpus** — the 200-prompt held-out bank scored by
   this candidate, JSONL on Modal volume
3. **Regression journal** — JSONL of every test the candidate
   failed, indexed by failure taxonomy, on Modal volume

If an arm does not produce all three, its row in the published
table reads **`n/a — artifact incomplete`** rather than a number.

---

## What this charter does NOT cover

- The 32B shot. That's still gated by `slm-learning-097` and
  needs separate authorization once Arm 1 lands.
- Production routing decisions (which adapter goes where in the
  inference gateway). That's a deployment question, not a proof
  question.
- Frontier comparator on owned domains (gad_tools etc.). The
  comparator row in this charter is on HE/MBPP/escape-the-dungeon.
  Owned-domain comparators are a follow-up cycle.
- Any architectural change beyond Variant A morphism. Variant B
  and dense-to-MoE upcycling are explicitly deferred.

---

## Operator decisions (answered 2026-05-08)

| Q | Choice | Rationale (operator-given) |
|---|---|---|
| Q1 row-7 framing | **Option I — hybrid** | claude-cli/GAD remains driver; selected completions route through our SLM/adapter via vLLM. Label honestly as "hybrid GAD trajectory, not pure SLM agent." |
| Q2 stochasticity | **3-runs median** | 1 run too noisy; 5 runs slows iteration; 3 is a paper-shaped compromise |
| Q3 cost backfill | **Estimate from token counts now + add real cost logging going forward** | Re-running v1..v12 just for cost is wasteful; estimate is acceptable if clearly labeled |

These three decisions are now load-bearing in the charter. Goalpost-shifts require a decision amendment.

## Vocabulary locks (operator-given 2026-05-08)

### Base-failure row

A training example **made from something a specific base model
already failed**, with a corrected target and failure-type
label. Schema:

```json
{
  "source_model": "Qwen2.5-Coder-7B-Instruct",
  "source_eval": "humaneval",
  "prompt": "Write a function that ...",
  "base_output": "def foo(...): ...",
  "base_passed": false,
  "failure_type": "edge_case_miss | wrong_algorithm | wrong_signature | hallucination",
  "corrected_output": "def foo(...): ...",
  "target_contract": "function_definition",
  "tests": ["assert ..."],
  "reason_for_inclusion": "<base_id> base failed this case"
}
```

The 7B-hard-fn-norm dataset (`data/processed/7b-hard-fn-norm-2026-05-08/rows.jsonl`,
58 rows) is the canonical example. Generic fn_norm rows teach
broad output shape; base-failure rows teach the exact things a
specific base still cannot do.

**Charter rule:** any "hard" or "gap-targeted" arm in this
charter (Arm 1, Arm 2) must train on base-failure rows for the
specific base under test, NOT on generic fn_norm rows. This is
non-negotiable per `slm-learning-130`.

### Base strength (not parameter count)

Parameter count is *how many weights*. Base strength is *how
well the pretrained/instruct model performs before we touch
it.* They are not the same. Evidence: 3B base scores 83.5% HE
vs 7B base 81.7% HE in our harness — the smaller, better-tuned
3B beats the larger 7B on this task.

**Per-domain base-strength score:**

```
base_strength_<domain> =
    public_eval_score
  + GAD_eval_score
  + contract_pass_rate
  + cost_efficiency
  + latency_efficiency
  + context_or_retrieval_compatibility
  − regression_risk
```

Compute one per domain: `coding`, `tool_action`,
`game_artifact`, `repo_repair`, `reasoning`. A model can be
strong for coding and weak for tool actions. Charter rows that
cite "base strength" must name the domain.

## Open questions (deferred)

### Q1 (resolved above) — row-7 framing

The existing v1..v12 runs are all `claude-cli` driving the
framework. None are an SLM-driven trajectory. Three options:

- **Option I (hybrid).** claude-cli drives the framework but
  routes code-completion calls through vLLM serving our adapter.
  This is the "does our adapter help an external CLI ship a real
  game" framing. ~$5–10 per row. Cleanest story for the paper:
  same framework, different model backend.
- **Option II (pure SLM).** Modify
  `custom_portfolio/vendor/get-anything-done/evals/escape-the-dungeon`
  so an SLM checkpoint can drive trajectory directly. Cross-repo
  work; ~$20+ for the eval modification + the runs. Bigger story
  but more risk.
- **Option III (deferred).** v1 of the paper claims on HE/MBPP/$
  only; row 7 is anchored by v4/v5 (existing) but not contested.
  Add Arm 4b in v2.

Recommendation: **Option I.** Framework is held constant, only
the model backend changes — that is exactly what publishable
ablation studies look like.

### Q2 — row-7 stochasticity

Trajectory completion is non-deterministic. Three options:

- 1 run per candidate (cheap, noisy)
- 3 runs, take median (recommended)
- 5 runs, report mean ± stdev (cleanest paper, 5× cost)

Recommendation: **3 runs, take median** for v1; bump to 5 for
the published version if budget allows.

### Q3 — backfill missing cost data on v1..v12

The v1..v12 SCORE.md files capture composite scores and wall
time but **not USD cost**. To publish $/successful-task on row 3
for the v4 / v5 anchors, we need to retroactively estimate cost
from token counts and the claude-cli pricing at the time of each
run. Options:

- Estimate from token counts × current haiku/sonnet/opus pricing
  (cheap, ~30 min, slightly imprecise)
- Re-run v4 and v5 with cost logging on (~$10 per re-run × 2)
- Skip $ cost on row 7; only report token cost (free, slightly
  weaker comparison)

Recommendation: **estimate from token counts** as the v1
approximation; flag the limitation in the paper.

---

## Cross-references

- `reports/research/morphism_qwen2_arch_review.md` — Arm 2 gate
- `reports/research/p0_upscaling_program.md` — the 10 lanes; Arm 1 is lane 2, Arm 2 is lane 10, Arm 3 is lane 5
- `reports/scaling/gad_scaling_ledger.md` — current canonical assemblies
- `reports/evals/hard_fn_norm_7b_gate.md` — Claim 1 partial proof
- `reports/evals/fn_normalized_3b_specialist.md` — the negative result that constrains Claim 1
- `.planning/concerns/research-program-charter.md` — operating constitution
- `slm-learning-103` — compare-and-compete (4-row matrix, extended to 8 here)
- `slm-learning-125` — cost-per-successful-task as the comparison metric
- `slm-learning-130` — gap-targeted training as canonical scale recipe

---

## Decision proposed: slm-learning-164

> **Scaling-proof charter is pre-registered.** The three tiered
> claims, the eight measurement metrics, the four experimental
> arms, and the gating sequence are frozen as of 2026-05-08. Any
> deviation from this charter during execution must be logged as
> a decision amendment, not a goalpost shift. Charter is the
> authority for what counts as a proven scaling result in this
> project until superseded.

— Dr. Stein, scaling-proof charter draft 1, 2026-05-08
