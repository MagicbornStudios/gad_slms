# Training Data Inventory — slm-learning

**Date:** 2026-05-06
**Repo:** `C:/Users/benja/Documents/slm_learning/`
**Project id:** `slm-learning`
**Active soul:** Dr. Stein
**Auditor:** claude-code (this session)

Companion to gad-monorepo audits at
`custom_portfolio/.planning/codebase/audit-2026-05-06-{monorepo-topology,runtime-substrate-map,agent-skill-inventory}.md`.

---

## 1. Corpus inventory (data/)

### 1.1 Training-ready JSONL (instruction + command shape)

| File | Pairs | Source / shape | Used by |
|---|---|---|---|
| `data/gad_tool_pairs.jsonl` | 153 | hand-curated seed: NL → gad CLI command | superseded by v2 |
| `data/gad_tool_pairs_v2.jsonl` | **783** | 153 seeds + 630 distilled from haiku-4-5 (`scripts/distill_gad_pairs.py`); vocab-anchored against actual `gad --help` surface | **v2 adapter (30/30 GAD-tools, 100%)** |
| `data/distilled_pairs.jsonl` | 630 | haiku-4-5 distillation output | feeds v2 |
| `data/tool_use_pairs.jsonl` | 789 | real Claude-Code traces extracted by `scripts/extract_tool_use_pairs.py` from `.planning/.trace-events.jsonl` | tooluse sanity adapter |
| `data/openmathinstruct_2k.jsonl` | 2,000 | HF dataset `nvidia/OpenMathInstruct-2` subset | first math run (2k baseline) |
| `data/openmathinstruct_5k.jsonl` | **5,000** | Same dataset, larger subset | **math 1.5B adapter (25/50 GSM8K, 12x baseline)** |
| `data/multitask_combined.jsonl` | 6,572 | `gad_tool_pairs_v2 + tool_use_pairs + openmathinstruct_5k` concatenated | **multitask LoRA candidate (training in flight)** |
| `data/sft_pairs.json` | 1,001 | older SFT pairs (Phase 02 era) | superseded |
| `data/reasoning_pairs.json` | 1,981 | Stage 2 reasoning training data | superseded |
| `data/dpo_pairs.json` | 401 | DPO preference pairs (synthetic, too separable per state log) | dr_stein.pt (Phase 02 closeout) |

### 1.2 Doc-verifier corpora (bootstrapped)

| File | Pairs | Source | Status |
|---|---|---|---|
| `data/agent_corpus_gad-doc-verifier.bootstrapped.jsonl` | **475** | `scripts/synth_doc_verifier_pairs.py --root .` (full slm-learning) | unblocks SL-T-04-09 |
| `data/agent_corpus_gad-doc-verifier.bootstrapped.multiroot.jsonl` | **264** | same script across slm-learning + grime_time_site + tweakcn + my_writing | sibling-root expansion |
| `data/agent_corpus_gad-doc-verifier.jsonl` | 0 | trace-extraction reservation | empty — feed via telemetry ingest |
| `data/agent_corpus_gad-codebase-mapper.jsonl` | 2 | trace-extraction reservation | starter, expand via global Claude's audit outputs |
| `data/agent_corpus_gad-assumptions-analyzer.jsonl` | 0 | trace-extraction reservation | empty |

Schema for the bootstrapped pairs (`slm-learning-doc-verifier-pair@1`):
```json
{
  "input": {"doc_path": "...", "claim": "...", "claim_category": "file_path|function|command|dependency", "line": N},
  "output": {"claim": "...", "status": "verified|refuted|unknown", "evidence": ["..."], "confidence": 0.0, "reason": "..."},
  "provenance": {"source_file": "...", "agent_type": "gad-doc-verifier", "data_tier": "bootstrapped", ...}
}
```

### 1.3 Telemetry ingest output (gitignored — contains live secrets even after redaction sweep)

`data/processed/gad-telemetry-2026-05-06/` (not in git per `.gitignore`):

| File | Pairs | Source |
|---|---|---|
| `sft_basic.jsonl` | 3,446 | prompt → response, derived from `data/raw/2026-05-06/events.jsonl` (119,819 envelopes, 52 sessions) via `scripts/ingest_gad_telemetry.py` |
| `sft_reasoned.jsonl` | 307 | prompt → reasoning + response (CoT) |
| `sft_tooluse.jsonl` | 4,841 | prior context → next tool_call (handles both `role=tool_call` and `role=meta` with `content.type=tool_call`) |

Combined: **8,594 SFT pairs from real Claude sessions across 5 days.**

The pair JSONLs are gitignored due to GitHub push-protection finding live OAuth tokens in raw response content. Redaction layer is in place for future runs (commit `f01fce2`).

### 1.4 External standard datasets

`data/external/` (gitignored):
- `arc_challenge/`, `arc_easy/` — ARC-AI2 reasoning eval
- `gsm8k/` — grade-school math (used in benchmark matrix, n=50 default)
- `hellaswag/` — commonsense reasoning
- `humaneval/` — code generation eval (used, n=10 default — small for cost)
- `mbpp/` — Python coding eval
- `oasst1/` — OpenAssistant conversations

Provenance: `data/external/MANIFEST.json`. Pulled by `scripts/download_datasets.py` (Phase 03 SL-T-03-03, done).

### 1.5 Raw / corpus artifacts

| File | Bytes | Purpose |
|---|---|---|
| `data/multitask_combined.jsonl` | 7.7 MB | Active training input (gitignored — derivable) |
| `data/openmathinstruct_5k.jsonl` | 5.5 MB | Math training input |
| `data/monorepo_corpus.txt` | 10.9 MB | Phase 02 era ingest of monorepo (legacy) |
| `data/reasoning.txt` | 2.5 MB | Phase 02 reasoning corpus (legacy) |
| `data/gad_corpus.txt` | 74 KB | gad-CLI corpus (text) |
| `data/gad_command_surface.txt` | 20 KB | dump of `gad --help` surface (used for vocab anchoring) |
| `data/.gad_help_root.txt` | 12 KB | root help cache |
| `data/gad_supported_stacks.json` | 49 lines | stack registry for monorepo ingest filter |
| `data/knowledge_graph.gml` | 605 KB | Phase 02 knowledge-graph artifact |
| `data/swe_bench_slice_v1.json` | 1.6 KB | locked 50-issue SWE-bench slice (30 Lite + 20 Verified) |

### 1.6 Raw telemetry exports (consumed by ingest)

| Path | Bytes | Source |
|---|---|---|
| `data/raw/2026-05-06/events.jsonl` | 90 MB (gitignored) | `gad telemetry export` from gad-monorepo phase 145 |
| `data/raw/2026-05-06/MANIFEST.json` | 563 B (tracked) | sha256-stamped manifest |

---

## 2. Data quality tiers

Per `slm-learning-041` schema:

| Tier | Definition | Examples in repo |
|---|---|---|
| **gold** | Human-reviewed, hand-curated | `gad_tool_pairs.jsonl` (153 hand seeds) |
| **silver** | Frontier agent + automated checks | `tool_use_pairs.jsonl` (real Claude-Code traces); `sft_basic` / `sft_reasoned` (real Claude responses + reasoning) |
| **bootstrapped** | Programmatically grounded from filesystem (no LLM teacher) | `agent_corpus_gad-doc-verifier.bootstrapped.jsonl` (475 + 264) |
| **synthetic** | Haiku paraphrase / augmentation | `distilled_pairs.jsonl` (630 from haiku-4-5) |
| **negative** | Failure / counterexample | (none yet — TODO: mine from `experiments/runs/*/manifest.json` failures + skeleton revivals) |

---

## 3. Generated training run artifacts

`experiments/runs/<name>/` per run:
- `manifest.json` — config snapshot + final metrics + git sha
- `train.log` — training stdout
- `config.snapshot.json` — config at train time
- `adapter/` — adapter weights (gitignored: `.safetensors`, `.bin`)
- `eval/<benchmark>.json` — per-benchmark eval results

Active run dirs:
- `baseline_repro/` (Phase 03 sweep, 0/30)
- `higher_lr/` (Phase 03 sweep, 0/30 after re-eval; was sampling noise)
- `lower_lr_longer/`, `more_epochs/`, `more_pairs/` (Phase 03 sweep)
- `stage25_gad_tools_lora/` (9/30, 30%)
- `stage25_gad_tools_lora_higher_lr/` (12/30, 40%)
- `stage25_qwen15_instruct_control/` (22/30, 73.3%)
- `stage25_qwen15_distill_reasoning/` (8/30, 26.7%)
- `stage25_qwen15_instruct_control_bf16/` (bf16 wall-time validation)
- `stage25_qwen15_instruct_math/` (math 1.5B, 25/50 GSM8K)
- **`stage25_qwen15_multitask/` (in flight, ~50% trained at audit time)**

Hub publications (per `slm-learning-023`): `scrubster/dr-stein-*` namespace on HuggingFace Hub.

| Hub repo | Score (best eval) |
|---|---|
| `scrubster/dr-stein-stage25-qwen15-instruct-v2` | **30/30 (100%) GAD-tools** |
| `scrubster/dr-stein-stage25-qwen15-instruct-control` | 22/30 (73.3%) GAD-tools |
| `scrubster/dr-stein-colab-qwen15-tooluse-sanity` | loss 0.39, 90% token acc |
| `scrubster/dr-stein-colab-cli` (3B variant) | 30/30 GAD-tools (3B saturates same eval) |
| `scrubster/dr-stein-colab-qwen15-math-5k` | 25/50 GSM8K |

---

## 4. Sources by extraction script

| Script | Output corpus | Status |
|---|---|---|
| `scripts/distill_gad_pairs.py` | `data/distilled_pairs.jsonl` (630) | active — haiku-4-5 subagent teacher |
| `scripts/extract_tool_use_pairs.py` | `data/tool_use_pairs.jsonl` (789) | active — reads `.planning/.trace-events.jsonl` |
| `scripts/extract_agent_corpus.py` | `data/agent_corpus_*.jsonl` reservations | active — Phase 04 SL-T-04-07 |
| `scripts/synth_doc_verifier_pairs.py` | `data/agent_corpus_gad-doc-verifier.bootstrapped*.jsonl` | active — bootstrapped data tier |
| `scripts/ingest_gad_telemetry.py` | `data/processed/<run-id>/sft_*.jsonl` | active — workstream A of cross-instance bridge |
| `scripts/download_datasets.py` | `data/external/{arc,gsm8k,humaneval,mbpp,...}/` | active — HF dataset puller |

---

## 5. Sensitive-data risk assessment

| Source | Risk | Mitigation |
|---|---|---|
| `data/raw/<date>/events.jsonl` | **HIGH** — contains real OAuth tokens, API keys, session content | gitignored; events.jsonl never pushed |
| `data/processed/<date>/sft_*.jsonl` | **MEDIUM** — redacted via `scripts/ingest_gad_telemetry.py` redaction layer (Google OAuth, refresh, Slack, Stripe, Bearer, generic api_key, long b64) | gitignored; regeneratable from raw + script |
| `data/agent_corpus_gad-doc-verifier.bootstrapped.jsonl` | LOW — paths + claims, redacted by `scripts/synth_doc_verifier_pairs.py` | tracked in git, secret-checked |
| `data/tool_use_pairs.jsonl` | LOW — extracted from local trace events; no external content | tracked |
| `data/openmathinstruct_5k.jsonl` | NONE | tracked |
| `data/gad_tool_pairs_v2.jsonl` | NONE | tracked |
| `data/multitask_combined.jsonl` | derived | gitignored |

GitHub push-protection blocked one corpus push during this session (commit reset, redaction layer added in `f01fce2`). All future ingests apply redaction at extraction time.

---

## 6. What can train what (cohort table)

| Specialist target | Corpus | Pairs | Status |
|---|---|---|---|
| CLI translator | `gad_tool_pairs_v2.jsonl` | 783 | **trained = 30/30** |
| Math reasoner | `openmathinstruct_5k.jsonl` | 5,000 | trained = 25/50 GSM8K |
| Tool-use coder | `tool_use_pairs.jsonl` + `sft_tooluse.jsonl` | 789 + 4,841 = 5,630 | sanity trained; expanded corpus available |
| Doc-verifier (SL-T-04-09) | `agent_corpus_gad-doc-verifier.bootstrapped*` | 475 + 264 = 739 | corpus ready, untrained |
| Multi-task generalist (SL-T-04-03) | `multitask_combined.jsonl` | 6,572 | **training in flight** |
| Code-completion (HumanEval-targeted) | none yet | 0 | open gap — extract from telemetry response shape OR add HumanEval-style synthetic |
| Routing classifier | `.planning/.gad-log/<date>-routing.jsonl` (empty — see runtime-substrate audit gap) | 0 | open gap — wire `logRoutingDecision()` first per gad-monorepo audit |
| Reranker / judge | `data/processed/<date>/sft_*.jsonl` accept/reject pairs | accumulating | Phase 05 first SLM target after doc-verifier |
| Codebase attention classifier | `.planning/.trace-events.jsonl` + git history features | derived at train time | per `slm-learning-072` |
| Per-domain (project-tagged per `slm-learning-079`) | filter telemetry by envelope `project` field | varies | Phase 148 (gad-monorepo) + slm-learning trainer |

---

## 7. Eval pairing — does each corpus have a corresponding eval?

| Corpus | Has eval? | Eval source |
|---|---|---|
| `gad_tool_pairs_v2.jsonl` | YES | `promptfoo-gad-tools.yaml` (30 cases) |
| `openmathinstruct_5k.jsonl` | YES | GSM8K (`scripts/eval_gsm8k.py`, n=50) |
| `tool_use_pairs.jsonl` | partial | training-loss only; no held-out tool-use eval set |
| `agent_corpus_gad-doc-verifier.bootstrapped*` | NO | needs held-out eval split + F1/accuracy metric (see eval-monitoring audit) |
| `multitask_combined.jsonl` | YES (composite) | gad_tools + gsm8k + humaneval |
| `sft_tooluse.jsonl` | NO | needs tool-use eval set |
| Code-completion | YES (would-be) | HumanEval, MBPP — but no code training data yet, so 0/10 HumanEval across all |
| SWE-bench | scaffold | `scripts/eval_swebench.py` + `data/swe_bench_slice_v1.json` (50 issues, 30 Lite + 20 Verified, status=scaffold) |

---

## 8. Gaps + recommended next data work

| Gap | Action | Cost |
|---|---|---|
| Doc-verifier held-out eval split | randomly sample 50 from 739, redact label, regenerate, compare | 1 hr |
| Tool-use eval set | use 50-pair held-out split from `tool_use_pairs.jsonl` (was-real-trace baseline) | 1 hr |
| HumanEval training data — currently 0 pairs of code completion shape | extract function-body completions from telemetry response envelopes (needs role-aware filter beyond current ingest); OR pull `nuprl/MultiPL-T-py` / `bigcode/starcoderdata` Python subset | 2-4 hrs |
| Negative tier — no failure-case training data | mine `experiments/runs/*/manifest.json` for failed runs + extract preference pairs (winning vs losing config); skeletons revived after failure also feed this | 2 hrs |
| Magicborn structured game data corpus | none yet — `slm-learning-078` calls for it; need to harvest narrative project + write JSON-schema validator | 1 week (when narrative line activates) |
| Routing decision log empty | gap blocked by `logRoutingDecision()` having zero callers in gad-monorepo (see runtime-substrate audit) — needs framework PR | cross-project |
| Telemetry ingest produces gitignored output → not reproducible cross-machine | producer-side redaction (recommend to global Claude per closeout) OR encrypted-at-rest data lake | medium |
| Per-project cohort filtering | exists in envelope schema (`project` field) but ingest doesn't yet filter — easy add to `ingest_gad_telemetry.py` | 30 min |

---

*Audit author: claude-code (opus-4-7 1M ctx). Counts derived from `wc -l data/*.jsonl` + `experiments/INDEX.md` + state-log entries.*
