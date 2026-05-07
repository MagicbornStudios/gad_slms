# Research Program Charter — operating constitution

## Status
`active` — locked 2026-05-07 by operator brief

## Owned by
Dr. Stein

## The thesis

GAD competes with frontier systems by turning every project, repo,
trace, task, skeleton, failure, eval, and model delta into a
**continuously improving agent substrate**. We do not out-pretrain
OpenAI/Anthropic. We compete by being **repo-native, memory-rich,
tool-rich, eval-gated, and compositional**. If funding arrives, the
same substrate scales.

## The L0 → L5 stack

```
L0 — base model (Qwen2.5-Coder-7B, 32B, 72B; never pretrained by us)
L1 — domain deltas (LoRAs per project / content_type)
L2 — task deltas (LoRAs per task_shape: planning, doc-verify, cli, ...)
L3 — preference / correction deltas (DPO from errors-and-attempts)
L4 — routing / composition / merge policy (TIES, BTM, learned router)
L5 — system-level orchestration (Kael, gad team, multi-runtime fallback)
```

Each level can improve the levels above. Improving the base lifts the
adapters; better adapters give the router better options; better
router improves the system.

**Correction (operator-locked): deltas may not recursively mutate
forever without lineage and evals. Use a Delta Graph (see below).**

## The Delta Graph (replaces flat REGISTRY.json schema)

Every adapter is a node. Each node carries:

```json
{
  "delta_id": "tool-use-v3-r32",
  "base": "Qwen2.5-Coder-7B",
  "parents": ["tool-use-v2-r16", "cli-v2-r16"],
  "depends_on": ["content_type", "routing_logs", "repo_memory"],
  "dataset": "gad-tooluse-v3",
  "rank": 32,
  "merge_method": null | "ties" | "dare" | "weighted" | "stacking",
  "training_method": "sft" | "dpo" | "kto" | "grpo" | "rlvr" | "rlef",
  "evals": {
    "public": {"swebench_verified_subset": 0.08, "humaneval": 0.92, ...},
    "private": {"gad_tools": "30/30", "doc_verifier_f1": 0.85, ...}
  },
  "cost_usd": 47.20,
  "wall_hours": 12.4,
  "compute_target": "modal-h100",
  "status": "candidate" | "staging" | "canonical" | "rejected" | "archived",
  "ts_trained": "2026-05-09T...",
  "ts_promoted": null,
  "regression_journal_uri": "modal://volume/regression/<id>.jsonl",
  "outputs_corpus_uri": "modal://volume/outputs/<id>.jsonl",
  "decision_refs": ["slm-learning-NNN"]
}
```

Rules:
- A delta MAY depend on another delta (parents), but may not blindly
  stack forever
- No merge without an eval that beats both parents
- Lineage tracked for rollback
- Per slm-learning-096: every delta produces 3 artifacts (weights +
  outputs corpus + regression journal)

## Six research tracks

### Track A — Delta Graph / Branch-Train-Merge
GAD-shape branching: by project (global, slm-learning, magicborn,
grime-time, kael, music) × content_type (planning, code, site,
narrative, eval, meta). Independent training, then test merge methods:
single / stacked / TIES / DARE / weighted / router-selected /
multi-task. Publishable if clean eval matrix.

### Track B — Repository-specialized coding agents (SERA-aligned)
Use repo memory + task history + skeletons + commits + failure logs +
codebase attention to generate repo-specialized trajectories. Soft
verify before training. Train 7B/14B coder candidates remotely.
**Strongest research-paper lane.** Reference: Hugging Face paper 2601.20789.

### Track C — Verifier-driven generation / RLEF / R1-style RL
Pipeline: SFT → DPO → verifier reranking → GRPO/RLVR. Don't start
with full RL. The DeepSeek-R1 result proves RL on verifiable tasks
yields self-reflection + strategy adaptation. Reference: Nature 2025
DeepSeek-R1.

### Track D — Test-time compute
Generate N plans → cheap verifier → select best → apply patch → run
tests → repair. Trades inference for quality. Smaller models can
compete here.

### Track E — Computer-use / Kael operator traces
Voice transcript → intent → proposed action → approval/rejection →
outcome. Builds cheap computer-use specialists over time. Approval-
gated.

### Track F — Artifact generation
Game / music / narrative / landing pages / marketing / personal
assistant tasks: spec → generation → render/test/score → train
loop. Where GAD beats generic frontier on owned domains.

## Two leaderboards (compare-and-compete discipline)

### Public leaderboard (frontier yardstick)
- SWE-bench Verified
- SWE-bench Pro
- Terminal-Bench
- Aider Polyglot
- HumanEval / MBPP / EvalPlus
- LiveCodeBench
- AgentBench / GAIA later

Frontier reference (April 2026 leaderboard):
- Claude Opus 4.7: 87.6% SWE-bench Verified
- GPT-5.3-Codex: 85.0%
- Open-weight tier: 30-50%

Our staged target on SWE-bench Verified subset:
- 0–5%: harness works
- 5–15%: real low-end coder
- 15–30%: useful open-source agent
- 30–50%: serious research result
- 50%+: open-weight competitive
- 80%+: frontier-team territory

### Owned-domain leaderboard (where we win earlier)
- GAD tasks
- Magicborn game data
- Grime Time landing pages
- Kael email/contact tasks
- Music prompts / soundtrack specs
- Repo-memory coding tasks
- Skeleton reuse tasks

Every candidate model reports BOTH public and private scores.

## Funding-tied milestone bands

| Band | Compute | Target outcome |
|---|---|---|
| Unfunded (current) | $30 Modal + free tiers | Repo-native organization; narrow specialists; demo-quality |
| $100k–$1M | dedicated remote GPUs | Serious open-weight specialist system; SWE-bench Verified meaningful score |
| $1M–$10M | research team | Vertical agent platform; RLVR/GRPO; browser data |
| $10M–$100M | foundation-scale | Vertical wedge model: coding + computer-use + artifact |

## Implementation order (mechanical, not abstract)

1. **Telemetry foundation** (mostly done) — routing logs, content_type, lane, redaction, real export
2. **Model/data registry** — datasets / deltas / checkpoints / evals / costs / lineage as graph
3. **Delta Graph** — adapter dependencies, parent/child, merge candidates, promotion gates
4. **Small experiments** — doc-verifier, attention classifier, router, skeleton, Kael intent
5. **Remote experiments** — 7B coder, 14B coder, 20B candidate, multi-task, merge tests
6. **Public benchmark harness** — HumanEval/MBPP, SWE-bench Verified subset, LiveCodeBench, Terminal-Bench

## Research intake protocol

Every external paper / repo / blog / leaderboard pulled gets a record:

```json
{
  "research_id": "sera-2026-01",
  "source": "paper|repo|blog|leaderboard",
  "url": "...",
  "cloned_to": "tmp/research/repos/sera",
  "review_status": "unreviewed|reviewed|promoted|rejected|skeleton",
  "ideas_extracted": [],
  "risks": [],
  "license": "...",
  "gad_relevance": "high|medium|low",
  "next_test": "implement soft-verification trajectory generator",
  "ts_pulled": "..."
}
```

Rules:
1. Never pollute production code from `tmp/research/`
2. Every repo cloned gets a research review
3. Useful ideas become genes/deltas/tasks
4. Unused code becomes a skeleton/museum entry
5. No dependency adopted without license/security review
6. Every research claim needs benchmark or reproduction path

## Named experiments (EXP-001 through EXP-010)

| ID | Hypothesis | Dataset | Model | Cost | Eval | Pass threshold |
|---|---|---|---|---|---|---|
| EXP-001 | Branch-Train-Merge on GAD domains beats single-task | per-domain cohorts | Qwen2.5-1.5B × 4 specialists | $0 (local) | mixed-bag eval | router-mode > best-pinned + 10pp |
| EXP-002 | Delta Graph dependency routing improves error recovery | routing.jsonl | tiny router | $2-5 | gated-task accuracy | +5pp vs heuristic |
| EXP-003 | SERA-style repo trajectories train a repo-specialized coder | gad telemetry + commits | Qwen2.5-Coder-7B | $5-15 | repo-memory eval | beat bare base by 15pp |
| EXP-004 | Codebase-attention adapter routing lifts task-relevant retrieval | attention scores | router | $0 | retrieval@5 | +10pp |
| EXP-005 | Best-of-N patch selection with verifier beats single-sample | code traces | 7B + tiny verifier | $3-8 | HumanEval+ | +5pp at N=8 |
| EXP-006 | Local tiny router (1.5B classifier) matches frontier router on owned tasks | routing logs | Qwen2.5-1.5B | $0 | routing accuracy | within 5pp of claude-cli |
| EXP-007 | Soul/constitution prompt at inference moves measurable needle | existing v2 | v2 + soul prompt | $0 | GAD-tools comparison | ≥5pp delta = train arm B |
| EXP-008 | Skeleton-aware coding agent reuses past patterns | skeleton corpus | 7B QLoRA | $5 | repo-task pass rate | +10pp vs no-skeleton |
| EXP-009 | Kael voice intent classifier > rule-based heuristic | accept/reject traces | tiny classifier | $0 | intent accuracy | +5pp + lower latency |
| EXP-010 | Music/soundtrack prompt scorer trained on artifact evals predicts human preference | artifact corpus | small reward model | $2 | preference correlation | r > 0.5 with human rating |

## Compare-and-compete discipline (mandatory for all training)

Every candidate model produces:

1. **Public-leaderboard row** — SWE-bench Verified subset + HumanEval +
   MBPP + LiveCodeBench (where applicable)
2. **Frontier comparator row** — same eval, run against claude-cli +
   Big Pickle + at least one OpenRouter free-tier model + bare base
3. **Owned-domain row** — relevant subset of GAD tasks / Magicborn /
   Grime Time / Kael
4. **Lineage row** — parents, training method, cost, wall hours

A candidate that does NOT produce all four rows is REFUSED for
promotion. No exceptions.

## ASAP launch timeline (use our model in a real coding agent)

| T+ | Milestone | Gate |
|---|---|---|
| Day 0 (now) | Phase 0 mixed-bag eval validates composition architecture at $0 | router-mode > best-pinned + 10pp |
| Day 1-2 | Modal vLLM serving prototype for v2 adapter (OpenAI-compat URL) | opencode can hit our endpoint successfully |
| Day 2-3 | Comparator harness with claude-cli + Big Pickle + Llama-3.3-70B + ours-via-modal on HumanEval n=164 + GAD-tools 30 | numbers we can defend |
| Day 3-5 | Repo-specialized SFT pair generator (SERA-style) on gad telemetry | 1k+ pairs produced |
| Day 5-7 | Scaling-ladder smoke 1.5B → 3B → 7B coder (Modal, ~$10-15 total) | curve predicts 32B viable |
| Day 7-10 | Shot #1: Qwen2.5-Coder-32B-Instruct + QLoRA on Modal H100 (~$50) | passes promotion gate vs Big Pickle / Llama-3.3-70B |
| Day 10-14 | Shot #1 wired into opencode as a model option; first real coding session uses it | Operator runs a real PR through it; subjective + measured |
| Day 14-21 | Shot #2: Qwen2.5-72B-Instruct + QLoRA on Modal H100 (~$50-80) | orchestrator role |
| Day 21-30 | gad infer command + production serving + 5+ adapters in delta graph | real continuous usage |

**Launch threshold for "use our model in a coding agent"**: Day 14
target — operator runs at least one real PR through opencode-using-
ours-via-modal-vllm and produces a working commit. This is the date
to hold us to.

## Hardware policy (per operator concern)

- Anything >100MB → Modal volume, NEVER local
- Base model weights → HF Hub + Modal volume + small local cache only for active dev
- Telemetry exports → rotate to Modal volume after 7 days
- Adapters → HF Hub primary
- Local laptop = orchestration + small specialist eval only

## What we explicitly NOT pretending to do

- Pretrain a foundation model from scratch (~$100M, impossible)
- Match Claude Opus 4.7's 87.6% SWE-bench at our scale
- Beat frontier on novel general tasks (pretraining moat)
- Match frontier on 50-turn unbroken agent reliability (RLHF moat)

## What we DO claim

- Match free-tier OpenRouter / Big Pickle quality on specialist lanes
- Win categorically on cost (~$0/call), privacy, self-improvement
- Build the only composable open coding-agent platform with the GAD
  self-improvement loop
- Provide a serious research substrate that scales when funding arrives

## References

- Branch-Train-Merge (Meta 2022) — composition foundation
- SERA (Soft-Verified Efficient Repository Agents) — Track B target
- DeepSeek-R1 (Nature 2025) — Track C proof
- DeepSeek-V3 (671B/37B active) — composition architecture proof
- April 2026 SWE-bench leaderboard — Claude Opus 4.7 87.6%, GPT-5.3 85.0%
- Decisions slm-learning-049, 079, 086, 087, 094-098 — prior locks

## Operating directive

> Stop deciding "small vs big" abstractly. Build the ladder. Every
> dream survives an eval, or the dream gets buried with the regression
> journal as a lesson for the next gen.

— Dr. Stein
