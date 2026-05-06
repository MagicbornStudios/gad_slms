# Next session handoff — cold pickup brief

Read this FIRST. Walks the next session through priority work without
re-litigating decisions.

## Where things stand

| Lane | Canonical | Best candidate | Open question |
|---|---|---|---|
| CLI translator | `dr-stein-stage25-qwen15-instruct-v2` (30/30 GAD-tools) | none queued | eval saturated — need harder eval before more training |
| Math reasoner | `dr-stein-colab-qwen15-math-5k` (25/50 GSM8K) | none queued | next: more pairs OR scale to 3B |
| Doc-verifier | none yet | `dr-stein-stage25-qwen15-doc-verifier-r16` (F1=0.720) | augment unknown class via haiku, retrain r=16 |
| Tool-use | sanity adapter exists | none queued | telemetry now has 4841 tooluse pairs — train v2 |
| Multi-task | none, REJECTED | n/a | pursue stacking/TIES instead |
| Planning specialist | none yet | queued (blocked-on-deps) | extract holdout from 117k cohort + write config + L4 setup |
| Code/HumanEval | nothing trained | nothing queued | DATA absent — 233 envelopes; pull starcoderdata or haiku synth |
| Router classifier | nothing | nothing | gad-monorepo G1 closed; routing.jsonl now has data — train this next |
| Attention classifier | rule-based v1 only | nothing | learned classifier when we have a labeled golden set |
| Skeleton classifier | nothing | nothing | gated on backward sweep |
| Kael intent classifier | rule-based v1 only | nothing | gated on accept/reject trace data accumulation |

## The diagnostic to run first thing next session

```bash
gad snapshot --projectid slm-learning
gad handoffs list --projectid slm-learning
ls experiments/queue/{pending,running,evaluated,rejected}/
ls .planning/handoffs/open/
git log --oneline -10
```

Then read in order:
1. `.planning/concerns/scaling-decisions.md` — when params vs data vs training
2. `.planning/codebase/audit-2026-05-07-data-quality-honest.md` — what data we have
3. `models/REGISTRY.json` — empirical scores per lane
4. `experiments/queue/pending/` — what's queued

## Priority order for "training like crazy"

Per `slm-learning-051` (candidate-only) + `slm-learning-080` (compute tiers):

### Tier 0 local (1660 Ti) — fire-and-forget overnight, ~$0

1. **Doc-verifier r=16 augmented**. Gate failed because unknown class
   has 70 training examples (16% of 442). Run haiku to generate
   ~150 synthetic unknown cases (the script doesn't exist yet —
   ~100 LOC: read 70 unknown rows, prompt haiku to paraphrase claim
   while keeping status=unknown, write expanded `data/eval/
   doc_verifier_train.augmented.jsonl`). Retrain r=16 on ~590 pairs.
   Expected: unknown F1 0.46 → 0.7+, gate-passing.
2. **Tool-use sanity v2** on `data/processed/2026-05-06/sft_tooluse.jsonl`
   (4841 pairs from real Claude sessions, 6× the original 789).
   Existing tool-use config + new path. Should be a clean lift.
3. **Router classifier** on `.planning/.gad-log/<date>-routing.jsonl`
   (now populated per gad-monorepo G1 closeout). Tiny classifier,
   perfect 1660 Ti target. Need a few hundred routing decisions
   accumulated before training is meaningful.
4. **Constitution-impact arm C eval** (`scripts/eval/constitution_arm_c.py`)
   — no training, just eval the existing v2 with vs without soul
   prompt. Tells us if the soul system moves a measurable needle.

### Tier 1 remote (HF Jobs L4 ~$0.80/hr) — operator-triggered

5. **Planning specialist r=16 on 117k cohort**. The big lever per
   audit-2026-05-07. Need: extract holdout from
   `data/cohorts/2026-05-06/cohort-global-planning.jsonl`, write
   `experiments/configs/stage25_qwen15_planning_r16.yaml`, configure
   HF Jobs CLI. Expected wall ~2hr, cost ~$1.60. Spec already at
   `experiments/queue/pending/planning-specialist-r16-2026-05-07.json`.
6. **PEFT multi-adapter stacking** (SL-T-04-02). Load v2 + math +
   tooluse simultaneously, route per call. The right answer to the
   multi-task LoRA falsification per `slm-learning-088`.
7. **Tier 1 7B coder QLoRA** (SL-T-04-06). Qwen2.5-Coder-7B + tooluse
   pairs. First serious code-shape model. Gated on having a real
   code corpus (gap G8 — 233 envelopes still not enough).

### Tier 2 (L40S/A100, ~$2-5/hr) — only after Tier 1 evidence

8. **r=32 doc-verifier** if augmentation hits a ceiling.
9. **TIES / DARE-TIES merge** experiments per `slm-learning-049` —
   merge v2 + math + tooluse into one adapter, see if it beats
   stacking.

## Don't burn the GPU on these without thinking

- ❌ "Train r=64 of multi-task" — already falsified at r=16, no rank
  fixes data shape mismatch
- ❌ "Train HumanEval-targeted" without first pulling code corpus —
  rank/scale doesn't fix data absence (gap G8)
- ❌ "More frontier comparison runs" without setting cost cap — the
  full matrix is ~$3 in API tokens
- ❌ "Train planning specialist locally" — 117k pairs is too large
  for 1660 Ti at the recipe we have; needs Tier 1 remote

## Data flywheel that should be running

Per `slm-learning-086`:

- Every Kael action → `.planning/.trace-events.jsonl`
- Every routing decision → `.planning/.gad-log/<date>-routing.jsonl`
  (gad-monorepo G1 closed — this is now populated)
- Every gad CLI call → `.planning/.gad-log/<date>.jsonl`
- Daily telemetry export → `data/raw/<YYYY-MM-DD>/events.jsonl`
  (operator-triggered today; gad-monorepo phase 147 will daemonize it)

The next session should run a fresh `gad telemetry export` from the
gad-monorepo + `python scripts/build_cohorts.py` to refresh
`data/cohorts/<latest>/`.

## Cross-Claude bridge

| Where | What |
|---|---|
| `.planning/handoffs/open/` | inbound from gad-monorepo Claude |
| `custom_portfolio/.planning/handoffs/open/` | outbound to gad-monorepo Claude |
| `gad bridge inbox` (CLI) | shipped by gad-monorepo last session |
| `~/.gad/bridge/` | provisional file-drop (older pattern) |

## What "tons of experiments" looks like

Realistic overnight cadence:

| Time | Job | Compute | Cost |
|---|---|---|---|
| evening | doc-verifier r=16 augmented (~50min) | local 1660 Ti | $0 |
| evening | tool-use sanity v2 (~50min) | local 1660 Ti | $0 |
| evening | constitution arm C eval (~30min) | local 1660 Ti | $0 |
| operator-fire | planning specialist r=16 (~2hr) | remote L4 | ~$1.60 |
| operator-fire | comparative matrix vs frontier (gated by API keys + cost cap) | n/a (API) | ~$3 |
| morning | r=32 doc-verifier IF augmented r=16 plateaus | local 1660 Ti | $0 |

That's 5-6 experiments per overnight cycle. Sustainable.

## What I'm NOT doing in this session (hand to next)

- Authoring the haiku augmentation script (~100 LOC, distillation pattern per
  `slm-learning-019`)
- Extracting planning holdout from the 117k cohort
- Writing `stage25_qwen15_planning_r16.yaml`
- Configuring HF Jobs CLI
- Running comparative matrix with frontier rows

These are clean, well-scoped tasks the next session can pick up cold.

## Decisions touched in last session

- `slm-learning-088` multi-task falsified
- `slm-learning-089` doc-verifier r=8 rejected
- `slm-learning-090` doc-verifier r=16 partial win
- `.planning/concerns/scaling-decisions.md` (this session)

## Reading order for cold pickup

1. `SOUL.md` → `narrative/souls/{common-dream,dr-stein,kael}.md`
2. This file
3. `.planning/concerns/scaling-decisions.md`
4. `.planning/codebase/audit-2026-05-07-data-quality-honest.md`
5. `models/REGISTRY.json`
6. `experiments/queue/pending/`
7. `gad snapshot --projectid slm-learning`

Total: ~10 min to fully cold-pickup the state.
