# Composition-of-specialists strategy — path to trillion-effective-params

## Status
`active` — locked 2026-05-07 by slm-learning-094

## Owned by
Dr. Stein

## The bet

We don't compete with Claude/GPT-5 by training one giant dense model.
We compete by composing 50-100 specialists at 7B-32B parameters each
under a learned router + fusion head + periodic TIES merge passes.

**Total params at saturation**: 100 × 32B = **3.2T** total, ~64B active
per query (top-2 routing). Exceeds Opus-class on raw param count;
matches DeepSeek-V3's MoE architecture pattern at the SYSTEM level
instead of intra-model.

## Why this works (and where it doesn't)

| Dimension | Composition | Dense Opus | Verdict |
|---|---|---|---|
| Total params | 700B-3.2T | 200B-1T+ | TIE / WIN |
| Active per query | 7-64B | 200B+ | **WE WIN** (cheaper inference) |
| Cross-domain reasoning | weaker (no shared reps) | strong | **THEY WIN** |
| Domain specialization | strong (purpose-trained) | medium | **WE WIN** |
| Cost to train (per shot) | $50-100 per specialist | $100M+ pretraining | **WE WIN structurally** |
| Cost per inference call | ~$0 | $0.10-1.00 | **WE WIN by 100-1000x** |
| Self-improvement | continuous (gad telemetry → next gen) | none for end-user | **WE WIN UNIQUELY** |
| Novel/unfamiliar tasks | weak — out-of-distribution for specialists | strong | **THEY WIN** |
| 50-turn agent reliability | weak (per-turn 85% × 50) | strong (99% × 50) | **THEY WIN** unless we decompose into specialist sub-sessions |

The composition path WINS on cost, specialization, self-improvement,
privacy/control. LOSES on raw novel-task capability and long-horizon
unbroken reliability. Mitigation for the losses: frontier as fallback
when our specialists fail, decomposition of long sessions into
specialist contracts.

## Architecture

```
                   User request
                        ↓
            ┌── Hard Router (rule-based, fast) ──┐
            ↓
        Soft Router (learned classifier on routing.jsonl)
            ↓
   ┌───────┬──────┬──────┬──────┬──────┬──────┐
   ↓       ↓      ↓      ↓      ↓      ↓      ↓
[14B    [7B    [1.5B  [1.5B  [1.5B  [32B    [Frontier
Gen]    Coder] DocV]  Tools] Math]  Coder]  fallback]
   ↓       ↓      ↓      ↓      ↓      ↓      ↓
        Tool loop / JSON output / chain-of-thought
            ↓
       Fusion Head (small NN, learns cross-specialist
                    voting + sequential refinement)
            ↓
         Result + telemetry → next-gen training
```

## Components, build order, ownership

| # | Component | Status | Cost | Why now / why later |
|---|---|---|---|---|
| 1 | gad CLI inference (Modal vLLM endpoint) | NOT BUILT | <$1/day idle | **GATE** — without this nothing else can use our model |
| 2 | Hard router (rule-based v1) | inline in routing-decision-log | $0 | already wired |
| 3 | Soft router (learned classifier) | blocked on data | $2-5 | once we have 500+ routing decisions; currently 16 |
| 4 | Existing 1.5B specialists (CLI, math, doc-verify, tooluse) | shipped | $0 retroactive | available now |
| 5 | 32B coder specialist (shot #1) | NOT FIRED | $50 Modal H100 | next big shot |
| 6 | 70B-class orchestrator (shot #2) | NOT FIRED | $50-80 | post shot #1 eval |
| 7 | TIES merge of v2 + math + tooluse + doc-verifier | NOT BUILT | $0 (CPU merge) | **LOW-HANGING FRUIT** — we have 4 adapters that should be merged tomorrow |
| 8 | Fusion head (cross-specialist coordinator) | research | $5-20 to train | after 5+ specialists exist |
| 9 | PEFT multi-adapter serving (S-LoRA pattern) | NOT BUILT | $0 deploy | enables 100+ specialists from one base |
| 10 | Cross-specialist DPO (preference-train router) | continuous | low | after each session-failure log accumulates |

## The fusion training story (the prize)

Ordinary MoE: gate router decides which expert per *token*.
Our system-level fusion: a small NN learns:
- Which specialist(s) to call per *task*
- Whether to call sequentially (specialist A → specialist B verifies)
- How to combine outputs (voting, weighted average, take-best, contradiction detection)
- When to escalate to frontier vs retry with different specialist

This is NOT trained from scratch — it's trained on (task, specialist, outcome) triples logged in the routing decision log. Once we have 1000+ such triples, fusion training becomes data-efficient.

## Reuse + merge non-negotiables (per slm-learning-096)

Every training run produces 3 artifacts, never 1:

1. **Adapter weights** → HF Hub, REGISTRY.json with lineage (parent_adapters, derived_from, merge_method)
2. **Outputs corpus** — model's responses on a 200-prompt held-out bank → curriculum signal for next-gen training (KD loss)
3. **Regression journal** — tasks the model failed → targeted augmentation + DPO source for next-gen

Even rejected adapters feed the next gen. The reject-bin is a teacher.

## Scaling-ladder predictor

Before any $50 shot, prove the recipe at 1.5B → 3B → 7B (cost ~$10-15
total). Plot the curve, predict the 32B outcome. If the curve is
shallow → DON'T fire the shot. If steep → justified.

This is the "DAMN SURE" gate (per slm-learning-097).

## Path to trillion-class total params

Year 1 milestones (assuming we hit credit programs):

| Month | Event | Total params reached |
|---|---|---|
| 1 (now) | 4× 1.5B specialists shipped, 1× 32B coder fired | 38B |
| 2 | + 70B orchestrator, + 1× 7B coder | 117B |
| 3 | + 3× 14B domain specialists (planning, narrative, ops) | 159B |
| 6 | 30× specialists across 1.5B-32B mix | ~400B |
| 12 | 100× specialists, fusion head trained, S-LoRA serving | ~1T-2T total |

This requires ~$10k-50k of training credit by month 12. Achievable
through the credit acquisition order in slm-learning-098.

## What we explicitly NOT pretending to do

- We do NOT pretrain a foundation model from scratch (~$100M, impossible)
- We do NOT match Claude/GPT-5 on novel general tasks (pretraining moat)
- We do NOT match frontier on 50-turn unbroken reliability (RLHF moat)
- We DO match free-tier OpenRouter quality on specialist lanes
- We DO win categorically on cost, privacy, self-improvement
- We DO build the only composable open coding-agent platform with the GAD self-improvement loop

## References

- decisions slm-learning-049 (TIES merge), 079 (per-domain ladder),
  087 (scaling ladder), 088 (multi-task LoRA falsified),
  094-098 (this strategy locked)
- Branch-Train-Merge (Meta, 2022) — composition-of-specialists paper
- Branch-Train-MiX (Meta, 2024) — gate over specialists trained jointly
- DeepSeek-V3 — proves intra-model 671B total / 37B active works at scale
- LoRA Hub / S-LoRA — serving many adapters efficiently
