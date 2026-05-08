# Delta Packets and Dataset Sharding

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Decision refs:** slm-learning-186, 189, 192 (proposed in
`pressure_to_training_research_agenda.md`)
**Schemas:**
- `schemas/delta_packet.schema.json`
- `schemas/context_root.schema.json`
- `schemas/consolidation_run.schema.json`

---

## The principle

> Do not repeat full context in every training row. Store shared
> roots once, then train on typed deltas/addendums. Like file
> paths: root path once, changed filenames as deltas.

Bad row (repeats the world every time):

```json
{
  "input": "You are a coding assistant. Solve this Python problem...",
  "output": "def solve(x): ..."
}
```

Better row (shared root + minimal delta):

```json
{
  "root_context_id": "qwen-1p5b-mbpp-function-definition",
  "delta": {
    "failure_type": "edge_case_miss",
    "minimal_prompt": "...",
    "correction": "..."
  }
}
```

Training composes the prompt at load time:
`root.shared_instruction + delta.minimal_prompt → delta.correction`.
Storage shrinks; signal density grows.

---

## Three first-class objects

### 1. `context_root`

A **shared header** for many delta packets. Stored once, referenced
by ID from every packet that shares it.

Example:

```json
{
  "root_context_id": "qwen-1p5b-mbpp-function-definition",
  "project": "slm-learning",
  "benchmark": "mbpp",
  "model_family": "Qwen2.5-Coder-1.5B-Instruct",
  "target_contract": "function_definition",
  "shared_instruction": "You are a coding assistant. Solve the problem in clean Python.",
  "tokenizer_family": "qwen2",
  "schema_version": 1,
  "allowed_tools": [],
  "eval_refs": ["humaneval", "mbpp"]
}
```

### 2. `delta_packet`

A **typed addendum** that captures only the difference between
failed behavior and desired behavior, anchored to a `context_root`.

Example:

```json
{
  "packet_id": "qwen-1p5b-he-fail-23",
  "root_context_id": "qwen-1p5b-mbpp-function-definition",
  "base_model": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
  "task_shape": "function_repair",
  "skill_id": "code_function_repair",
  "pressure_source": "base_eval_failure",
  "failure_type": "edge_case_miss",
  "base_output_ref": "sha256:...",
  "minimal_prompt": "Write a function that returns ...",
  "correction": "def f(...): ...",
  "tests": ["assert f([]) == 0"],
  "retain_tags": ["mbpp_passed", "function_shape"],
  "target_contract": "function_definition",
  "provenance": {
    "captured_at": "2026-05-08T...",
    "from_run_id": "morphism-1p5b-base-2026-05-08"
  },
  "token_budget": 512
}
```

`base_output_ref` is a content hash so we don't store the full
incorrect output verbatim in every packet — just a pointer.

### 3. `retain_bank`

A **per-base store of stable behavior** the consolidation must not
break. Sampled into every consolidation mix.

Already implemented at
`scripts/data/build_retain_bank.py`; this section codifies it as
a first-class object alongside delta_packets.

---

## Shard layout

```
data/
  context_roots/
    qwen-1p5b-mbpp-function-definition.json
    qwen-7b-humaneval-function-definition.json
    qwen-3b-tool-action.json
    ...

  delta_packets/
    base_failures/
      qwen-1p5b-he-fail-001.json
      qwen-1p5b-he-fail-002.json
      ...
    tool_action_failures/
      ...
    schema_repairs/
      ...
    contract_violations/
      ...

  retain_banks/
    1p5b/humaneval/2026-05-08/passed.jsonl
    3b/humaneval/2026-05-08/passed.jsonl
    7b/humaneval/2026-05-08/passed.jsonl
    ...

  consolidation_mixes/
    1p5b-2026-05-08-mbpp-30-70/rows.jsonl
    3b-2026-05-08-he-50-50/rows.jsonl
    ...

schemas/
  context_root.schema.json
  delta_packet.schema.json
  consolidation_run.schema.json
  function_definition.schema.json
  tool_action.schema.json
  bestiary_entry.schema.json
```

---

## How consolidation composes the training mix

```
1. Operator (or pressure-gate) picks a context_root
   e.g., "qwen-1p5b-mbpp-function-definition"

2. compose_training_mix_from_shards.py reads:
   - the root's shared_instruction
   - delta_packets where root_context_id == this root
   - retain bank rows whose retain_tags overlap with the root

3. For each delta_packet, it materializes ONE training row at load:
   text = root.shared_instruction
        + "\n\n" + delta.minimal_prompt
        + "\n" + delta.correction
   (then formatted via tokenizer.apply_chat_template)

4. It samples retain rows at the configured ratio.

5. Output: rows.jsonl ready for SFTTrainer.
```

The benefits:
- **Storage:** root context stored ONCE, not N times.
- **Auditability:** delta_packets are self-describing; you can
  query "show me all packets with `failure_type=edge_case_miss`."
- **Reuse:** the same delta packet shard can be composed into
  multiple consolidation mixes (different ratios, different
  retain banks).
- **Schema migration:** adding a new field to root_context doesn't
  require rewriting every training row.

---

## What this changes about response style

The same principle applies to chat / SITREP responses (operator
note 2026-05-08):

- Don't restate the whole tree every turn.
- State the root idea once.
- Then say only the new/distinctive pieces.
- Pattern: (1) what changed, (2) why it matters, (3) what it
  falsifies, (4) what we should do next, (5) what to tell Claude.

This is "non-token-redundant speech." It's the SITREP discipline
already in CLAUDE.md, made more explicit.

---

## Refined "bad morphism target" framing

Earlier docs said: "broad code intelligence from 74 rows" is a
bad morphism target. This needs precision per operator note
2026-05-08:

It does NOT mean "never train toward broad reasoning." It means:

> **A tiny inserted identity/projection layer trained on 74 rows
> is the wrong mechanism for installing broad,
> architecture-wide intelligence in one shot.**

Refined rules:

**Good morphism target** (a small late-inserted residual layer
trained on hard+retain CAN absorb):
- compact, repeated, base-specific delta family
- late-stage output correction (formatting, decision, schema)
- behavior the base already does — just doing wrong consistently
- supported by a retain bank anchoring old behavior

**Bad morphism target for THIS mechanism** (the goal is fine, but
need a different mechanism):
- broad general reasoning from <100 rows → use larger LoRA + more data
- cross-base failure knowledge → build per-base hard sets (slm-learning-189)
- architecture-wide changes → use multi-LoRA composition or system MoE
- entirely new capabilities the base doesn't do at all → bigger base or specialist

The phrase "bad target" was always shorthand for "wrong mechanism
for this scope," never "never train this." This doc fixes the
phrasing project-wide.

---

## Acceptance test for the framework

When this is wired:

1. `gad pressure list --projectid slm-learning --since 7d` returns
   pressure clusters with type + count + last_seen.
2. `python scripts/data/build_delta_packets.py
       --pressure-cluster <id>
       --base-model qwen-1p5b
       --out data/delta_packets/...`
   produces N delta packets matching the schema.
3. `python scripts/data/compose_training_mix_from_shards.py
       --root qwen-1p5b-mbpp-function-definition
       --packet-dir data/delta_packets/base_failures
       --retain-bank data/retain_banks/1p5b/humaneval/2026-05-08
       --hard-ratio 0.3
       --out data/consolidation_mixes/<run_id>`
   produces a rows.jsonl identical-in-effect to the existing
   `build_consolidation_mix.py` output, validating compose-time
   materialization.
4. A consolidation run on the composed mix produces a
   `consolidation_run.json` per `schemas/consolidation_run.schema.json`.

---

## Cross-references

- `reports/research/incremental_latent_consolidation.md` — the loop
- `reports/research/pressure_to_training_research_agenda.md` — the questions
- `scripts/data/build_retain_bank.py` — already implemented
- `scripts/data/build_consolidation_mix.py` — current ad-hoc mixer; will be replaced by compose_training_mix_from_shards.py once the shard layout is populated
- `schemas/consolidation_run.schema.json` — already implemented

— Dr. Stein, delta packets + dataset sharding, 2026-05-08
