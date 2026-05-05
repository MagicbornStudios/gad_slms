# Overnight Sweep Report — 2026-05-05 02:30

You went to bed at ~01:00 with "knock out tons, evaluate, get the benchmarks,
pull down the standard training corpuses, set up for training many models
quickly." This is what got done.

## TL;DR

- **Real Dr. Stein baseline established for the first time** — 0/30 on the
  30-case GAD-tool-call eval. Prior runs were *not* baselines because of a
  silent random-weight bug (see "Bugs found" below).
- **5 hyperparameter experiments trained on GPU**, all 5 produced
  checkpoints. Wall times 8-29 min each (Stage 2 reasoning only).
- **First non-zero scores on the eval:** `higher_lr` and `lower_lr_longer`
  both hit **1/30 (3.3%)** — moved off the floor.
- **Standard public corpuses pulled** to `data/external/` (~150K examples).
- **Training factory operational:** drop a YAML in `experiments/configs/`,
  `scripts/run_sweep.py` runs the matrix, eval auto-grades each checkpoint.

## Reference baseline (pre-sweep dr_stein.pt)

**0/30 (0.0%)** on `promptfoo-gad-tools.yaml`. Confirmed by both the
30-case promptfoo run and the pure-Python `eval_checkpoint.py`.

## Sweep results

| run | epochs | lr | pairs | final_loss | wall | gad_tools | takeaway |
|-----|--------|----|-------|-----------|------|-----------|----------|
| baseline_repro     | 5  | 1e-5 | 100 | 4.1438 |  8 min | **0/30** (0.0%) | Reproduces Phase 02 defaults |
| higher_lr          | 5  | 5e-5 | 100 | **1.4744** |  8 min | **1/30** (3.3%) | Lowest loss; first non-zero score |
| lower_lr_longer    | 10 | 5e-6 | 100 | 3.9734 | 14 min | **1/30** (3.3%) | Same eval as higher_lr, slower |
| more_epochs        | 10 | 1e-5 | 100 | 2.8020 | 15 min | 0/30 (0.0%) | Lower loss did NOT translate |
| more_pairs         | 5  | 1e-5 | 200 | 2.8631 | 29 min | (eval skipped) | See "what failed" |

## What worked

- **`higher_lr` is the best run by every metric** (lowest loss at 1.47, equal
  best on eval at 1/30). 5× the default LR over a small 100-pair fine-tune
  doesn't catastrophically overfit — it just lets a 162.8M model actually
  move on tiny data.
- **The training factory** (`experiment_runner.py` + `run_sweep.py`) runs end
  to end. Sequential GPU training, deterministic checkpoint paths, manifest
  per run, INDEX.md ledger.
- **Pure-Python eval grader** (`eval_checkpoint.py`) is independent of npx
  promptfoo so eval is fast and scriptable.

## What failed (and was recovered)

1. **`scripts/16_reasoning_training.py` em-dashes broke `subprocess.run` on
   Windows.** Training itself succeeded, but `experiment_runner.py` exited
   non-zero in post-training log parsing because of cp1252/UTF-8 mismatch.
   Two checkpoints (`baseline_repro`, `higher_lr`) wrote without a
   MANIFEST.json. **Fixed in a01f24c**: PYTHONIOENCODING=utf-8 + explicit
   encoding/errors on subprocess.run + read_text(errors='replace').
   `scripts/salvage_manifest.py` reconstructs missing manifests from the
   train.log + config.snapshot.json.
2. **`more_pairs` eval got stuck.** Generation became 30-60× slower for this
   particular checkpoint (6 min/test vs 6 sec on others). Killed at 2/30 to
   avoid burning hours. Loss number is fine; eval skipped — open task.

## Bugs found and fixed (the real wins)

### `parents[4]` typo in `src/slm_from_scratch/models/dr_stein.py` (commit 03fec1a)

DrStein resolved the project root one directory too high, so checkpoint
loads silently fell back to random weights for **every prior session**.
This explains why prior training "didn't seem to help" — the TUI was never
using the artifacts. Fixed and committed; future model-wrapper subclasses
need a smoke test that prints `Loading weights from .../runs/finetuned/...`.

### `models/` ignore was unanchored (commit 03fec1a)

`.gitignore` had `models/` (matches anywhere), which silently hid
`src/slm_from_scratch/models/` (DrSteinModel, KaelModel) from version
control. Anchored to `/models/`; the wrappers are now tracked.

### Pressure cache key mismatch (commit b87bc88)

The gad-statusline.js hook reads `~/.cache/gad/pressure-<projectid>.json`
keyed by the kebab-case project id, but other writers used the underscore
form. Result: the statusline showed near-zero pressure even when the
evolution scan reported real candidate + shed signals.
`scripts/refresh_pressure.js` writes a unified snapshot folding both
operational + evolution-candidate pressure. Statusline now shows the
correct ⚡ bar (e.g. `73 evo!`).

## Artifacts on disk

- `runs/finetuned/{sft_model.pt, reasoning_model.pt, dr_stein.pt}` — Phase 02 outputs
- `experiments/runs/<config>/{checkpoint.pt, MANIFEST.json, train.log, eval_gad_tools.json}` — sweep
- `data/external/<dataset>/*.parquet` — 7 standard public corpuses
- `runs/eval/*.json` — eval results
- `experiments/INDEX.md` — append-only ledger

Note: all `.pt` files are gitignored. Manifests, logs, and eval JSON ride along.

## Update — 2026-05-05 morning

Re-ran the full matrix at **temperature 0.0 (greedy) on GPU** after fixing
three structural issues uncovered by investigating the `more_pairs` "stuck
eval":

1. `KaelModel` always loaded weights with `map_location='cpu'` and never
   moved to GPU. All prior evals ran on CPU at ~5.5s/test (164s/30).
2. `MiniLlama.generate` had no EOS early-stop; always emitted the full
   `max_new_tokens` even when the model emitted EOS after a few tokens.
3. `eval_checkpoint.py` accepted `--device` and `--temperature` but the
   former was never plumbed to the model wrapper, and the default temp
   of 0.7 added sampling variance to any "1/30" result.

After fixes (`src/slm_from_scratch/model.py`, `src/slm_from_scratch/models/{kael,dr_stein}.py`,
`scripts/eval_checkpoint.py`, `scripts/eval_all_experiments.py`), each
30-test eval now runs in **46-54 s on GPU** (vs ~165 s CPU), and
`more_pairs` completes cleanly in 46.5 s (was killed at 2/30 yesterday
because eval was crawling at ~6 min/test under nighttime CPU contention
— not a checkpoint pathology).

Corrected results:

| run | gad_tools (was) | gad_tools (temp=0.0, GPU) |
|-----|-----------------|---------------------------|
| dr_stein.pt baseline | 0/30 | **0/30** (confirmed) |
| baseline_repro | 0/30 | **0/30** (confirmed) |
| higher_lr | 1/30 | **0/30** (was sampling noise) |
| lower_lr_longer | 1/30 | **0/30** (was sampling noise) |
| more_epochs | 0/30 | **0/30** (confirmed) |
| more_pairs | (skipped) | **0/30** (now eval-able) |

**The actual baseline is 0/30 across the board.** Hyperparameter search on
this Stage-2 reasoning recipe alone is not going to move the needle —
the model has never seen `gad note add ...` etc. The training data
distribution is the bottleneck, not LR or epoch count. Item (2) below
(curated GAD-tool training pairs + Stage 2.5 fine-tune) is the only
high-leverage move.

## Update — 2026-05-05 mid-morning

Wired HumanEval + GSM8K eval harnesses against the same eval pipeline:

- `scripts/eval_humaneval.py` — pass@1 on HumanEval. Spawns each
  candidate in a fresh subprocess with a 10s timeout (safety boundary).
- `scripts/eval_gsm8k.py` — exact-match accuracy on the parsed final
  number; tolerates `#### N` markers + falls back to last-number-in-text.
- `scripts/eval_benchmark_matrix.py` — runs both benchmarks across
  every discovered checkpoint (Phase 02 stages + sweep runs), writes
  per-(checkpoint,benchmark) JSON next to the checkpoint, appends
  scored rows to `experiments/INDEX.md`.

Drafted the seed dataset for Stage 2.5:

- `data/gad_tool_pairs.jsonl` — **153 hand-curated (instruction, command)
  pairs** covering all 14 categories the GAD-tool eval probes (notes,
  tasks, state/snapshot, phases, decisions, errors, blockers, handoffs,
  evolution, projects, recipes, verify/health, file-location questions,
  disambiguation). Format is generic; the Stage 2.5 trainer wraps with
  ChatML at training time.

Replaced the OpenCode-teacher plan with a Claude-subagent teacher:

- `scripts/distill_gad_pairs.py` — calls `claude-haiku-4-5` (cheap,
  configurable) with a strict system prompt that forces a JSON array
  of paraphrases per seed pair. Default 3 paraphrases × 153 seeds
  = ~459 distilled pairs from one pass. Dry-run mode validates without
  hitting the API. Estimated ~109 K output tokens for a full pass on
  haiku-4-5 — pennies.
- Phase 03 task `SL-T-03-04` and `.planning/ROADMAP.xml` updated to
  reflect the OpenCode-out / Claude-subagent-in change.

## Update — 2026-05-05 cross-benchmark baseline

Ran `scripts/eval_benchmark_matrix.py` across 8 checkpoints
(HumanEval n=10, GSM8K n=50, temp=0.0, GPU). Results:

| checkpoint | HumanEval (pass@1) | GSM8K (acc) |
|---|---|---|
| sft_model | 0/10 (0.0%) | 0/50 (0.0%) |
| reasoning_model | 0/10 (0.0%) | 0/50 (0.0%) |
| **dr_stein** | 0/10 (0.0%) | 0/50 (0.0%) |
| baseline_repro | 0/10 (0.0%) | 0/50 (0.0%) |
| higher_lr | 0/10 (0.0%) | 0/50 (0.0%) |
| lower_lr_longer | 0/10 (0.0%) | 1/50 (2.0%) |
| more_epochs | 0/10 (0.0%) | 1/50 (2.0%) |
| more_pairs | 0/10 (0.0%) | 1/50 (2.0%) |

**The 3 GSM8K "hits" are coincidental.** All three matched the same
question (gold=20) by emitting a literal "20" rather than reasoning.
Greedy decoding makes this deterministic, but it's still string
collision, not solved math. The honest baseline is 0/everything.

This is the **first cross-benchmark baseline ever recorded for these
checkpoints** — prior runs had no HumanEval/GSM8K scores at all. The
harnesses are now wired and reusable for any future Stage 2.5 / 3 /
distilled checkpoint.

Implications for Stage 2.5:
- Expect HumanEval/GSM8K to stay at 0 even after GAD-tool fine-tuning;
  the seed dataset (`data/gad_tool_pairs.jsonl`) is targeted at
  GAD-CLI translation, not code or arithmetic.
- The right success metric for Stage 2.5 is moving the GAD-tool eval
  off 0/30 — code and math are downstream concerns that need
  separate distillation tracks (HumanEval-style + math chain-of-thought).

## What's queued for next session

1. **Re-eval `more_pairs`** with `--temperature 0.0 --max-new-tokens 30`
   to break out of whatever long-generation loop the checkpoint sat in.
2. **Curated GAD-tool training data** — the eval is testing OOD
   vocabulary. Stage 2 reasoning teaches `<think>` blocks from monorepo
   files; it never sees `gad note add ...`. Hand-write or distill a
   `data/gad_tool_pairs.jsonl` with 100-200 (prompt, gad-cli) pairs and
   add a Stage 2.5 fine-tune step. This is the single highest-leverage
   change for moving past 1/30.
3. **OpenCode teacher** — once you have OpenCode installed via the gad
   CLI installer, scripts/16-style runs can be replaced by distillation
   pairs from OpenCode's own tool calls.
4. **Run the eval at temperature 0.0** for all checkpoints to remove
   sampling variance from the comparison. Today's 1/30s could be lucky
   draws.
5. **Experiment with smaller architectures** (n_layer=12, n_embd=384,
   ~30M params) — would train Stage 1+2+3 in ~10 min total, opening up
   weight-size hypotheses you mentioned.
6. **Run HumanEval / GSM8K** evals for code + math reasoning tracks (the
   data is already pulled).

## Commit trail

- `2b91e00` Phase 03 baselines stamped + checkpoint eval helper
- `223b825` Sweep helpers: auto-eval and morning report
- `45d3f9a` Anchor runs/ ignore to root, track experiment manifests
- `a01f24c` Fix experiment runner UTF-8 handling + salvage helper

(plus earlier in the session: `64e66ed`, `03fec1a`, `b87bc88` for Phase 02
finalization, runtime path bug, pressure statusline.)
