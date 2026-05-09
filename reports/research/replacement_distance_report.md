# Replacement Distance Report — per-tier assessment

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Decision refs:** slm-learning-103, 168, 197, 199, 207, 208, 210, 212,
213
**Companion docs:** `reports/research/big_base_replacement_track.md`,
`benchmarks/frontier_open_replacement_matrix.yaml`,
`reports/research/teacher_species_policy.md`

This report scores each of the operator's four tiers against the
GAD-owned 5-tier model stack. "Distance" is the realistic gap between
the owned stack today and a state where the owned stack handles the
tier's daily work, with frontier (Opus) escalations only on the hard
residual.

We do **not** target frontier parity. Per slm-learning-199, Kael's
moat is integration depth × speed × cost. The replacement claim is
about routing: owned stack handles 70-90% of operator routine load,
frontier handles the residual, and the residual shrinks over time
as Gateway accumulates correction data (slm-learning-208).

## Tier 1 — routine GAD work

**Examples:** decision summary, handoff body, planning-doc edit,
short evals digest, paraphrase, tool-action JSON dispatch, simple
ROADMAP/UAT updates, todo capture.

**Distance: NEAR.** This is the tier with the highest routing leverage
and the lowest model demand. 1.5B + 7B can already do most of this if
wired through:

- Gateway router with task-shape detection (slm-learning-208)
- Tool-action JSON specialist adapter (already in the bench)
- Paraphrase variance per memory `project_augmentation_requires_variance`
- Short context root + delta context per `schemas/context_root.schema.json`

| Need | Status | Block |
|---|---|---|
| GAD Gateway router | not yet wired | slm-learning-208; doc claim only |
| 1.5B + 7B adapters for tier-1 task shapes | partially in bench | gad_tools eval corpus exists; tool_action eval corpus needs ≥100 rows |
| Cost tracing | schema present (`inference_trace.schema.json`) | Gateway must emit rows; not yet emitting |
| Kael-house corrections feeding back | scoping complete | slm-learning-167; first 50 rows captured |

**Estimated time to close:** 2-4 weeks of wiring once Gateway
ships. No new training shots required for Tier 1; the 1.5B + 7B Stein
canonical adapters are already in distribution.

**Estimated cost to close:** ~$10-30 for Tier 1 eval corpus expansion
+ Gateway integration (planning-and-wiring, not training).

## Tier 2 — coding-agent mechanical

**Examples:** repo-debugging, function repair, edit-diff against a
known repo, test-suite-driven repair, doc-driven refactor, terminal
sessions for known commands, GAD-CLI command generation, MDX
authoring against a structure, shell pipeline composition.

**Distance: MEDIUM.** This is where the Big-Base candidate (Phase 3)
matters. 7B Stein is a credible cheap-gate but has measurable failures
on hard repo-spanning tasks; 14B/32B may close that gap depending on
the Phase 1 base eval knee.

| Need | Status | Block |
|---|---|---|
| 7B/32B workhorse with repo-context packs | 7B in distribution; 32B base eval in flight | slm-learning-210 — Phase 1 must complete |
| Tool-use training corpus (Glaive + BFCL + GAD-tools) | Glaive registered, BFCL noted; GAD-tools eval corpus exists | tool-action SFT corpus must reach ≥200 high-quality rows |
| SWE-style eval harness | SWE-bench Verified noted in datasets.json | harness-with-sandboxed-checkout not yet wired; estimate ~3-5 days |
| Verifier/test loop | partial (HumanEval+ runner exists, project-specific test runners do not) | per-project test runners must exist before RL Phase 4 |
| Big-Base LoRA adapter | not yet trained | Phase 3 fire ($55-150) — gated by Phase 1 + corpus |

**Estimated time to close:** 4-8 weeks. The Big-Base candidate
adapter (Phase 3) is the largest line item; once trained, Tier 2
routine load can route to 32B + adapter, and Opus is reserved for
the residual hard rows (cross-repo, novel architecture, debugging
under ambiguity).

**Estimated cost to close:** $200-400 across:
- Phase 3 fire: $55-150 (Candidate A or B)
- Eval corpus expansion (SWE harness, tool-action, repo-debugging):
  $50-100 of bulk-labeler tokens
- Phase 5 smoothing pass: ~$5
- Buffer for second Phase 3 shot if first regresses on a task family:
  $80-120

## Tier 3 — novel architecture / research

**Examples:** new system design, novel-paper synthesis, multi-agent
orchestration, research-trace generation, hard cross-domain reasoning,
GAD-evolution skill drafting, charter-shaped decisions, framework
evolution (slm-learning-198+ class).

**Distance: FAR for 7B-only; CLOSER with high-end open + Opus
hybrid.** 7-32B will not match Opus on hard agentic reasoning per
operator brief and slm-learning-197. The realistic claim here is
NOT model-vs-model parity. It is:

> Big-Base candidate handles the *mechanical* part of novel work
> (drafting, summarization, structure, schema, registry edits). Opus
> handles the *judgment* part (architecture choice, novel synthesis,
> ambiguity resolution). The hybrid stack does Tier 3 work at lower
> cost than Opus-alone, with the same quality, by minimizing Opus
> tokens spent.

| Need | Status | Block |
|---|---|---|
| Big open teacher baseline (32B or 80B-A3B) | base eval in flight | slm-learning-210 |
| Opus-labeled corpus on novel-research task shapes | partial (Kael-house corrections; no pure research-synthesis corpus yet) | requires ~150 hand-curated rows of novel-research → correction pairs |
| Research-synthesis eval | does not exist | Charter does not specify one; need to design (rubric-shaped, judge-panel-based) |
| Long-context memory + retrieval | partial (`schemas/context_root.schema.json`) | retrieval surface not wired; semantic-delta packets exist as a pattern |
| Multi-agent debate/judge | exists at the framework level (gad team) | not wired into the inference path |

**Estimated time to close:** 3-6 months. Tier 3 is an *evolving*
capability — the more Gateway runs novel-work tasks and feeds
corrections back, the more the Big-Base candidate handles. We do not
expect a single Phase 3 fire to clear Tier 3.

**Estimated cost to close:** $400-1500 across the back-half of 2026:
- Multiple Phase 3 + Phase 4 cycles, each producing a stronger
  Big-Base candidate
- Sustained Opus-labeling spend on novel-research rows ($1-3 per row
  of teacher-quality CoT)
- Research-synthesis eval design + run: ~$50

**Dependency on Tier 2:** Tier 3 cannot ship until Tier 2 lands.
The same Big-Base body handles both; without a Tier 2-capable
candidate, Tier 3 is moot.

## Tier 4 — frontier parity

**Examples:** coding-agent on a novel codebase with no specs,
zero-shot game design, multi-modal frontier work, novel mathematical
proofs, real-time agentic loops at frontier latency.

**Distance: NOT NEAR without major funding.** Per Chinchilla math, a
67B compute-optimal pretraining run is funding-level work
(slm-learning operator policy: we don't do from-scratch). Even with
LoRA SFT + DPO + GRPO on 80B-A3B, we don't expect to match Opus on
the hardest residual.

**This is fine.** The replacement target is 70-90% routing-level, NOT
single-model parity. Tier 4 frontier work stays at Opus for the
foreseeable future. The success metric for Tier 4 is:

| Metric | Target | Measure |
|---|---|---|
| Tier 4 calls handled by Opus | ~100% (acknowledged) | Gateway routing log |
| Tier 4 calls / total daily calls | <10% | Gateway routing log |
| Tier 4 cost / total daily cost | <40% | `inference_trace.schema.json` rows |

If Tier 4 rare hard work is <10% of calls and <40% of cost, the stack
overall has replaced 70-90% of dependency even though the residual
hard load is still Opus. That matches the operator brief.

**Estimated time to close to parity:** indefinite (not the goal).

**Estimated cost to push the line:** open-ended. The right strategy
is to keep collecting Opus traces on Tier 4 work, fold them into
Phase 4 DPO/RL training data, and watch the Tier 4 boundary drift
downward over 12-24 months as the Big-Base candidate absorbs
mechanically-decomposable parts of formerly-Tier-4 tasks.

## Cross-tier summary

| Tier | Distance | Time-to-close | Cost-to-close | Primary block |
|---|---|---|---|---|
| 1 — routine | NEAR | 2-4 wk | $10-30 | Gateway not wired |
| 2 — coding mechanical | MEDIUM | 4-8 wk | $200-400 | Phase 3 fire pending; SWE harness pending |
| 3 — novel research | FAR (7B-only); CLOSER (hybrid) | 3-6 mo | $400-1500 | research-synthesis eval design; Opus corpus volume |
| 4 — frontier parity | NOT NEAR | open-ended | open-ended (not the goal) | structural — by design Opus handles residual |

The replacement claim per slm-learning-213 is realistic at Tier 1 +
Tier 2 + most of Tier 3, NOT at Tier 4. Cumulatively that's 70-90%
of operator routine load.

## Pre-conditions for the replacement claim to hold

1. Gateway ships and emits `inference_trace.schema.json`-shaped rows
   (slm-learning-208).
2. Phase 1 base evals complete and a knee is identified (or formally
   absent) per `data/registry/scaling_ladder_gates.json`.
3. Phase 3 first fire produces a Big-Base candidate that clears the 7
   task-shape rule in
   `benchmarks/frontier_open_replacement_matrix.yaml`.
4. Phase 4 begins after 30 days of Gateway data; escalation-rate
   trend confirms downward.
5. The 4-row compare-and-compete artifact (slm-learning-103) is
   produced for every promotion candidate.

If any of (1)-(3) fail, the replacement claim downgrades to "the
owned stack handles Tier 1 + the routine half of Tier 2; Opus stays
on the rest." Still useful, but a smaller win.

— Dr. Stein, replacement distance report, 2026-05-08
