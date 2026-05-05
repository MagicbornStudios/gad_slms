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

## Files

- `AGENTS.md` is the source contract.
- `CLAUDE.md` is the runtime mirror.
- `.planning/AGENTS.md` narrows the rules for planning-only edits.
