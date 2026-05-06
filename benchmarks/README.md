# Benchmark Registry

Per ChatGPT directive 2026-05-06 + decision `slm-learning-053` /
`slm-learning-071`. Every model candidate declares which benchmarks
it must pass. No declaration → no promotion.

## Layout

Each benchmark gets a directory with:

```
benchmarks/<name>/
  manifest.json     ← metadata (n, source, eval script, baseline scores)
  README.md         ← human description
  fixtures/         ← test cases (gitignored if large or sensitive)
  baselines/        ← scored runs of bare base models, frontier models
```

## Current benchmarks

| Name | Source script | Default n | Status |
|---|---|---|---|
| `gad_tools_v2` | `scripts/eval_checkpoint.py` + `promptfoo-gad-tools.yaml` | 30 | active — v2 hits 30/30 |
| `gsm8k` | `scripts/eval_gsm8k.py` | 50 | active |
| `humaneval` | `scripts/eval_humaneval.py` | 10 | active |
| `swebench_v1` | `scripts/eval_swebench.py` | 50 (slice locked at `data/swe_bench_slice_v1.json`) | scaffold |
| `doc_verifier` | (planned: `scripts/eval/eval_doc_verifier.py`) | 50 (held-out) | planned |
| `json_validity` | (planned: trivial regex/parse check) | per-task | planned |
| `tool_use_sanity` | (planned: scripts/eval/eval_tool_use.py) | 50 | planned |
| `attention_lane` | (planned: `tests/test_attention_ranking.py`) | per-fixture | planned |
| `runtime_router` | (planned, gated on G1) | tbd | blocked |

## manifest.json schema

```json
{
  "name": "doc_verifier",
  "version": "v1",
  "source_dataset": "data/eval/doc_verifier_holdout.reshaped.jsonl",
  "n": 50,
  "metric_primary": "f1_macro",
  "metric_secondary": ["accuracy", "json_validity_rate"],
  "baseline_scores": {
    "bare_qwen2.5-1.5b-instruct": {"f1_macro": 0.42, "accuracy": 0.50, "json_validity_rate": 0.35},
    "frontier_opus_4_7": {"f1_macro": 0.92, "accuracy": 0.96, "json_validity_rate": 0.98}
  },
  "promotion_threshold": {"f1_macro": 0.85, "json_validity_rate": 0.90},
  "evidence_tier_floor": "T2",
  "decision_refs": ["slm-learning-053", "slm-learning-071"]
}
```

## Promotion rule

A candidate qualifies for `staging` (per `slm-learning-082`) only when:

1. It scores ≥ `promotion_threshold` on every primary metric of every
   declared benchmark.
2. It does not regress more than 5 percentage points vs the current
   `canonical` on any other declared benchmark in the registry.
3. It declares an `evidence_tier` matching or exceeding the
   benchmark's `evidence_tier_floor`.

A candidate qualifies for `canonical` only via `scripts/delta/
promote_atomic.py` with `--decision-id` + `--gate-evidence`. Per
`slm-learning-051`, manual stamp always.
