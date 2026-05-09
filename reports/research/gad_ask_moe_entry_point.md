# gad ask: Universal Entry Point + MoE Soul Router

**Date:** 2026-05-09
**Decision refs:** GLOBAL-D-324, GLOBAL-D-325, GLOBAL-D-330, GLOBAL-D-332
**Dataset refs:** tool_use_preference.schema.json, decision_preference.schema.json

---

## 1. Bottom Line

`gad ask` is the single CLI surface an agent uses to query any general knowledge about the GAD ecosystem — codebase structure, decisions, handoffs, history, patterns — before it forage files. Kael is the first soul to be routed through it; MoE routing across the full soul family follows once multiple adapters are promoted.

---

## 2. The Vision

> "rather than read X files for data, an agent could have done `gad ask ""` and gotten specific domain knowledge about the GAD ecosystem and the codebase"

Every time an agent does a Glob+Read cascade to answer a question it could answer semantically, it spends 5-50x the tokens and 3-10x the wall time of a single `gad ask` call. The trace logs already show this pattern repeatedly: agents Globbing source trees, Grepping for patterns, Reading 4-6 files, then synthesizing — when the answer was indexable.

The deeper claim: `gad ask` knows *why* files are where they are, what probably does not need to be there (it has the history of decisions in its training), and can reason about that history faster semantically than any file-system search can match structurally. A model trained on the full decision corpus + handoff history + state-log entries is a faster lookup than a raw code search because it has already compressed the rationale, not just the text.

This is the consumer-facing API over the SLM training pipeline that has been running since phase 108. The pipeline produces the knowledge; `gad ask` is the mouth.

---

## 3. Architecture

```
gad ask "<query>" [--soul <id>] [--max-tokens N] [--cost-cap $X]
  │
  ├── 1. classify task_shape
  │         tool_action       → "what command do I run to stamp a task?"
  │         decision_lookup   → "why did we disable dual-generate?"
  │         repo_state        → "what phase is the desktop app in?"
  │         code_search       → "where does worker-loop call rotation?"
  │         history_recall    → "what happened to the OMX system?"
  │         reasoning         → "is this approach consistent with D-330?"
  │         onboarding        → "what is the GAD loop?"
  │
  ├── 2. route via soul_routes.toml
  │         today: hardcoded → Kael adapter (Qwen2.5 base + SLM tooluse adapter)
  │         phase 2: MoE router classifies → picks soul by task_shape + specialization
  │         phase 3: multi-soul ensemble for cross-cutting queries
  │
  ├── 3. soul-aware retrieval (RAG)
  │         ├── decision_dataset      (.planning/DECISIONS.xml → decision_preference pairs)
  │         ├── handoff_dataset       (.planning/handoffs/ → closed + open)
  │         ├── delta_packet_dataset  (slm_learning/data/delta_packets/)
  │         ├── retain_bank           (per-soul retain bank: slm_learning/data/retain-banks/<soul>/)
  │         └── repo embedding index  (file paths + summaries, lazy-built on first call)
  │
  ├── 4. compose context window
  │         RAG-trim to token budget (default: 4096 context for fast Kael, 8192 for deep queries)
  │         inject active soul's constitutional_principles as system prefix
  │         include task_shape in the prompt so the model knows what kind of answer to give
  │
  └── 5. soul-routed inference
            base_model + adapter_stack from soul_routes.toml
            → returns: answer, citations (decision/handoff/file refs), cost_usd
            → logged to .planning/.gad-log/<date>.jsonl with tool="gad ask"
```

The retrieval step is cheap. The inference step on Kael's SLM (1.5B-3B) is cheap. The whole call should cost under $0.001 for 95% of queries. That is 10-100x cheaper than a Glob+Read cascade that hits the frontier API.

---

## 4. Phase 1 — Kael-Only

Single soul route. All queries go to Kael. No routing model needed — `soul_routes.toml` is a hardcoded entry:

```toml
[routes]
default = "kael"

[souls.kael]
base_model = "Qwen/Qwen2.5-1.5B-Instruct"
adapter_stack = ["slm_learning/models/kael-1-1.5b-sft-tooluse"]
max_tokens_default = 512
cost_per_1k_tokens = 0.00012
task_shapes = ["tool_action", "decision_lookup", "repo_state", "code_search", "history_recall", "reasoning", "onboarding"]
```

Kael handles all query types in phase 1. The goal is to establish the habit — every agent in the ecosystem calls `gad ask` first, gets a useful answer, and stops doing file foraging. Quality does not need to be perfect; it needs to be good enough that the agent trusts the call over a raw filesystem search.

Tool-use DPO training (tool_use_preference pairs) explicitly marks `gad ask` as the chosen branch and file-foraging cascades as the rejected branch. This preference data is fed back into Kael's training so the next generation of Kael prefers to call itself over foraging.

---

## 5. Phase 2 — MoE Routing

When two or more souls have promoted adapter stacks (Kael + Gilgamesh minimum), the router activates.

The routing model is small — a classifier that takes the query + task_shape and picks a soul. It does NOT need to be a full Kael invocation; a 50M-parameter classifier or even a bag-of-words rule-table is sufficient for the task_shape → soul mapping.

```
task_shape → primary soul

tool_action       → Kael        (trained on gad CLI surface + tool-use DPO)
decision_lookup   → Gilgamesh   (trained on DECISIONS.xml + design corpus)
repo_state        → Kael        (trained on handoffs + state-log entries)
code_search       → Kael        (trained on monorepo corpus + file summaries)
history_recall    → Gilgamesh   (trained on full decision + error + handoff history)
reasoning         → Gilgamesh   (trained on architectural rationale corpus)
onboarding        → Kael        (trained on CLAUDE.md + skill bodies + AGENTS.md)
```

Pattern ref: Mixtral-8x7B MoE (sparse gating, top-2 expert activation). Qwen-MoE (32 experts, 6 active). For the GAD soul router, the "experts" are not transformer FFN layers but full inference calls against different soul adapters. The routing is coarse-grained (one call to one soul), not token-level mixture. This keeps the routing simple and auditable — the log shows which soul answered which query, attribution is clean.

The router itself is a lightweight gating model trained on the decision_preference + tool_use_preference pairs, where the label is which soul produced the better answer for each query type.

---

## 6. Phase 3 — Multi-Soul Composition

For cross-cutting queries that span soul specializations — "is this architectural decision consistent with our tooling philosophy and with how Kael's chat surface works?" — phase 3 routes to both souls and merges.

Merge protocol (proposed, not locked):

1. Route query to both souls in parallel.
2. Each soul returns answer + citations + confidence_score.
3. Merge step: Gilgamesh answer provides the strategic frame (first paragraph). Kael answer provides the implementation detail (second paragraph + tool citations). Citations are union-deduped.
4. If answers contradict, surface the conflict explicitly rather than silently picking one.

Phase 3 is a research phase. The merge protocol is the open question — see section 10.

---

## 7. CLI Surface (Next Phase — Sketch Only)

```
# Core query
gad ask "<query>"
gad ask "<query>" --soul kael
gad ask "<query>" --max-tokens 1024 --cost-cap 0.005
gad ask "<query>" --cite-only          # return citations only, no full answer
gad ask "<query>" --json               # machine-readable output

# Dry-run / debug
gad ask --route "<query>"              # print soul + task_shape without running inference
gad ask --dry-run "<query>"            # build context window, print it, don't call model
gad ask --explain "<query>"            # show retrieval results before inference

# History
gad ask history                        # all past asks with cost
gad ask history --soul kael --limit 20
gad ask history --since 2026-05-08

# Index management
gad ask index --status                 # show repo embedding index freshness
gad ask index --rebuild                # explicit rebuild (expensive; not auto)
gad ask index --rebuild --scope vendor/get-anything-done  # partial rebuild
```

None of this is implemented. The CLI surface is a spec for the phase that adds `gad ask` to the binary.

---

## 8. Datasets That Train gad ask Itself

The training pipeline already exists (`vendor/get-anything-done/lib/datasets/curator.cjs`). The new datasets plug into it as additional `dataset_block` entries.

| dataset_block | source | trains |
|---|---|---|
| `tool_use_preference` | .trace-events.jsonl + mine_tool_use_preference_pairs.py | Prefer cheap tool path; prefer gad ask over file foraging |
| `decision_preference` | DECISIONS.xml + mine_decision_preference_pairs.py | Know what was decided, why, what was rejected, what the anti-pattern is |
| `gad_command_surface` | data/gad_command_surface.txt (exists) | Know the full gad CLI surface |
| `agent_corpus_global` | data/agent_corpus_global_*.jsonl (exists) | Know the monorepo structure |
| `retain_bank_kael` | data/retain-banks/kael/ | Kael's voice, constitutional principles, standing rules |
| `delta_packets` | data/delta_packets/ | Recent codebase changes Kael should know about |
| `error_corpus` | ERRORS-AND-ATTEMPTS.xml | Know what has gone wrong and the rules derived from those failures |

The critical new entries are the two preference schemas. Without them, Kael may know the CLI surface but will not have a preference signal teaching it to call `gad ask` as a first resort. The DPO signal is what makes the behavior a preference, not just a capability.

---

## 9. Standing Rule the Dataset Enforces

Any agent operating in the GAD ecosystem that needs general knowledge about the codebase, decisions, handoffs, history, or recurring patterns MUST call `gad ask` before doing file-system foraging.

Tool-use DPO rates file-foraging cascades (Glob+Read+Read+Grep sequences) as the rejected branch. Kael's training will internalize this as a strong prior: when I need to know something about this codebase, my first move is `gad ask`, not `Glob`.

This rule applies to ALL runtimes that have shell access. Claude-code subagents, codex workers, gemini workers — all of them can call `gad ask` because it is a CLI binary, not a Claude-specific tool. This makes the rule portable across the entire multi-agent substrate.

The standing rule does NOT prohibit file-system tools. It sets a priority ordering: semantic lookup first, structural search as fallback when the semantic index does not have the answer.

---

## 10. Open Questions

**Q1 — Index lifecycle.** Should `gad ask` lazy-build the repo embedding index on first call (transparent, slow first call, fast thereafter) or require explicit `gad ask index --rebuild` (transparent cost, requires operator action before first use)? The lazy approach is better for new operators; the explicit approach is better for CI where first-call latency is a contract. Recommend: lazy with a warning that prints estimated build time + cost.

**Q2 — Multi-soul merge protocol.** Phase 3 composition when two souls contradict each other — pick the higher-confidence answer, surface the conflict explicitly, or route to a meta-soul that adjudicates? No answer yet. Operator decision required before phase 3 is opened.

**Q3 — Cost cap defaults.** What is the per-call cost cap that ships as the default? If Kael's SLM is running locally (zero marginal cost), the cap is irrelevant. If it routes to the Anthropic API as fallback, the cap matters. Recommend: $0.01 per call, $0.10 per session, configurable via gad-config.toml.

**Q4 — Claude-code shell-out vs SDK direct.** Should a claude-code agent shell out to `gad ask` (subprocess, easy, audit trail automatic) or call the underlying inference SDK directly (lower latency, no subprocess overhead)? Subprocess is the right default — it keeps the audit trail clean and means `gad ask` works identically from all runtimes. SDK-direct is an optimization for high-frequency use cases that can be added later without breaking the contract.

**Q5 — Embedding index scope.** Should the repo embedding index cover vendor/get-anything-done (the framework) as a first-class citizen alongside apps/* and packages/*? Operator confirms the GAD framework codebase is a primary knowledge domain, not a third-party library. Recommend: yes, index vendor/get-anything-done at the same priority as apps/desktop.

**Q6 — Cross-project routing.** `gad ask "what is the SLM training pipeline?"` — does this route to the global project's Kael or to slm-learning's Kael (if it has a separate adapter)? Initial recommendation: single Kael adapter covers all projects; per-project routing is a phase 3+ consideration.

---

*This document is a design artifact, not an implementation plan. No gad ask code exists. The next step is a phase to add `gad ask` as a `commander` subcommand in vendor/get-anything-done, initially backed by a simple semantic search over DECISIONS.xml + gad_corpus.txt with no model inference — pure retrieval. Model inference is added in the following phase once the retrieval quality is validated.*
