# Phase 06 — SWE-bench Integration

## Status

`planned` (depends on phase 04 substrate)

## Goal

Wire **SWE-bench-Lite** and **SWE-bench-Verified** into the eval
matrix per decision `slm-learning-053`. Score every candidate adapter
on a fixed SWE-bench slice as part of the promotion gate. Verdent-style
coding-agent eval discipline.

## Why this phase exists

User-requested 2026-05-06: "we need SWE benchmarks that Verdent is so
keen on." Existing eval matrix covers HumanEval / MBPP / GSM8K / ARC /
HellaSwag / GAD-tools — none of these stress real-repo bug-fix
ability. SWE-bench is the canonical hard benchmark for repo-level
coding-agent capability and the natural addition for the eval stack
(decision `slm-learning-053`).

## What is SWE-bench

- **SWE-bench** (Jimenez et al. 2023): 2294 real GitHub issues from 12
  Python repos, paired with the test that the fix needs to make pass.
- **SWE-bench-Lite**: 300-issue curated subset, faster to run,
  community-favorite for iteration.
- **SWE-bench-Verified**: 500-issue subset annotated by humans for
  high-quality issue-test alignment. The harder of the two but more
  defensible.

The harness gives the agent the issue text + the repo at the bug
commit; the agent produces a patch; the harness applies the patch and
runs the test suite; pass/fail is the score.

## Why this is hard at our scale

A 1.5B–7B SLM cannot solve SWE-bench problems end-to-end at
frontier-level rates. **That is fine.** The point is:

- Establish a baseline number for our candidates so we can track
  progress over time.
- Identify which candidates regress on SWE-bench shape (adapter
  trained for narrow shape may break code editing).
- Use SWE-bench as a forcing function: which task shapes are our
  specialists actually useful for?
- Provide a defensible external benchmark when claims are made
  (decision `slm-learning-071` — evidence-tiered capability policy).

We will run a **fixed slice** (e.g., 50 issues) per candidate, not the
full 2294, to keep iteration cost bounded. The slice is locked per
phase; comparisons across candidates use the same 50 issues.

## Architecture

```
[ candidate adapter ] ──→ [ swe-bench harness ] ──→ [ patch generator ] ──→ [ test runner ] ──→ [ result.jsonl ]
                                  │                                                                      │
                                  └─── reads slm-learning-fixed-slice.json ───┐                           │
                                                                               ↓                          ↓
                                                              [ baseline-Opus + bare-base comparisons ] [ promotion gate input ]
```

### Components

- `scripts/eval/swe_bench/harness.py` — wraps the official SWE-bench
  evaluation harness (or our own minimal port if licensing permits).
- `scripts/eval/swe_bench/patch_generator.py` — runs the candidate
  adapter (via the vLLM serving substrate from phase 04) and extracts
  a patch from its response.
- `scripts/eval/swe_bench/test_runner.py` — applies patch, runs tests
  in the issue's repo + commit, captures pass/fail.
- `scripts/eval/swe_bench/result_schema.py` — JSON schema for results
  (issue_id, candidate_id, patch_chars, pass, runtime_s, error_class).
- `data/swe_bench_slice_v1.json` — locked slice of 50 issue ids used
  for cross-candidate comparison.

### Slice locking

The slice is selected once and stored as a static JSON file. The
selection criteria:

- 30 issues from SWE-bench-Lite (faster, easier baseline)
- 20 issues from SWE-bench-Verified (harder, more defensible)
- diverse repos (not all from one repo)
- diverse difficulty bands (mix of one-line fixes and multi-file
  fixes per the official difficulty annotations)

Slice locked = same 50 issues forever (until the phase explicitly
retires the slice and locks v2).

## Result schema

```json
{
  "candidate_id": "scrubster/dr-stein-multitask-v1",
  "harness_commit": "<sha>",
  "slice_version": "v1",
  "issues": [
    {
      "issue_id": "django__django-12345",
      "pass": false,
      "patch_chars": 482,
      "runtime_s": 47.3,
      "error_class": "test_failure | patch_apply_failure | timeout | parse_failure | none"
    }
  ],
  "summary": {
    "passed": 7,
    "failed": 43,
    "pass_rate": 0.14,
    "vs_bare_base": "+3 pp",
    "vs_opus_baseline": "-31 pp",
    "evidence_tier": "T2"
  }
}
```

## Task breakdown

| ID | Goal | Status |
|---|---|---|
| SL-T-06-01 | Vendor / port the SWE-bench harness for local Windows execution (Docker-free if possible) | planned |
| SL-T-06-02 | Lock the 50-issue slice — `data/swe_bench_slice_v1.json` | planned |
| SL-T-06-03 | Implement `patch_generator.py` against the vLLM serving endpoint | planned |
| SL-T-06-04 | Implement `test_runner.py` with sandboxing (subprocess + timeout per slm-learning math/code patterns) | planned |
| SL-T-06-05 | Run baseline: bare Qwen2.5-1.5B-Instruct on the slice. This is the absolute floor we beat | planned |
| SL-T-06-06 | Run baseline: bare Opus on the slice. This is the ceiling we acknowledge we cannot match (per slm-learning-070) | planned |
| SL-T-06-07 | Wire SWE-bench result into `eval_benchmark_matrix.py` so every candidate gets scored automatically | planned |
| SL-T-06-08 | Add `swe_bench_slice_v1` to the promotion-gate criteria | planned |

## Acceptance criteria

- Slice is locked at 50 issues, ids visible in `data/`.
- Bare-base + bare-Opus baselines exist with full result.jsonl.
- Every candidate trained in phase 05 onward produces a SWE-bench
  result alongside its other eval scores.
- Promotion gate (slm-learning-032) reads SWE-bench result as one of
  its inputs.
- A candidate that regresses on SWE-bench by >5 percentage points
  vs the previous best on the same shape is automatically blocked from
  promotion (Verifier verdict = `refuted`).

## Risk register (from Critic)

- **License surface of SWE-bench harness**: the official harness is MIT
  but vendored deps may be restrictive. Mitigation: minimal port with
  documented license trail.
- **Docker dependency**: SWE-bench traditionally uses Docker. We are
  on Windows, no Docker by default. Mitigation: subprocess + Python
  venv per repo; if it breaks, accept SWE-bench-Lite-Python-pure
  subset only.
- **Cost cliff on bare Opus baseline**: full 50-issue Opus run could
  cost real money. Mitigation: cap baseline run at slice-v1, document
  the dollar cost in the manifest, reuse baseline across all
  candidates rather than re-running.
- **Skeleton risk**: the harness is itself code that may bit-rot. Mark
  the harness commit in every result so old results remain
  interpretable.

## References

- decision `slm-learning-053` (eval stack additions)
- decision `slm-learning-070` (realistic ceiling — SWE-bench is where
  the ceiling is most visible)
- decision `slm-learning-071` (evidence-tiered capability policy —
  SWE-bench is a T2/T3 evidence source)
- concern `.planning/concerns/git-fluency.md` — patch generation IS
  git fluency under the hood
- phase 05 plan — produces the candidates that this phase scores
