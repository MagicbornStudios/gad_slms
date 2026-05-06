# Eval + Monitoring Inventory — slm-learning

**Date:** 2026-05-06
**Repo:** `C:/Users/benja/Documents/slm_learning/`
**Auditor:** claude-code (this session)

---

## 1. What exists

### 1.1 Benchmark harnesses (Python)

| Script | Benchmark | Status | Notes |
|---|---|---|---|
| `scripts/eval_humaneval.py` | HumanEval (code) | active | n=10 default; subprocess + 10s timeout per problem |
| `scripts/eval_gsm8k.py` | GSM8K (math) | active | n=50 default; numeric-answer parsing |
| `scripts/eval_checkpoint.py` | gad-tools (CLI translation) | active | pure-Python grader, alt to promptfoo |
| `scripts/eval_benchmark_matrix.py` | matrix (gad_tools + humaneval + gsm8k) | active | per-checkpoint eval orchestrator |
| `scripts/eval_all_experiments.py` | sweep eval | active | runs matrix across all `experiments/runs/<name>/` |
| `scripts/eval_swebench.py` | SWE-bench | **scaffold** | 50-issue slice locked at `data/swe_bench_slice_v1.json`; real scoring pending phase 06 SL-T-06-03/04 |

Per `AGENTS.md` "Eval Pipeline Conventions":
- temp=0.0 (greedy)
- GPU when available
- EOS early-stop ON
- Per-checkpoint eval JSONs land beside the checkpoint at `experiments/runs/<name>/eval/<benchmark>.json`
- HumanEval candidates run in subprocess with 10s timeout

### 1.2 Promptfoo configs (npx-based, prompt regression)

| File | Suite | Cases |
|---|---|---|
| `promptfoo.yaml` | `gad-tool-call-3` (legacy 3-case) | 3 |
| `promptfoo-gad-tools.yaml` | `gad-tool-call-30` | **30** (the canonical CLI eval suite, what v2 hits 30/30 on) |

### 1.3 Eval result format

JSON (per benchmark):
```json
{
  "name": "stage25_qwen15_instruct_v2",
  "checkpoint": "scrubster/dr-stein-stage25-qwen15-instruct-v2",
  "benchmark": "gad_tools",
  "n": 30,
  "passed": 30,
  "score": 1.0,
  "wall_seconds": 50.4,
  "device": "cuda",
  "temperature": 0.0,
  "max_new_tokens": 50,
  "per_case": [...]
}
```

### 1.4 Observability / monitoring

| Tool | Status | Use case |
|---|---|---|
| **promptfoo** | installed, used | prompt regression (the 30-case GAD-tool suite) |
| **Phoenix (Arize)** | NOT installed | trace observability — proposed in `slm-learning-053` |
| **Langfuse** | NOT installed | alternative tracing |
| **lm-evaluation-harness** | NOT integrated | EleutherAI suite — proposed in `slm-learning-053` for HumanEval/MBPP/GSM8K/ARC/HellaSwag at scale |
| **Weights & Biases** | NOT integrated | training run telemetry — left out per `slm-learning-053` (state log + JSONL traces are enough for now) |
| **Aim** | NOT integrated | alternative training telemetry |
| **HELM** | NOT integrated | comprehensive eval framework |
| **Inspect-AI (UK AISI)** | NOT integrated | OSS modern eval framework |
| `experiments/INDEX.md` | active | hand-maintained per-run ledger |
| `experiments/REPORT.md` | active | per-sweep narrative report |
| `.planning/.trace-events.jsonl` | active | every gad CLI call + agent-emitted trace |
| `.planning/.gad-log/<date>.jsonl` | active | one JSONL per day of gad CLI usage |

### 1.5 Manifest schema (per run)

`experiments/runs/<name>/manifest.json`:
- `name`, `base_model`, `adapter` type, `compute_target`
- `lora` config (r, alpha, dropout, target_modules)
- `data` (source, path, max_length, fields, system_prompt)
- `training` (epochs, lr, batch_size, gradient_accumulation, bf16/fp16, gradient_checkpointing, seed, save_strategy)
- `eval.benchmarks` list, `temperature`, `max_new_tokens`
- `hub` (publish flag, private flag, repo id)
- After train: `final_loss`, `wall_seconds`, `git_sha`, `eval_results` populated

---

## 2. What is missing / stale

| Gap | Severity | Action |
|---|---|---|
| **No regression detection automation** | high | A candidate that regresses by >5pp on any benchmark vs the prior canonical should auto-flag in `eval_candidate.py`. Logic is in place, baseline pointer isn't. |
| **No skeleton-recognition eval dimension** (per `slm-learning-065`) | medium | Gated on skeleton classifier existing first |
| **No constitution-impact eval** (per `slm-learning-060`) | medium | Need an `eval_constitution.py` that runs the same prompt set with vs without soul system prompt; arm C of the A/B/C |
| **No cross-CLI variance eval** (per `slm-learning-043`) | medium | Need fixture that sends same prompt through claude-code / codex-cli / gemini-cli / curl all hitting our local vLLM endpoint and compares outputs |
| **No SWE-bench / LiveCodeBench real harness** | high (for phase 06 ambition) | Phase 06 SL-T-06-03/04 — patch_generator + test_runner; harness vendoring; Docker-on-Windows fallback to subprocess |
| **No artifact eval** (rubric-based score on real artifacts produced by candidates, not just benchmark accuracy) | medium | Phase 04 task SL-T-04-05 (game-task A/B/C eval) is planned but not yet started |
| **No human-preference data pipeline** | medium | `gad_nl.py` (just shipped) logs accept/reject events to `.planning/.trace-events.jsonl`; need an aggregator that turns those into DPO pairs |
| **No latency / cost tracking on eval results** | low | Add `wall_seconds` + estimated tokens + estimated cost to every eval result; useful for cost-vs-quality plots |
| **No external dashboard** | low | If we want a public-facing "where slm-learning is on benchmarks today" surface, would need a static page generated from manifests + eval JSONs |
| **No standard for "evidence tier"** declaration in manifests | medium | Per `slm-learning-071` T1..T4 should be a field on every eval result |

---

## 3. Recommended minimal eval stack (next phase)

Prioritized:

1. **Wire `eval_candidate.py` baseline pointer.** Maintain `experiments/runs/CANONICAL.json` (just `{name, hub_id, scores: {gad_tools: 1.0, gsm8k: 0.5, humaneval: 0.0}}`) so every candidate has something to regress against. ~30 LOC.
2. **Add evidence_tier field to eval JSON.** Per `slm-learning-071` T1..T4 declared at write time. Trivial schema add.
3. **Phoenix tracing of vLLM serving + gad_nl wrapper.** Local-friendly, OSS, no cloud signup. Captures every NL→CLI suggestion + accept/reject for preference data. ~2 hr setup.
4. **Held-out doc-verifier eval split.** 50 pairs sampled from the 739 bootstrapped, label hidden, run inference, F1 score. ~1 hr.
5. **Cross-CLI variance fixture.** Same prompt, four CLI shells, our endpoint. Per `slm-learning-043`. ~2 hr.
6. **SWE-bench-Lite real run on a 5-issue mini-slice (smoke before phase 06 full slice).** Patch generator + test runner against 5 known-easy Lite issues. Time-boxed. ~1 day.
7. **lm-evaluation-harness integration** for ARC/HellaSwag/MBPP at scale. Lower priority since our v2/math results already validate the small-eval signal.

---

## 4. Decision references

- `slm-learning-053` — Phoenix + lm-eval-harness as additions
- `slm-learning-060` — constitution-impact arm C eval design
- `slm-learning-065` — skeleton recognition gated on classifier
- `slm-learning-071` — T1..T4 evidence-tier policy on every claim
- `slm-learning-043` — cross-CLI variance is a first-class concern

---

*Audit author: claude-code (opus-4-7 1M ctx). Counts derived from `experiments/INDEX.md` + script enumeration.*
