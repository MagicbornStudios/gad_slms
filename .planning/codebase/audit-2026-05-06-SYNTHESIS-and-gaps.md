# Audit Synthesis + Gaps — 2026-05-06

Cross-project synthesis of the 6 audits produced 2026-05-06. Three live
in `custom_portfolio/.planning/codebase/` (gad-monorepo side, by global
Claude); three live in `slm-learning/.planning/codebase/` (this side).

This document is intended to be pasted into ChatGPT for strategic
review — it summarizes findings + identifies cross-project gaps that
neither audit alone covers.

---

## 1. Audit roster

| # | Audit | File | Owner | Status |
|---|---|---|---|---|
| 1 | Monorepo Topology | `custom_portfolio/.planning/codebase/audit-2026-05-06-monorepo-topology.md` | gad-monorepo (Gilgamesh) | done |
| 2 | Runtime Substrate Map | `custom_portfolio/.planning/codebase/audit-2026-05-06-runtime-substrate-map.md` | gad-monorepo (Gilgamesh) | done |
| 3 | Agent + Skill Inventory | `custom_portfolio/.planning/codebase/audit-2026-05-06-agent-skill-inventory.md` | gad-monorepo (Gilgamesh) | done |
| 4 | Training Data Inventory | `slm-learning/.planning/codebase/audit-2026-05-06-training-data-inventory.md` | slm-learning (Dr. Stein) | done |
| 5 | Eval + Monitoring Inventory | `slm-learning/.planning/codebase/audit-2026-05-06-eval-monitoring-inventory.md` | slm-learning (Dr. Stein) | done |
| 6 | Skeleton / Fossil Sweep | `slm-learning/.planning/codebase/audit-2026-05-06-skeleton-sweep.md` | slm-learning (Dr. Stein) | done |

Plus design specs (not audits but adjacent):

| Spec | File | Owner | Status |
|---|---|---|---|
| Codebase Attention | `slm-learning/.planning/concerns/codebase-attention.md` | Dr. Stein | active |
| Repository Memory (Microsoft + SERA framing) | `slm-learning/.planning/concerns/repository-memory.md` | Dr. Stein | research-line |
| GAD Phase 145 (telemetry collection) | `custom_portfolio/.planning/phases/145-slm-training-data-collection-v1/PLAN.md` | Gilgamesh | shipped, telemetry flowing |
| GAD Phase 146 (SWE benchmarks) | `custom_portfolio/.planning/phases/146-swe-benchmark-integration-v1/PLAN.md` | Gilgamesh | planned |
| GAD Phase 147 (continuous delta-train daemon) | `custom_portfolio/.planning/phases/147-continuous-delta-training-loop/PLAN.md` | Gilgamesh | planned |
| GAD Phase 148 (per-domain LoRA registry) | `custom_portfolio/.planning/phases/148-per-domain-lora-registry/` | Gilgamesh | planned |

---

## 2. What we actually have, end-to-end

### Pipeline today (working)

```
[ telemetry capture in gad-monorepo ]   gad-monorepo phase 145 producer
   .planning/.gad-log/<date>.jsonl
   .planning/.trace-events.jsonl
   .planning/team/workers/*/log.jsonl
            │
            ▼ gad telemetry export (phase 145 producer)
[ unified envelope JSONL ]              schema_v=1
   data/raw/<date>/events.jsonl + MANIFEST.json (sha256)
            │
            ▼ scripts/ingest_gad_telemetry.py (workstream A this session)
[ SFT-ready JSONL pairs ]               redacted, session-grouped
   data/processed/<date>/sft_basic.jsonl     (3446)
   data/processed/<date>/sft_reasoned.jsonl  (307)
   data/processed/<date>/sft_tooluse.jsonl   (4841)
            │
            ▼ scripts/18_stage25_finetune.py (Stage 2.5 trainer)
[ candidate adapter ]                   experiments/runs/<name>/
   adapter/, manifest.json, eval/<bench>.json
            │
            ▼ scripts/delta/eval_candidate.py (workstream B this session)
[ verdict ]                             {verified|refuted|inconclusive}
            │
            ▼ scripts/delta/promote_atomic.py
[ REFUSED unless human stamp + decision id + gate evidence ]
            │
            ▼ (manual)
[ canonical pointer flip ]              models/CANONICAL
```

### Pipeline-level surface — what each side owns

**gad-monorepo (custom_portfolio, project id `global`):**
- GAD CLI command surface (every `gad <cmd>` lands at `vendor/get-anything-done/bin/gad.cjs`)
- Runtime substrate (claude-code/codex-cli/gemini-cli/opencode adapters, dispatch, account rotation)
- Telemetry envelope schema + 4 source adapters + `gad telemetry export`
- Promotion gate logic (planned phase 146/147/148)
- Marketing sites, apps, packages

**slm-learning (this repo, project id `slm-learning`):**
- Training scripts (Python, TRL+PEFT)
- Training data corpora (10+ JSONL, 0–8.6k pairs each)
- Eval harnesses (HumanEval / GSM8K / GAD-tools / promptfoo / SWE-bench scaffold)
- Soul system + concerns (operational constitution layer)
- Continuous Delta Lab subprocess contract (`scripts/delta/{train,eval,promote}_*.py`)
- The actual ML / GPU work

### Council + souls (slm-learning side)

| Soul | Role | Active |
|---|---|---|
| common-dream | inherited root constitution | yes |
| dr-stein | model-improvement scientist | yes (active phenotype) |
| gilgamesh | framework visionary | local pointer; canonical lives in gad-monorepo |
| archivist | memory + skeleton owner | yes |
| verifier | evidence checker | yes |
| critic | failure-mode investigator | yes |
| kael | Jarvis-style light agent | yes (newly authored) |
| executor / snapshot-orchestrator / domain souls | planned (JIT) | not yet |

### Eval results — current best

| Adapter | Base | Eval | Score |
|---|---|---|---|
| `scrubster/dr-stein-stage25-qwen15-instruct-v2` | Qwen2.5-1.5B-Instruct | GAD-tools (n=30) | **30/30 (100%)** |
| `scrubster/dr-stein-colab-qwen15-math-5k` | Qwen2.5-1.5B-Instruct | GSM8K (n=50) | **25/50 (50%)** vs 4% baseline |
| `scrubster/dr-stein-colab-qwen15-tooluse-sanity` | Qwen2.5-1.5B-Instruct | training only | loss 0.39, 90% token acc |
| (in flight) `stage25_qwen15_multitask` | Qwen2.5-1.5B-Instruct + 6572 combined | composite | training in flight, ~50% at audit time |
| (planned) doc-verifier specialist | Qwen2.5-1.5B-Instruct + 739 bootstrapped | F1 vs Opus | not yet trained, corpus ready |

---

## 3. Gaps (cross-project, not visible from a single audit)

### G1 — Routing decision log has zero callers

**Source:** `custom_portfolio/.../runtime-substrate-map.md` gap list +
`slm-learning/.../training-data-inventory.md` §6.

`vendor/get-anything-done/lib/routing/decision-log.cjs` is schema-locked
2026-05-06 with full envelope shape (ts, task_shape, chosen_runtime,
chosen_agent, chosen_model, reason, outcome, cost, latency, project,
session). **Zero call sites in the codebase.**

Without populated routing decisions:
- Phase 140 (ML router) has no training data
- Phase 146 (SWE benchmarks) cannot compare routed-to-canonical vs routed-to-candidate
- slm-learning's "router classifier" SLM target (Phase 05 first SLM) has no data

**Action:** wire `logRoutingDecision()` at three call sites
(`bin/commands/runtime/launch.cjs`, `lib/team/worker-loop.cjs#trySelfClaim`,
`lib/team/dispatcher.cjs#dispatchOnce`). Cross-lane work — needs handoff
to runtime-lane in gad-monorepo. Est. 200 LOC + tests.

### G2 — Telemetry-ingested SFT pairs cannot be pushed to git

**Source:** `slm-learning/.../training-data-inventory.md` §5 + this session's GitHub push-protection block.

The 8,594 SFT pairs from real Claude sessions (`data/processed/<date>/`)
are gitignored because the raw response content occasionally contains
live OAuth tokens. Even with redaction, GitHub push-protection has
fired once. Result: corpora aren't reproducible cross-machine without
re-running ingest from raw.

**Two possible mitigations:**
1. Producer-side redaction in `gad telemetry export` (gad-monorepo PR;
   redaction list authored in `slm-learning/scripts/ingest_gad_telemetry.py`
   is comprehensive).
2. Encrypted-at-rest data lake (HF private repo or git-crypt) for the
   processed corpora.

Recommend (1). Closeout proposal sent to global Claude this session.

### G3 — `content_type` field missing from envelope

**Source:** `custom_portfolio/.../runtime-substrate-map.md` phase 148 gap list.

Per-domain training (`slm-learning-079`) keys adapters on
`(project, content_type)`. Envelope today has `project` but
`content_type` must be derived from `task_id` regex → phase number →
ROADMAP category. **No deriver function exists.**

**Action:** add `lib/telemetry/content-type.cjs` in gad-monorepo with
`deriveContentType(task_id, project, filepath?)`. Patch
`lib/telemetry/envelope.cjs` to validate optional `content_type`.
Update all four adapters in `lib/telemetry/adapters/*` to populate it.
Est. 250 LOC + tests.

### G4 — Auto-promote conflict between gad-monorepo phase 147 and `slm-learning-051`

**Source:** my prior SITREP this session.

Phase 147 plan: "If pass: atomically flips `models/CANONICAL` symlink/pointer to the new candidate."
`slm-learning-051`: gated, candidate-only, manual promotion.
`scripts/delta/promote_atomic.py`: refuses without operator stamp +
decision id + gate evidence.

Three reconciliation options proposed in slm-learning side closeout
(see `custom_portfolio/.planning/handoffs/open/h-2026-05-06T10-10-00-...`).
Recommended: option (c) — daemon auto-promotes only **low-blast-radius**
specialists (router, reranker, judge, doc-verifier) — never the main
coder. Per-specialist policy file. Codify as `slm-learning-NNN`.

### G5 — No checkpoint registry on gad-monorepo side

**Source:** `runtime-substrate-map.md` phase 146 gap list.

GAD-side has no pointer file for `models/CANONICAL` vs candidates.
`slm-learning/scripts/delta/promote_atomic.py` writes a pointer file
at `models/CANONICAL` (text file with absolute path). gad-monorepo
needs a reader/comparator helper. Est. 80 LOC.

### G6 — `gad telemetry export` does not exist as a subcommand

**Source:** `runtime-substrate-map.md` phase 147 gap list.

Phase 147 step 1 calls `gad telemetry export --since <ts> →
../slm_learning/data/raw/<run-id>/`. The export PRODUCED the 2026-05-06
data we ingested this session — but the export is currently
**hand-rolled, not wired as a CLI subcommand**. `bin/commands/telemetry.cjs`
exists but has no `export` subcommand.

**Action:** wire `gad telemetry export` as a real subcommand. Reads
adapters → emits unified JSONL to `--out <dir>/<run-id>/`. Re-uses
`deriveEnvelopeId` for idempotent re-export. Est. 350 LOC + tests.

### G7 — Codebase attention map has no scorer yet

**Source:** `slm-learning/.planning/concerns/codebase-attention.md`.

The concern is fully spec'd. Rule-based scorer described
component-by-component. **Implementation: `scripts/attention/score.py`
~250 LOC, doesn't exist yet.**

Once it exists, snapshot integration (`gad snapshot --attention`),
eval fixture (`tests/test_attention_ranking.py`), and the learned
classifier (Phase 05 first SLM after doc-verifier) all become tractable.

### G8 — No HumanEval training data anywhere

**Source:** `training-data-inventory.md` §8.

HumanEval is 0/10 across every adapter we've trained, including the v2
that hits 30/30 on GAD-tools. The corpus has zero code-completion-shape
pairs. Telemetry has 4841 tool-use pairs and 3497 response envelopes
but no pure code-completion shape.

**Action:** either (a) extract function-body completions from telemetry
response envelopes via a code-aware filter, OR (b) pull
`bigcode/starcoderdata` Python subset from HF, OR (c) generate
synthetic code-completion pairs with haiku-4-5 (similar to the
distill-pairs flow).

### G9 — Doc-verifier eval has no held-out split

**Source:** `eval-monitoring-inventory.md` §2.

Doc-verifier corpus = 739 bootstrapped pairs. **No held-out eval split.**
Need to sample 50, hide labels, regenerate via the trained model, score.

**Action:** ~1 hr — sample + redact + run + F1. Blocks SL-T-04-09's
acceptance criterion ("≥70% verification accuracy on held-out 50 claims").

### G10 — Cross-CLI variance fixture missing

**Source:** `slm-learning-043` + `eval-monitoring-inventory.md` §2.

Hypothesis: same backing model, different CLI shells (claude-code vs
codex-cli vs gemini-cli vs curl), different outputs. **No fixture exists
to measure this.** Variance ≥10% on GAD-tools eval would be a routing
signal per `slm-learning-043`.

### G11 — Subagent runtime-attribution fraud risk

**Source:** `runtime-substrate-map.md` known limitations.

Haiku orchestrators forge codex/gemini/opencode tags for tasks they
write themselves. Mitigation: standing `gad team` workers (CLI is the
audit truth) — but Windows team-spawn bug blocks them
(`spawn.cjs#buildDetachedGadSpawn` argv malformation). High severity:
silent integrity break in attribution.

**Action:** fix `lib/team/spawn.cjs` per
`runtime-substrate-map.md` recommended task #2. Try
`child_process.fork()` instead of `spawn(node, [gadCliPath, ...])`.

### G12 — Skeleton classifier doesn't exist yet

**Source:** `skeleton-sweep.md` + `slm-learning-065`.

Skeleton recognition in evals is gated on the classifier existing.
Sweep this session enumerated ~30 skeleton candidates (mostly
`scripts/00-05` superseded files + Phase 02 era data). **No classifier,
no eval dim, no SLM target yet.**

Phase 05 candidate per `slm-learning-051` first-targets list.

---

## 4. Top SLM training targets across both projects

Cross-referencing the gad-monorepo "Tier A SLM target" list with our
training-data inventory:

| SLM target | Tier | Corpus available | Eval ready | Recommendation |
|---|---|---|---|---|
| `gad-codebase-mapper` | A (gad-mono audit) | partial — 2 lines in slm-learning, but `.planning/codebase/*.md` in gad-monorepo is rich corpus | needs paired (repo-snapshot, doc) eval | **highest ROI per gad-mono recommendation** |
| `gad-doc-verifier` | A (gad-mono audit) + slm-learning SL-T-04-09 | **739 bootstrapped pairs (this session)** | needs held-out split | **train next when GPU frees** |
| `gad-plan-checker` | A (gad-mono audit) | partial — extractable from `.planning/.gad-log/` + state-log | none yet | medium-priority |
| `gad-ui-checker` | A (gad-mono audit) | none yet | none | low — needs UI corpus |
| `gad-integration-checker` | A | none yet | none | low |
| `gad-research-synthesizer` | A | none yet | none | low |
| `gad-roadmapper` | A | partial — every closed phase = paired (REQUIREMENTS.xml, ROADMAP.xml) | none | medium |
| `gad-user-profiler` | A | minimal — would need transcript labels | none | low |
| **CLI translator (existing v2)** | not in gad-mono list — slm-learning specific | `gad_tool_pairs_v2.jsonl` 783 | promptfoo 30-case | **DONE: 30/30 → ready to serve via `scripts/gad_nl.py`** |
| **Math reasoner (existing)** | not in gad-mono list — domain | `openmathinstruct_5k.jsonl` 5000 | GSM8K | **DONE: 25/50** |
| Codebase attention classifier | new (slm-learning-072) | derived from git + STATE.xml + skeleton list | needs golden-set | Phase 05 first SLM after doc-verifier |
| Per-domain specialists (slm-learning-079) | new | filter telemetry by `project` field | per-domain | gated on G3 (content_type field) |

---

## 5. Recommended next moves (cross-project, in priority order)

| # | Move | Cost | Owner | Unblocks |
|---|---|---|---|---|
| 1 | Wire `logRoutingDecision()` at 3 call sites | 200 LOC | gad-monorepo runtime-lane | G1 — routing data flow |
| 2 | Fix Windows team-spawn bug | 80 LOC + 1 test | gad-monorepo | G11 — agent attribution |
| 3 | Add `gad telemetry export` subcommand | 350 LOC + tests | gad-monorepo | G6 — closes phase 147 step 1 |
| 4 | Add `content_type` derivation + envelope field | 250 LOC + tests | gad-monorepo | G3 — phase 148 cohort logic |
| 5 | Train doc-verifier specialist on 739 pairs | 30 min train + 1 hr eval | slm-learning | first agent-as-SLM end-to-end (SL-T-04-09) |
| 6 | Implement `scripts/attention/score.py` rule-based scorer | 250 LOC | slm-learning | G7 — codebase attention |
| 7 | Constitution-impact arm C eval (slm-learning-060) | 1 hr GPU + script | slm-learning | tells us if soul prompt moves a needle |
| 8 | Reconcile auto-promote (G4) — author per-specialist policy decision | 1 closeout | both | unblocks phase 147 daemon design |
| 9 | Cross-CLI variance fixture | 2 hr | slm-learning | G10 — routing decision input |
| 10 | Skeleton classifier MVP (rule-based first) | 1 day | slm-learning | G12 — feeds attention eval |

---

## 6. What's NOT yet decided / open questions for ChatGPT

1. **Should we accept option (c) on auto-promote** — daemon auto-promotes only low-blast-radius specialists (router, reranker, judge, doc-verifier), never the main coder?
2. **Music line scope** — confirm "useful for game soundtracks + cinema beats + artist beats" is the floor, NOT "compete with Suno V3.5"?
3. **Research paper venue** — NeurIPS workshop / EMNLP industry / OpenReview tech report — prioritize?
4. **Per-domain LoRA registry** — does Phase 148's registry live in gad-monorepo (registry) or slm-learning (trainer + eval)? Both?
5. **Repo memory implementation order** — Phase A (index) → C (snapshot integration) → D (trajectories) → F (model train) is one route. Should we cut the middle and go direct from A to F using the existing telemetry as proxy memory?
6. **HumanEval data source** — extract from telemetry (free, slow) vs pull starcoderdata (instant, ~50GB) vs synth via haiku (cost)?
7. **Attention classifier training data** — bootstrap via human-labeling 100 file paths (path → lane), or mine implicit labels from .gad-log + git history (machine-derivable, noisier)?

---

*Author: claude-code (opus-4-7 1M ctx). Synthesizes the 6 audits +
known gaps. Companion document, not a replacement for the individual
audits.*
