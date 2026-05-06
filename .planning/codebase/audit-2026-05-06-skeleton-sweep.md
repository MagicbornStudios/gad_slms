# Skeleton / Fossil Sweep — slm-learning

**Date:** 2026-05-06
**Scope:** `slm-learning/` only (gad-monorepo skeletons enumerated separately in `custom_portfolio/.planning/codebase/audit-2026-05-06-monorepo-topology.md` §8)

Per concern `.planning/concerns/skeleton-system.md` and decisions
`slm-learning-056..058` + `slm-learning-066..067`. Targeted sweep
only (per `slm-learning-067`); deeper archaeology deferred until the
classifier is mature.

---

## 1. Skeleton candidates found

### Code skeletons (file-level)

| Path | Status recommendation | Reason |
|---|---|---|
| `scripts/00_tokenizer_lesson.py` | **prototype/museum** | Phase 01 lesson scaffold, never extended; superseded by Stage 2.5 pipeline |
| `scripts/01_train_char_lm.py` | **museum** | Pre-Qwen char-LM training, fully superseded by `scripts/18_stage25_finetune.py` |
| `scripts/02_make_reasoning_data.py` | museum | Phase 02 reasoning corpus prep, replaced by HF dataset pulls |
| `scripts/03_train_reasoning_lm.py` | museum | Phase 02 standalone trainer, replaced by `18_stage25_finetune.py` + TRL+PEFT |
| `scripts/04_generate.py` | museum | Phase 02 generation script, replaced by `serve_adapter.py` + `gad_nl.py` |
| `scripts/05_eval_reasoning.py` | museum | Phase 02 eval, replaced by `eval_benchmark_matrix.py` |
| `scripts/06_learning_tui.py` + `06_learning_tui.css` | active | Dr. Stein lesson TUI — keep |
| `scripts/07_inspect_reasoning_data.py` | museum | One-off inspector, replaced by direct JSONL inspection |
| `scripts/08_compile_gad_corpus.py` | zoo (deprecated, may be referenced) | gad CLI corpus compiler; superseded by `extract_*` scripts but may still be invoked |
| `scripts/09_finetune_dr_stein.py` | zoo | Phase 02 SmolLM2-base finetune entry point; superseded by Stage 2.5 + Qwen base per `slm-learning-022` |
| `scripts/10_grow_network.py` | **museum** | Network morphism layer growth — explicitly OUT per `slm-learning-050` |
| `scripts/11_upcycle_to_moe.py` | museum | MoE upcycling experiment, deferred per phase plan reorg |
| `scripts/12_mlops_manager.py` | active | bf16 quantization sweeper — keep per `slm-learning-005` |
| `scripts/13_ingest_monorepo.py` | zoo | replaced by `ingest_gad_telemetry.py` for ongoing ingest; keep for one-off monorepo sweeps |
| `scripts/14_build_knowledge_graph.py` | museum | Phase 02 knowledge-graph build, single output preserved at `data/knowledge_graph.gml` |
| `scripts/15_build_rag_index.py` | museum | Phase 02 RAG, never wired |
| `scripts/16_reasoning_training.py` | zoo | Phase 02 stage-2 trainer; preserved for `dr_stein.pt` reproducibility |
| `scripts/17_dpo_training.py` | zoo | Phase 02 stage-3 DPO; preserved for `dr_stein.pt` reproducibility |
| `scripts/18_stage25_finetune.py` | **active** | the canonical trainer |
| `scripts/refresh_pressure.js` | unknown | one-line JS file, purpose unclear — investigate |
| `projects/llm-from-scratch/` (sibling, not in this repo) | dead | per gad-monorepo audit §7 — superseded by this repo entirely |

### Run / log skeletons

| Path | Status | Reason |
|---|---|---|
| `experiments/runs/.eval-distill-humaneval-2048.log` | museum | log of falsified hypothesis (decision `slm-learning-027`) |
| `experiments/runs/.hf-job-sweep1.log` | museum | one-off cloud sweep log |
| `experiments/runs/.hub-push-control*.log` | museum | hub-push diagnostic logs |
| `experiments/runs/.sweep-*.log` (12+ files) | museum | per-sweep stdout captures; gitignored as of `758a180` |
| `experiments/runs/.multitask-overnight.log` | active (this session's training) | will move to museum after run completes |
| `experiments/runs/.synth-multiroot.log` | active (this session) | will move to museum |
| `experiments/runs/baseline_repro/` | zoo | first sweep checkpoint; preserve for Phase 03 reproducibility |
| `experiments/runs/{higher_lr,lower_lr_longer,more_epochs,more_pairs}/` | zoo | Phase 03 sweep checkpoints; preserve |
| `experiments/runs/stage25_gad_tools_lora{,_higher_lr}/` | zoo | superseded by `instruct_v2` (30/30) |
| `experiments/runs/stage25_qwen15_distill_reasoning/` | museum | distillation hypothesis falsified per `slm-learning-027` |

### Data skeletons

| Path | Status | Reason |
|---|---|---|
| `data/gad_tool_pairs.jsonl` (153 seeds) | zoo | superseded by `_v2` (783); preserve for v1→v2 lineage |
| `data/sft_pairs.json` (1001) | zoo | Phase 02 SFT data; superseded by per-shape JSONLs |
| `data/reasoning_pairs.json` (1981) | zoo | Phase 02 reasoning data; superseded |
| `data/dpo_pairs.json` (401) | zoo | preserved for `dr_stein.pt` lineage |
| `data/monorepo_corpus.txt` (10.9 MB) | zoo | Phase 02 ingest snapshot; superseded by per-script extractors |
| `data/reasoning.txt` (2.5 MB) | zoo | Phase 02 reasoning text dump |
| `data/openmathinstruct_2k.jsonl` (2000) | zoo | superseded by 5k variant |
| `data/multitask_combined.jsonl` (6572) | active (this session) | gitignored, regeneratable |
| `data/agent_corpus_gad-doc-verifier.jsonl` (0 lines) | zoo | empty placeholder; consider removing |
| `data/agent_corpus_gad-assumptions-analyzer.jsonl` (0 lines) | zoo | empty placeholder |
| `data/agent_corpus_gad-codebase-mapper.jsonl` (2 lines) | zoo | minimal starter |
| `data/.gad_help_root.txt` (12 KB) | active | help cache referenced by extractors |

### Soul / planning skeletons

| Path | Status | Reason |
|---|---|---|
| `narrative/souls/speech-native-builder.md` | **museum** | retired soul; preserved as historical only per `narrative.toml` comment |
| `.planning/02-CONTEXT.md` | zoo | Phase 02 era context dump; preserved |
| `.planning/HANDOFF-2026-05-04.md` | zoo | one-off session handoff; superseded by handoff queue + bridge directory |
| `.planning/tasks/03-04.json`, `03-06.json`, `03-07.json` | active (just stamped) | Phase 03 closeout — these are the recently-stamped task records |
| `.planning/phases/PHASE-05*.md`, `PHASE-06*.md` | active | new phase plans |

---

## 2. Recommended actions

Per `slm-learning-067` (targeted sweep, time-boxed):

| Action | Files | Notes |
|---|---|---|
| **gitignore the .log files** | `experiments/runs/.*.log` | DONE in `758a180` |
| Consider `tmp/museum/` / `tmp/zoo/` directories | none yet — `tmp/` does not exist in slm-learning | per `slm-learning-066`, museum (frozen) + zoo (life-support) split. Create on first move. |
| Add `# SKELETON: deprecated YYYY-MM-DD reason: ...` markers to scripts/00–05 | `scripts/0[0-5]_*.py` | per `slm-learning-057` stage 1 (in-place marker) |
| Decide fate of `scripts/refresh_pressure.js` | 1 file | investigate-or-remove |
| Remove empty placeholder JSONLs | `data/agent_corpus_gad-doc-verifier.jsonl` (0), `agent_corpus_gad-assumptions-analyzer.jsonl` (0) | OR keep as reservation slots for future trace-extracted corpora |

Don't move scripts/0X yet — preserve git history. The marker (stage 1) is cheap; the move (stage 2) waits until age-threshold (60 days with marker AND zero inbound references).

---

## 3. Cross-reference to gad-monorepo skeletons

From `custom_portfolio/.planning/codebase/audit-2026-05-06-monorepo-topology.md` §8:

| Path | Notes |
|---|---|
| `apps/portfolio/` | DEPRECATED, slated for `archive/portfolio/` |
| `projects/llm-from-scratch/` | DEAD — superseded by this repo (`slm-learning`) |
| `.tmp/` (many subdirs) | YES — many fossils; gitignored |
| `.claw/` | OMX/claw-code remnant, removed per memory |
| `bash.exe.stackdump` files | crash dumps to delete |

These don't live in slm-learning, but: `projects/llm-from-scratch` is the **dead sibling** that preceded slm-learning. Memory note `project_slm_learning_official_home` says "fuck llm-from-scratch, use slm-learning." That's the canonical interment record.

---

*Sweep author: claude-code (opus-4-7 1M ctx). Time-boxed per `slm-learning-067` to <4 hours of agent attention; this single pass is ~30 minutes of read.*
