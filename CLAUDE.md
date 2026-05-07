# slm-learning Agent Contract

This file mirrors `AGENTS.md` for runtimes that read `CLAUDE.md`.
For long-form content (TUI structure, VCS, speech rules, full SLM
training strategy) read `AGENTS.md`. This file is the quick reference.

Project name: `slm-learning`
Project id: `slm-learning`  (kebab-case — the gad CLI rejects the
underscore form)

## Soul pointer

Read `SOUL.md` first, then read the active soul body at
`narrative/souls/dr-stein.md`. The earlier `speech-native-builder` soul
is preserved as historical context but is no longer active.

## Loop

Use this loop every session:

1. `gad snapshot --projectid slm-learning`
2. Pick one task
3. Implement the task
4. `gad tasks stamp <task-id> --projectid slm-learning --status done --agent <agent> --runtime <runtime>`
5. `gad state log "<delta>" --projectid slm-learning`
6. Commit

## Planning IDs

Use canonical IDs exactly:

| Entity | Format |
|---|---|
| decisions | `slm-learning-<nnn>` (e.g. `slm-learning-018`) |
| tasks | `SL-T-<phase>-<n>` (e.g. `SL-T-03-04`) |
| handoffs | `h-<ISO>-slm-learning-<phase>` |
| requirements | `SL-R-<n>` |
| errors | `SL-E-<n>` |

## Communication style

- SITREP format.
- Tables when structure helps.
- Report deltas only.
- Always close with gaps.
- Call entities by registered name, not shorthand.

## GAD CLI quick reference

| Command | Purpose |
|---|---|
| `gad snapshot --projectid slm-learning` | Hydrate planning context before work |
| `gad tasks list --projectid slm-learning` | Inspect available work |
| `gad tasks stamp <task-id> --projectid slm-learning --status done --agent <agent> --runtime <runtime>` | Stamp task completion |
| `gad state log "<delta>" --projectid slm-learning` | Append a state-log entry |
| `gad decisions add slm-learning-<n> --projectid slm-learning --summary "..."` | Record a decision |
| `gad note add <slug> --projectid slm-learning --title "..." --body "..."` | Capture a planning note |
| `gad handoffs list --projectid slm-learning` | Inspect open handoffs |
| `gad handoffs claim <handoff-id>` | Claim a handoff |
| `gad handoffs complete <handoff-id> --by <runtime>` | Close a handoff |

## SLM training strategy summary

Full rationale: AGENTS.md "SLM Training Strategy" section + decisions
`slm-learning-011` through `slm-learning-018`. Headlines:

- 6GB GTX 1660 Ti is the hard VRAM ceiling.
- TRL `SFTTrainer` + PEFT (LoRA/QLoRA) for new fine-tunes; bespoke
  loops in `scripts/16_*.py` / `scripts/17_*.py` are kept for the
  educational track only.
- HF datasets (FineWeb, The Stack, OpenMathInstruct, OpenCodeReasoning,
  FineMath) replace monorepo-only data for code/math/reasoning tracks.
- Train -> prune -> retrain -> prune iterative loop. Sparsity is a
  first-class hyperparameter.
- MoE with reasoning-specialized experts is the long-term architecture.
- High reasoning > crystallized knowledge. Slower output is OK if
  reliably correct.
- Synthetic data via stronger LLMs (Claude haiku for paraphrase, Opus
  for chain-of-thought traces).
- Free remote compute (Colab/Kaggle/HF Spaces) for jobs that exceed
  local; inference + planning stay local.

## Eval defaults

Read AGENTS.md "Eval Pipeline Conventions". Headlines:
- temp=0.0 greedy, GPU, EOS early-stop ON.
- Per-checkpoint eval JSONs land next to the checkpoint.
- HumanEval candidates run in subprocess with 10s timeout.

## Lane discipline

Single-agent by default. Use multi-agent execution only when `gad team`
is active and the work has been explicitly split into lanes.

## Compare-and-compete discipline (MANDATORY)

Per `slm-learning-103` + `.planning/concerns/research-program-charter.md`:

Every candidate model produces FOUR eval rows or it is REFUSED for promotion:

1. **Public-leaderboard row** — SWE-bench Verified subset + HumanEval +
   MBPP + LiveCodeBench (where applicable to the lane)
2. **Frontier comparator row** — same eval set against:
   `claude-cli` + `Big Pickle` (OpenCode Zen) + at least one
   OpenRouter free-tier model (Llama-3.3-70B-Instruct:free or
   nemotron-3-super-120b:free) + bare-base
3. **Owned-domain row** — relevant subset of GAD-tools / doc-verifier /
   tooluse / Magicborn / Grime Time / Kael
4. **Lineage row** — parents, training method, cost, wall hours,
   regression journal URI, outputs corpus URI

No exceptions. A candidate without the comparator row is not a
candidate, it's a vibe.

## Hardware policy

Per `slm-learning-105`. The local laptop disk is at 93% capacity:

- Anything >100MB goes to **Modal volume**, never local
- Base model weights: HF Hub + Modal volume, small local cache only
  for active dev (cap ~10GB)
- Telemetry exports rotate to Modal volume after 7 days
- Adapters live on HF Hub primary
- Local laptop = orchestration + small specialist eval only

## Delta Graph (model registry schema)

Per `slm-learning-100`. Every adapter is a node. Required fields:
`delta_id`, `base`, `parents[]`, `depends_on[]`, `dataset`, `rank`,
`merge_method`, `training_method`, `evals.public`, `evals.private`,
`cost_usd`, `wall_hours`, `compute_target`, `status`,
`regression_journal_uri`, `outputs_corpus_uri`, `decision_refs[]`.

Per `slm-learning-096`: every training run produces 3 reusable
artifacts (weights + outputs corpus on a held-out 200-prompt bank +
regression journal of failed tasks). Lost training is structurally
impossible.

## Six research tracks (`slm-learning-101`)

A — Branch-Train-Merge (composition of specialists)
B — SERA repo-specialized coder (strongest paper lane)
C — Verifier-driven RL (SFT → DPO → GRPO/RLVR)
D — Test-time compute (best-of-N + verifier)
E — Kael computer-use traces
F — Artifact generation (game / music / landing / marketing)

## Named experiments

`.planning/research/EXPERIMENTS.json` — EXP-001 through EXP-010 each
carry hypothesis + dataset + model + cost + eval + pass-threshold.
Don't fire a new experiment without an EXP-id. See
`.planning/concerns/research-program-charter.md` for the table.

## Research intake protocol

Per `slm-learning-106`:

- External code goes to `tmp/research/{papers,repos,experiments,reviews}`
- Every clone gets a research review record
- Useful ideas become deltas/tasks; unused becomes skeleton
- License + security review before adopting any dependency
- Every claim needs a benchmark or reproduction path

## Two-shot $50 discipline

Per `slm-learning-097`. Big training shots only fire after:
- Pre-flight comparator matrix has real numbers vs frontier
- Scaling-ladder smoke (1.5B → 3B → 7B) predicts the larger size
- Holdout gate threshold written before training, not after

## Files

- `AGENTS.md` is the source contract.
- `CLAUDE.md` is the runtime mirror.
- `.planning/AGENTS.md` narrows the rules for planning-only edits.
- `.planning/concerns/research-program-charter.md` is the operating
  constitution for the research program (locked 2026-05-07).
