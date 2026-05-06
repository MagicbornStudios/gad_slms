# Data Quality — Honest Assessment

**Date:** 2026-05-07
**Scope:** what we ACTUALLY have to train on vs what we CLAIM to want to train on
**Auditor:** claude-code (slm-learning, this session)
**Triggered by:** operator question 2026-05-06: "do we have high quality
data and etc that we are trying to learn and do."

Companion to `.planning/codebase/audit-2026-05-06-training-data-inventory.md`
(which describes everything in the corpus). This document scores
WHAT WE HAVE for which task shape, and is direct about the gaps.

---

## The TL;DR

Per the cohort builder run on the 2026-05-06 telemetry export
(119,819 envelopes filtered to 23 cohorts at the project +
content_type axis):

| Trainable cohorts (≥1000 envelopes) | Count |
|---|---|
| `global / planning` | 117,196 |
| `gad-framework / planning` | 1,838 |

| Sub-threshold cohorts | Count |
|---|---|
| `global / code` | 629 |
| `get-anything-done / planning` | 60 |
| `llm-from-scratch / planning` | 24 |
| `slm-learning / planning` | 19 |
| `7greens / planning` | 11 |
| `grime-time / planning` | 8 |
| (15 more, all <10) | … |

**Implication: we have huge volumes of planning data and basically
nothing else.** Real distribution from the producer-side (gad-monorepo
Claude reported, 156K envelopes total):

```
content_type histogram:
  planning  131549
  meta       24683
  code         233
  site          10
  narrative      5
  eval           2
```

Code = 0.15% of the corpus. Narrative = 0.003%. Site, eval = noise floor.

---

## What this means for each lane

| Specialist | Trainable today? | Why |
|---|---|---|
| **CLI translator** (v2 canonical 30/30) | YES — already trained | 783 hand-curated + vocab-anchored pairs (`gad_tool_pairs_v2.jsonl`) |
| **Math reasoner** (canonical 25/50) | YES — already trained | 5000 OpenMathInstruct-2 pairs (external HF dataset, not from telemetry) |
| **Tool-use sanity** | YES — already trained | 789 real Claude-Code traces extracted from `.trace-events.jsonl` |
| **Doc-verifier** | YES — corpus ready | 442 reshaped train + 50 holdout from `synth_doc_verifier_pairs.py` (filesystem-grounded, NOT telemetry) |
| **Multi-task generalist** | training in flight | 6,572 combined pairs (CLI + tool-use + math) |
| **Planning agent** (snapshot summarizer / planner / handoff judge) | YES, brand new | 117k+ envelopes from `global / planning` cohort — biggest available signal |
| **Decision logger / archivist** | YES, marginal | 325 decision envelopes (new adapter from phase 145.5 export) |
| **Errors-and-attempts DPO source** | YES, marginal | 97 envelopes (DPO gold — chosen vs rejected pairs available) |
| **Handoff router / task→solution agent** | YES, small | 473 handoff envelopes with `parent_id` chains |
| **Code completion / repair (HumanEval)** | **NO — gap G8 confirmed** | 233 code envelopes total. Need either (a) HF starcoderdata pull, (b) extract code from response envelopes via code-aware filter, OR (c) haiku synthesis |
| **Narrative scene / book / structured world data** | **NO** | 5 envelopes. Need narrative project to start producing real content |
| **Site / landing page / frontend** | **NO** | 10 envelopes. Need active sites/* work |
| **Eval / species / generations** | **NO** | 2 envelopes. Phase 06 will produce these |
| **SWE-bench code-repair** | **NO** | scaffold only; needs real patch-generator + test-runner per phase 06 |

---

## What we should NOT claim

Per `slm-learning-070` (realistic ceiling) + `slm-learning-071`
(evidence-tiered policy):

- ❌ "We have a coding agent" — we have 233 code envelopes. We are far
  from a coder. The current 0/10 HumanEval scores across every adapter
  are not a bug — they reflect the data we don't have.
- ❌ "We can compete with Suno" — already scoped out per `slm-learning-077`
  (game/cinema/beats only).
- ❌ "We're publishable" — we have empirical results (v2 30/30, math
  25/50) but no novel claim with rigorous baseline + reproducibility.
- ❌ "Per-domain LoRA registry is ready" — only 2 of 23 cohorts pass
  the 1000-envelope floor. Per-domain training is BLOCKED on
  accumulating telemetry from real domain work, not on infrastructure.

---

## What we CAN claim

- ✅ "v2 CLI translator solves the GAD-tools 30-case at 100%" — T2
  evidence (multi-run, baseline-compared)
- ✅ "math 1.5B trained on 5k OpenMathInstruct hits 50% on GSM8K, 12x
  bare-base" — T2 evidence
- ✅ "We can route narrow planning queries to a local 1.5B at $0/call"
  — T1 evidence; widen to T2 by running comparative-matrix vs frontier
- ✅ "We have a working telemetry → SFT pipeline that redacts secrets
  by default and produces session-grouped pairs" — T2
- ✅ "117k planning envelopes is enough to train a planning specialist"
  — T1 hypothesis; needs the actual training run to promote to T2

---

## What changes the data picture

The 233 code envelopes will grow if/when:

1. We do real code work in the monorepo (every `gad team` worker
   touching `*.ts/*.py` files emits `content_type=code` envelopes)
2. We seed `data/external/` with a real code corpus (starcoderdata,
   bigcode/the-stack-smol, MultiPL-T)
3. We synthesize via haiku (decision `slm-learning-019` already
   approves this for distillation)
4. We add a code-completion eval that pulls failing rows back as
   training pairs (negative-tier per the data tiers in
   training-data-inventory.md)

The narrative + site numbers will grow when those projects come online
(`magicborn-narrative` is not yet active in the monorepo; `7greens`
and `grime-time` have very low envelope counts).

---

## Comparative-eval-matrix scaffold

Operator request: "comparative results to models across the board and
frontier models in the same ecosystem." Scaffold shipped at:

- `scripts/eval/run_comparative_matrix.py` — N models × M benchmarks
- `scripts/eval/render_comparison.py` — produces paste-ready markdown
- `scripts/eval/models_to_compare.json` — declared model axis (3 local +
  1 remote-stub + 5 frontier rows)

Status today:

| Benchmark | Loadable cases? | Models we can score now |
|---|---|---|
| `gad_tools_v2` | YES (30 cases from `promptfoo-gad-tools.yaml`) | local-3 (when v2 endpoint serving) + frontier (when API keys set) |
| `doc_verifier` | YES (50 holdout cases) | local-3 + frontier |
| `gsm8k` | NOT YET wired into matrix | use existing `scripts/eval_gsm8k.py` |
| `humaneval` | NOT YET wired | use existing `scripts/eval_humaneval.py` |
| `swebench_v1` | scaffold only | phase 06 dependency |

Next step to actually populate the comparative table:

1. `bash scripts/serve/start_v2.sh --windows` (start the local endpoint)
2. Set env: `ANTHROPIC_API_KEY=... OPENAI_API_KEY=... GOOGLE_API_KEY=...`
3. `python scripts/eval/run_comparative_matrix.py --benchmark gad_tools_v2`
4. `python scripts/eval/run_comparative_matrix.py --benchmark doc_verifier`
5. `python scripts/eval/render_comparison.py --in experiments/comparative/matrix-*.json`

Cost cap warning: the 30-case GAD-tools eval against all 5 frontier
rows would cost ~$2-5 in tokens depending on response length. Use
`--no-frontier` for cost-controlled iteration.

---

## Recommended priority order

Per ChatGPT directive 2026-05-06 + this audit:

1. **Stop pretending we can train a coder.** Mark all "code"-shape
   training in the queue as `blocked-on-corpus` until either external
   data lands or telemetry ramps.
2. **Train the planning specialist.** 117k envelopes is huge. New
   queue job: `gad-planning-specialist-r16-2026-05-07` on a
   filtered planning cohort, evaluated on a 50-pair held-out
   planning-task set. This is the biggest available win.
3. **Run the comparative matrix on what works** (gad_tools_v2 +
   doc_verifier across local-3 + frontier-3 = 18 rows, ~2 minutes
   compute, ~$1-2 in API calls).
4. **Pull starcoderdata Python subset** for the next coder attempt.
   Time-box: 1 day to download + tokenize + first training run.
5. **Collect more code envelopes** by deliberately running coding
   tasks through `gad team` workers — every `*.ts/*.py` edit grows the
   `code` cohort.

---

## Decisions touched

- `slm-learning-053` — eval stack additions
- `slm-learning-070` — realistic ceiling (workflow memory + narrow
  routing, NOT capability matching)
- `slm-learning-071` — evidence-tiered capability policy
- `slm-learning-079` — per-domain specialist ladder (gated on this
  data quality being honest)
- `slm-learning-086` — data flywheel mandate
- `slm-learning-087` — scaling ladder; "more parameters won't fix bad
  data" is exactly this audit's central point

*Author: claude-code (opus-4-7 1M ctx). Counts from
`scripts/build_cohorts.py` run on `data/raw/2026-05-06/`.*
