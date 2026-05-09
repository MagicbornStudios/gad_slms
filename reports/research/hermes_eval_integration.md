# Hermes / NousCoder eval integration

**Date:** 2026-05-09
**Owner:** Dr. Stein (slm-learning)
**Decision refs:** slm-learning-097, 100, 103, 210
**Status:** design-only — no evals fired

## 1. Bottom line

Nous Research's Hermes and NousCoder families are now first-class rungs in the
Big-Base scaling ladder, not just inspiration or aspirational benchmarks. Both
the Apache-2.0 14B models (Hermes-4-14B and NousCoder-14B) can be downloaded,
hosted on Modal, and benchmarked without commercial restriction. This gives us
concrete external bars to beat with our own kael-14b adapters.

The compare-and-compete discipline (slm-learning-103) already requires frontier
comparator rows on every promotion candidate. Previously those rows were
Anthropic Sonnet/Opus (API costs) or static published Qwen cards. Adding Hermes
and NousCoder as self-hosted comparators is strictly better: same harness, same
fence-strip judge, apples-to-apples rows.

## 2. Rung table — incremental cost

| Rung slug | HF model | Size | License | GPU | Eval cost | Status |
|---|---|---|---|---|---|---|
| nous-hermes-4-14b | NousResearch/Hermes-4-14B | 14B | Apache-2.0 | H100 | $3 | comparator |
| nous-nouscoder-14b | NousResearch/NousCoder-14B | 14B | Apache-2.0 | H100 | $3 | comparator |
| nous-hermes-4-70b | NousResearch/Hermes-4-Llama-3.1-70B | 70B | Llama 3.1 community | H100x2 | $6 | comparator |
| nous-hermes-4-405b | NousResearch/Hermes-4-Llama-3.1-405B | 405B | Llama 3.1 community | H200x4 | $12 | comparator-eval-only |

**Incremental total: $24.** Combined with the existing $14 Big-Base ladder, budget
ceiling is raised to $35 (405B fires only if remaining budget allows). Full rung
entries with serving instructions and graduation gates are in
`slm_learning/data/registry/benchmark_target_rungs.toml`.

## 3. Eval suite

| Eval ID | Rungs that fire | Notes |
|---|---|---|
| humaneval-clean-v1 | all four | Fence-strip patched via rejudge_he_local.py; same harness as GAD-owned rungs |
| mbpp-clean-v1 | all four | n=164 sanitized split |
| gad_tools_v1 | hermes-4-14b, nouscoder-14b | GAD CLI tool-use judge |
| tool_action_v1 | hermes-4-14b, hermes-4-70b | Tool-call correctness rubric |
| kael_task_v1 | hermes-4-14b, nouscoder-14b | NEW: gad_tools_kael_task_eval.py, 30 domain tasks |
| swe-bench-verified-mini | nouscoder-14b | Coding specialist bar; mini subset only |
| research_synthesis_v1 | hermes-4-70b only | Stretch eval; only fire at 70B+ |

`kael_task_v1` is the only eval where our GAD-trained adapters have home-field
advantage — tasks are drawn from real GAD CLI workflows (handoff reclaim,
decision lookup, Modal deploy, settings mutation). NousCoder-14B and
Hermes-4-14B have never seen these task shapes in post-training; our
kael-14b adapter trained on GAD trace data should lead here.

## 4. Graduation gates

Codified in `benchmark_target_rungs.toml` under each rung's `graduation_gate`
field. Summary:

- **14B production route:** our kael-14b adapter must beat Hermes-4-14B on
  HumanEval by >= 2pp AND beat NousCoder-14B by >= -2pp (within 2pp under).
  If adapter is under both bars, extend the Stein-house training corpus before
  promoting the adapter.
- **14B code-agent lane:** NousCoder-14B sets the direct bar. kael-14b adapter
  HumanEval >= NousCoder-14B - 2pp.
- **70B + 405B:** frontier ceiling comparators only; no graduation gate. These
  rows answer "how far below the open-weight frontier are we?" not "should we
  replace this rung with Hermes?"

## 5. Open questions

**Llama 3.1 community license (70B + 405B):** Commercial use is permitted with
attribution, but the terms require a separate license agreement for deployments
over 700M MAU. At current scale this is not a blocker, but the 70B and 405B
rows should be flagged for legal review before any production routing decision
cites them as a cost-justified replacement for Opus. The 14B Apache-2.0 rows
have no such restriction.

**405B serving cost:** Self-hosted 405B on Modal H200x4 is expensive and
logistically complex. Preferred path: fire via Together.ai or Fireworks external
API at their per-token cost, which is likely cheaper than hourly H200x4 for a
one-shot ceiling reference. Operator to confirm before firing.

**Hermes-4 HF slugs:** The placeholder HF IDs in the rung registry
(e.g. `NousResearch/Hermes-3-Llama-3.1-8B`) are standing placeholders pending
verification. Confirm actual model card slugs against the NousResearch HF org
before download. Do not download until slugs are verified — wrong slug wastes
Modal storage and compute budget.

**kael_task_v1 task count:** Currently 5 seed tasks. The eval script supports
up to 50 tasks (--task-dir auto-globs). Operator should add 25-45 additional
task files in `data/eval/kael_task_eval/` before firing the comparator eval to
get statistically meaningful separation between models.
