# Task Replacement Matrix

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Decision refs:** slm-learning-217 (this matrix determines training
priorities), slm-learning-214 (GAD-owned inference is default),
slm-learning-215 (frontier becomes enrichment-only),
slm-learning-197-200 (teacher policy + Kael moat),
slm-learning-103 (compare-and-compete).

## Operator direction summary (2026-05-08)

This matrix is the source of truth for "what model serves what task
shape" during the subscription-replacement migration. It uses the
task_shape vocabulary from `data/registry/teachers.json` augmented
with the replacement-plan additions called out in the operator
direction (gad_note, gad_decision, gad_handoff, eval_summary,
tech_stack_inference, dataset_cleanup, delta_packet_creation,
context_compression, classification, repo_repair,
architecture_review, artifact_generation).

## How to read the matrix

| Column | Meaning |
|---|---|
| Priority | Operator-set replacement priority (1 = highest) |
| task_shape | Canonical label (extends teachers.json vocabulary) |
| Current tool | What is paying for this work today |
| Replacement model | Tier 0/1/2 target that absorbs the traffic |
| Tier | tier0_local / tier1_workhorse / tier2_high_end |
| Confidence | How well this replacement currently works (high / medium / low / untested) |
| Cost / call (USD) | Approximate per-call cost on the replacement |
| Frontier-as-enrichment | When the Tier-3 frontier is still allowed in the loop |
| Gate threshold | Pass criterion in the smoke benchmark |
| Training source | Where corrected rows feed back |

Pricing references: RunPod flex $0.00019/sec idle, $0.00076/sec
A100 active; Together API Qwen3-Coder-Next $0.50 / $1.20 per Mtok
(input / output); HF dedicated ~$0.50/hr. Per-call costs assume
median 2k-token context + 400-token completion unless noted.

## Matrix

| # | task_shape | Current tool | Replacement model | Tier | Confidence | Cost/call (USD) | Frontier enrichment | Gate threshold | Training source |
|---|---|---|---|---|---|---|---|---|---|
| 1 | gad_note | Claude Code / ChatGPT | kael-1p5b-gad-meta-v1 | tier0_local | medium | ~$0.0001 | Operator override only | >=90% schema-valid, edit distance <10 tokens | inference_trace + edit-distance corpus |
| 1 | gad_decision | Claude Code / ChatGPT | kael-1p5b-gad-meta-v1 | tier0_local | medium | ~$0.0001 | Operator override only | >=90% schema-valid + decision_refs resolved | inference_trace + edit-distance corpus |
| 1 | gad_handoff | Claude Code / ChatGPT | kael-1p5b-gad-meta-v1 | tier0_local | medium | ~$0.0001 | Operator override only | Handoff body schema validates, score >=12/16 on rubric | inference_trace + handoff close events |
| 2 | tool_action_json | Claude Code (Sonnet) | kael-7b-tool-action-v1 (LoRA over Qwen2.5-Coder-7B) | tier1_workhorse | high (after Month 3) | ~$0.001-0.003 (Modal A100) | When verifier disagrees with Tier 1 emit | >=85% on BFCL + GAD-tools owned-domain | tool_action delta packets |
| 3 | eval_summary | ChatGPT / Claude | qwen2.5-coder-3b-instruct + retain LoRA | tier1_workhorse | medium | ~$0.0008 | When summary contradicts verifier | >=80% operator-accept | eval-summary edit-distance corpus |
| 4 | tech_stack_inference | Claude Code | kael-1p5b-classifier-v1 | tier0_local | high | ~$0.0001 | Never (Tier 0 sufficient) | >=90% top-1 on held-out 200 prompts | classifier retrain monthly |
| 4 | classification | Claude / ChatGPT | kael-1p5b-classifier-v1 | tier0_local | high | ~$0.0001 | Never | >=90% on routing test bench | classifier retrain monthly |
| 4 | context_compression | Claude (long-context) | qwen3-next-80b-a3b-instruct (Modal H100, batch) | tier2_high_end | medium | ~$0.005-0.02 (token-volume) | When summary loses critical detail | Compression ratio >=4x with operator-accept >=80% | compression edit-distance corpus |
| 5 | dataset_cleanup | Claude Code (subagent) | qwen2.5-coder-7b-instruct + verifier loop | tier1_workhorse | high | ~$0.001 | When schema validator fails repeatedly | >=95% schema-valid output, verifier passes | cleanup deltas |
| 5 | delta_packet_creation | Claude Code (subagent) | qwen2.5-coder-7b-instruct + verifier loop | tier1_workhorse | high | ~$0.001 | Operator review only | >=95% packets parse against delta_packet.schema.json | self-feeding |
| 6 | code_function_completion | Claude Code | qwen2.5-coder-7b-instruct (Stein canonical) | tier1_workhorse | high | ~$0.001 | When verifier fails -> Opus repair | HE/MBPP not regressed vs canonical 84.8/82.3 | HumanEval+/MBPP+ failure -> delta packet |
| 6 | code_repair | Claude Code | kael-7b-repair-v1 (planned) | tier1_workhorse | low (untrained) | ~$0.001 | Always for Tier-3 hard rows in Month 1-3 | >=70% test_suite_diff_runner pass | repair traces |
| 7 | artifact_generation (game / bestiary) | ChatGPT / Claude | qwen2.5-coder-7b-instruct + game-artifact LoRA (planned Month 4) | tier1_workhorse | low (untrained) | ~$0.002 | Frontier panel for tone/style critique | Operator-accept >=70% on Magicborn + Grime Time targets | artifact edit-distance corpus |
| 7 | bulk_paraphrase | Claude Haiku | claude-haiku-4-5 (cheap teacher) -> swap to qwen2.5-coder-7b after Month 4 | tier2_high_end -> tier1_workhorse | high (Haiku); medium (planned) | ~$0.0005 (Haiku); ~$0.001 (Qwen) | Haiku is the labeler per slm-learning-197; not frontier | Variance check passes per project_augmentation_requires_variance.md | paraphrase corpus |
| 7 | chain_of_thought_synth | Claude Opus | claude-opus-4-5 (Tier 3 teacher, gated) | tier3_frontier | high | ~$0.05-0.20 | This IS the frontier route; cap volume | CoT trace verifier passes final_answer_check | CoT teacher corpus |
| 8 | repo_repair | Claude Code (heavy) | kael-14b-repair-v1 (planned Month 4+) | tier2_high_end | untested | ~$0.005-0.02 (Modal A100) | When kael-14b verifier fails | >=60% on repo-level test suite diff | repo_repair traces |
| 9 | architecture_review | Claude Opus / GPT-5 | claude-opus-4-5 + frontier_judge_panel (Tier 3) | tier3_frontier | high | ~$0.10-0.50 | This IS the frontier route; budget-capped | Operator-accept; not auto-gated | architecture review corpus (small, hand-curated) |
| 9 | math_reasoning | Claude Opus | claude-opus-4-5 + deepseek-r1-distill-qwen-32b comparator | tier3_frontier (primary) + tier2_high_end (comparator) | high | ~$0.05 (Opus); ~$0.005 (R1-distill on Modal) | Always (this is hard reasoning) | symbolic_solver + numeric_check passes | CoT corpus |
| 9 | trajectory_completion (Kael) | Claude Opus | claude-opus-4-5 (teacher) -> kael-7b-trajectory-v1 student | tier3_frontier (teacher) -> tier1_workhorse (student) | medium (in flight) | ~$0.05 teacher; ~$0.001 student | Opus IS the teacher per slm-learning-197 | trace_replay + game_state_invariants pass | Kael-house trajectory corpus |
| 9 | frontier_judge_panel | Opus + GPT-5 + Gemini | claude-opus-4-5 + gpt-5 + gemini-2.5-pro | tier3_frontier | high | ~$0.30-1.00 (panel cost) | This IS the frontier route; reserved for Charter Row 8 | n/a (research artifact) | judge-panel disagreement signal |
| 9 | logit_inspection | n/a (closed weights cannot expose logits) | qwen2.5-coder-7b-instruct (open weights only) | tier2_high_end | high | ~$0.001 | Frontier cannot serve this role | Inspector emits hidden states without crash | research-only |

## Vocabulary alignment notes

This matrix uses the canonical task_shape labels from
`data/registry/teachers.json` (code_function_completion, code_repair,
tool_action_json, math_reasoning, trajectory_completion,
bulk_paraphrase, chain_of_thought_synth, frontier_judge_panel,
logit_inspection) and adds the replacement-plan labels called out by
the operator direction. The additions are:

- `gad_note`, `gad_decision`, `gad_handoff` — meta-task shapes for
  GAD planning surface emissions.
- `eval_summary` — short summary of a benchmark/eval run.
- `tech_stack_inference` — classify a repo / project by its stack.
- `classification` — generic category emit (single-label).
- `context_compression` — long-context summary with structured output.
- `dataset_cleanup` — schema-fix + dedup pass over a JSONL.
- `delta_packet_creation` — emit a `delta_packet` schema row.
- `repo_repair` — multi-file repair across a repository.
- `architecture_review` — high-level design critique.
- `artifact_generation` — game / bestiary / marketing / landing.

These should be added to `teachers.json` policies in the next
registry pass (slm-learning-218+ scope) so the matrix and the teacher
policy stay aligned. Until then, this doc is the canonical mapping.

## Training priority order (slm-learning-217)

The replacement matrix sets training priorities:

1. **gad_meta corpus** — gad_note + gad_decision + gad_handoff. Trains
   `kael-1p5b-gad-meta-v1`. Smallest model, fastest payback (Month 2).
2. **tool_action_json corpus** — already in flight (Kael trajectory
   path). Trains `kael-7b-tool-action-v1` (Month 2-3).
3. **eval_summary + classification corpus** — small specialists,
   Month 3.
4. **dataset_cleanup + delta_packet corpus** — self-feeding training
   data pipeline (Month 3+).
5. **code_function_completion + code_repair corpus** — main coding
   route (continuous, already in flight as Stein-7B).
6. **artifact_generation corpus** — Magicborn + Grime Time + Kael
   (Month 4+).
7. **repo_repair corpus** — long-context, hard (Month 4+).

Architecture review and math_reasoning stay on Tier 3 frontier
indefinitely; they are NOT replacement targets. The cost is justified
by the value of correctness on hard rows.

## Cross-references

- `data/registry/teachers.json` — canonical task_shape vocabulary
- `data/registry/model_families.json` — model ids + cost rates
- `reports/research/subscription_replacement_plan.md` — phased timeline
- `reports/research/teacher_species_policy.md` — teacher / labeler
  / comparator / inspector role split
- `reports/costs/ai_spend_ledger.md` — monthly close + gate log
- `benchmarks/day_to_day_replacement_smoke.yaml` — gate benchmark
- `schemas/inference_trace.schema.json` — per-call log schema

— Dr. Stein, task replacement matrix, 2026-05-08
