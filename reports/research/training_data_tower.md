# Training Data Tower — GAD Ecosystem Research Report

**Date:** 2026-05-09  
**Author:** claude-code (Sonnet 4.6), operator direction  
**Status:** Living document — update at each evolution milestone

---

## 1. Bottom Line

The Training Data Tower is a 9-layer data architecture that maps every learning signal — from raw web text to live agent trajectories — to a distinct curation and training stage. **GAD's moat is not broad intelligence; it is dense, structured, continuously-evolving intelligence about its own ecosystem and customer projects.** Frontier labs cannot own that data. We can.

---

## 2. The 9 Layers

### Layer 1 — Foundation (Pretrain)

Broad language modeling on web-scale corpora. Teaches grammar, world knowledge, and generalization. Reference: [FineWeb](https://huggingface.co/datasets/HuggingFaceFW/fineweb) (18.5T tokens, CC-2013 to 2024, 96 snapshots, quality-filtered), [Dolma](https://huggingface.co/datasets/allenai/dolma) (3T tokens, diverse sources). GAD does not compete here — this layer is a given in the base models we fine-tune.

### Layer 2 — Code / Domain (Pretrain-Cont)

Code understanding, file-system reasoning, CLI invocation patterns. Reference: [The Stack v2](https://huggingface.co/datasets/bigcode/the-stack-v2) (67.5 TB source, ~900B code tokens used by StarCoder2-15B trained on 4T tokens). GAD's domain is TypeScript/React/Tauri/Next + the gad CLI DSL. We extend this layer by producing `tech_stack_inference` pairs from real monorepo edits.

### Layer 3 — Instruction Following (SFT)

Supervised fine-tuning on (instruction, response) pairs that teach the model to follow directives in a specific style. Reference: [Tulu 3](https://huggingface.co/datasets/allenai/tulu-3-sft-mixture) (939k SFT rows, persona-augmented, RLVR-ready), [OpenHermes 2.5](https://huggingface.co/datasets/teknium/OpenHermes-2.5) (1M rows, GPT-4-generated). GAD's target: Kael SFT v1 — operator-voice instruction following tuned on real Kael sessions, 200–500 rows to start.

### Layer 4 — Reasoning (Chain-of-Thought)

Long-form thinking traces that teach the model to reason before answering. Reference: [OpenThoughts-114k](https://huggingface.co/datasets/open-thoughts/OpenThoughts-114k) (114k CoT examples from DeepSeek-R1) and [OpenThoughts3](https://huggingface.co/datasets/open-thoughts/OpenThoughts-3) (1.2M diverse reasoning traces). GAD's analog is planning traces: the 172k `role=reasoning` envelopes in the 2026-05-09 delta-export are raw material for this layer.

### Layer 5 — Preference / Alignment (DPO)

Preference pairs (chosen vs rejected) that steer tone, format, and decision quality. Reference: [UltraFeedback](https://huggingface.co/datasets/openbmb/UltraFeedback) (64k prompts, GPT-4-judged, 256k responses). GAD's `gad feedback record` command (shipped 2026-05-09) writes to `.planning/datasets/preference-pairs/`. Currently 2 rows — this is the most urgent pipeline gap.

### Layer 6 — Tool / Action (JSON Grounding)

Structured function-call and tool-invocation sequences. Teaches the model to emit schema-valid JSON, select the right tool, and chain tool calls. Reference: [ToolBench](https://github.com/OpenBMB/ToolBench) (16k instructions, 126k+ solution paths). GAD's target: `tool_action_json_v1` — extracted from `.planning/.gad-log/` envelopes with `role=tool_call` (701 envelopes in today's export).

### Layer 7 — Agent Trajectory (Multi-Step)

Complete task trajectories: plan, act, verify, correct, stamp. Reference: [OpenThoughts-Agent](https://huggingface.co/datasets/open-thoughts/OpenThoughts-Agent) (15.2k SFT, 720 RL tasks). GAD's analog: curated `agent_trace` records derived from session logs. Every `gad tasks stamp` event anchors a trajectory. Today: 5,348 `role=response` envelopes are raw material.

### Layer 8 — GAD-Owned Pressure / Delta Packets

The highest-signal layer in the tower for GAD's use case: context-root-anchored packets capturing exactly where the model diverged from correct behavior and what the correction was. No redundant context storage; every packet teaches one delta. Reference: slm-learning delta_packet design (decisions slm-learning-186, slm-learning-192), `C:/Users/benja/Documents/slm_learning/schemas/delta_packet.schema.json`. Tower variant: `delta_packet_tower.schema.json`.

### Layer 9 — Customer / Project Soul

Per-project personality, tone, vocabulary, and decision history adapted as a lightweight LoRA or system-prompt adapter. Reference: `C:/Users/benja/Documents/slm_learning/schemas/customer_soul_adapter.schema.json`. Enables Kael's voice for the `magicborn` project to differ from the `grime-time` project without retraining a new base. This layer is GAD's unique commercial moat — frontier labs cannot replicate it.

---

## 3. Where GAD Competes

| Layer | Owned Dataset Target | Current Rows | Target Rows | Gap |
|---|---|---|---|---|
| SFT (L3) | `kael-sft-v1` | 0 | 200–500 | Build from session transcripts + Opus teacher |
| DPO (L5) | `kael-dpo-v1` | 2 | 200–500 | `gad feedback record` pipeline just shipped |
| Tool/Action (L6) | `tool-action-json-v1` | ~701 raw | 500–1000 curated | Curator pass needed on gad-log tool_call envelopes |
| Agent Trajectory (L7) | `gad-decision-handoff-v1` | ~5,348 raw | 300–1000 curated | Curator pass on response+tool_call pairs |
| Agent Trajectory (L7) | `repo-task-trace-v1` | ~466k raw | 100–300 curated | Filter by task_id + quality_label |
| Domain (L2) | `tech-stack-inference-v1` | 0 | 500 | Extract from monorepo edit history |
| Customer Soul (L9) | `game-artifact-v1` | 0 | 100–300 | Curate from magicborn narrative sessions |
| Retain (all) | retain banks per model/base/task | 0 | 100–500 each | Distill from ERRORS-AND-ATTEMPTS.xml |

---

## 4. Schema Index

All schemas at `C:/Users/benja/Documents/slm_learning/schemas/`:

| Schema | Description |
|---|---|
| [`dataset_block.schema.json`](../../schemas/dataset_block.schema.json) | Top-level metadata for a named, promotable dataset unit. One block per dataset_id. |
| [`delta_packet_tower.schema.json`](../../schemas/delta_packet_tower.schema.json) | Tower Layer 8 agent-action-delta record anchored to a context_root. Distinct from model-correction `delta_packet.schema.json`. |
| [`retain_bank.schema.json`](../../schemas/retain_bank.schema.json) | Golden (prompt, expected_output) pairs that must not regress during fine-tuning. One bank = one model × one purpose. |
| [`preference_pair.schema.json`](../../schemas/preference_pair.schema.json) | DPO triple: prompt + picked + rejected. Matches `gad feedback record` output shape. |
| [`agent_trace.schema.json`](../../schemas/agent_trace.schema.json) | Full multi-step trajectory for one agent session: plan → act → verify → stamp. |
| [`evolution_dataset_manifest.schema.json`](../../schemas/evolution_dataset_manifest.schema.json) | Declares which dataset_blocks, retain banks, and preference pairs feed one evolution run. Glues the tower together. |

---

## 5. Production Pipeline State — TODAY (2026-05-09)

### What's Captured

`.planning/.gad-log/` contains dated JSONL files from 2026-04-07 onward. The 2026-05-09 delta-training export (`tick-2026-05-09T16-06-26-934Z`) confirms **466,015 envelopes** across the full history. Role breakdown: 282,173 meta, 172,057 reasoning, 5,348 response, 5,035 prompt, 701 tool_call, 701 tool_result. Session-level logs also exist at `.planning/team/workers/*/log.jsonl` for team-dispatched workers. Raw material is abundant.

### What's Curated

`vendor/get-anything-done/lib/datasets/curator.cjs` runs on a schedule, writing to `.planning/datasets/<type>/` directories. Today's dataset directories: `ai-spend-ledger`, `claim`, `cli-call`, `complete`, `deviation`, `dispatch`, `edit`, `inference-trace`, `plain-chat`, `preference-pairs`, `search`, `slm-disagreement`. The curator classifies envelopes by content_type and role into these typed buckets. Output is JSONL per day.

### What's Promotable

`.planning/delta-training/exports/tick-2026-05-09T16-06-26-934Z/MANIFEST.json` confirms: 466,015 rows, 339 MB, SHA-256 verified, 62 redacted envelopes stripped. Content type breakdown: 281,916 planning, 183,596 meta, 480 code. The `role=tool_call` and `role=response` subsets (~6k rows combined) are the highest-priority candidates for Layer 6 and 7 curation passes.

### What's MISSING

**Preference-pair sink is nearly empty.** `.planning/datasets/preference-pairs/2026-05-09.jsonl` has exactly **2 rows**. `gad feedback record` shipped today (2026-05-09) — the collection mechanism exists but has not been fed. This is P0: without DPO data, Layer 5 cannot be trained and alignment tuning stalls. Operator action required: begin rating session outputs via `gad feedback record` at end of each substantive session.

---

## 6. Next Concrete Dataset Cycle

Ordered by effort (low → high). Each entry is one backlog target.

| # | dataset_id | Layer | Target Rows | Source Channel | Eval Gate | Est. Tokens |
|---|---|---|---|---|---|---|
| 1 | `kael-dpo-v1` | DPO | 200–500 | operator manual via `gad feedback record` | kael-dpo-eval-v1 | ~500k |
| 2 | `tool-action-json-v1` | Tool/Action | 500–1000 | gad-log curator (role=tool_call filter) | schema-valid >= 0.99 | ~2M |
| 3 | `gad-decision-handoff-v1` | Agent Trace | 300–1000 | gad-log curator (response+tool_call pairs, task_id present) | human spot-check 50 rows | ~5M |
| 4 | `retain-hard-failures-v1` | Retain | 100–500 | distilled from ERRORS-AND-ATTEMPTS.xml + Opus teacher | retain-regression-eval-v1 | ~1M |
| 5 | `kael-sft-v1` | SFT | 200–500 | Opus teacher (session transcripts as seed) | kael-sft-eval-v1 | ~2M |
| 6 | `repo-task-trace-v1` | Agent Trace | 100–300 | gad-log curator (filter by stamped task_id) | task-trace-eval-v1 | ~3M |
| 7 | `tech-stack-inference-v1` | Domain | 500 | distilled from monorepo git history + edit envelopes | tech-stack-eval-v1 | ~4M |
| 8 | `game-artifact-v1` | Customer Soul | 100–300 | operator manual (magicborn narrative sessions) | game-artifact-eval-v1 | ~2M |

---

## 7. Strongest Recommendation

**GAD's moat is owned data, not foundation data.** Frontier labs have FineWeb-scale pretraining, Tulu 3-scale instruction tuning, and OpenThoughts-scale reasoning. Competing on those layers wastes resources on a game already won. The data GAD uniquely owns — every agent decision, every handoff, every tool-call correction, every project soul — is data no frontier lab can acquire. The rule is simple: **do not clone foundation data; curate what only you can produce.** The 466k envelopes in today's export are the seed. The preference-pair gap (2 rows) is the immediate bottleneck. Fix that first; Layer 5 unlocks the rest of the alignment stack.
