# Agent Guide

## Operating constitution (read first)

This project is a research program, not a one-off training repo. The
operating constitution is `.planning/concerns/research-program-charter.md`
(locked 2026-05-07 by operator brief). Read it before any training,
serving, or eval work.

Headlines that bind every session:

- **Compare-and-compete is mandatory.** Every candidate model produces
  4 eval rows (public leaderboard + frontier comparator + owned-domain
  + lineage) or it is REFUSED for promotion. See `slm-learning-103`.
- **Delta Graph schema for adapters.** Every LoRA tracks
  parents/depends_on/evals/cost/lineage in `models/REGISTRY.json`. No
  blind stacking. No merge without an eval beating both parents. See
  `slm-learning-100`.
- **3-artifact rule per training run.** Weights + outputs-corpus +
  regression journal. Lost training is structurally impossible. See
  `slm-learning-096`.
- **Two-shot $50 discipline.** No big training fires without pre-flight
  comparator matrix landing real numbers vs frontier AND scaling-ladder
  smoke (1.5B → 3B → 7B) predicting the bigger outcome. See
  `slm-learning-097`.
- **Hardware policy.** Anything >100MB goes to Modal volume, NOT local.
  Local disk at 93% — assume the laptop is fragile. See
  `slm-learning-105`.
- **Six research tracks** are open: Branch-Train-Merge, SERA repo-coder,
  RLEF/RLVR, test-time compute, Kael computer-use, artifact generation.
  See `slm-learning-101`.
- **Named experiments only.** EXP-001 through EXP-010 each have
  hypothesis + dataset + model + cost + eval + pass-threshold in
  `.planning/research/EXPERIMENTS.json`.

## gad

Use `gad` as the durable planning and project-memory CLI for this repo.

Project id: `slm-learning`

Read `SOUL.md` first, then read the active soul body at
`narrative/souls/dr-stein.md`. Gilgamesh remains the broader/default leader,
but this project-specific soul is Dr. Stein: a mad scientist responsible for
creating SLMs, souls, and reasoning loops from this project itself.

High-value commands:

- `gad` - print the full command surface.
- `gad projects list` - confirm registered projects and project ids.
- `gad state show --projectid slm-learning` - view current milestone, status, and next action.
- `gad tasks list --projectid slm-learning` - inspect planned/in-progress work.
- `gad errors list --projectid slm-learning` - review prior mistakes before implementing related work.
- `gad errors add --projectid slm-learning --id <slug> --title <title> --context <text> --failure <text> --rule <text>` - log implementation errors with a future rule.
- `gad issues list --projectid slm-learning` - review durable planning issues.
- `gad issues add --projectid slm-learning` - capture a planning issue when a requirement or defect should persist.
- `gad decisions list --projectid slm-learning` - review durable decisions.
- `gad requirements list --projectid slm-learning` - inspect captured requirements.
- `gad snapshot --projectid slm-learning` - get the canonical orientation snapshot when available.
- `gad startup --projectid slm-learning --no-side-effects` - read-only session orientation fallback.
- `gad tui` - launch the interactive GAD terminal orchestrator.

The current planning scaffold is in `.planning/`:

- `.planning/STATE.xml`
- `.planning/tasks/`
- `.planning/REQUIREMENTS.xml`
- `.planning/DECISIONS.xml`
- `.planning/ERRORS-AND-ATTEMPTS.xml`

## Project Commands

Use npm scripts as the main entrypoints:

- `npm run setup` - create/update `.venv`, install TUI deps, then install model deps.
- `npm run dev` - run the Textual app in dev mode.
- `npm run start` or `npm run tui` - run the Textual app normally.
- `npm run serve` - run through `textual serve`.
- `npm run reset-setup` - remove `.venv` so setup can rebuild it.

Direct Python checks:

- `./.venv/Scripts/python.exe -m py_compile <files>` on Windows.
- Use Textual `run_test()` smoke tests for UI changes where practical.

## TUI Structure

Entrypoint:

- `scripts/06_learning_tui.py`

Focused modules:

- `scripts/learning_tui/app.py` - app shell and global bindings.
- `scripts/learning_tui/app_banner.py` - compact route/device/status banner.
- `scripts/learning_tui/menu_screen.py` - lesson menu screen.
- `scripts/learning_tui/lesson_screen.py` - chat/artifact lesson screen.
- `scripts/learning_tui/visual_context.py` - VCS state, selection, prompt copy behavior.
- `scripts/learning_tui/vcs_tag.py` - visible clickable VCS id tags.
- `scripts/learning_tui/lessons.py` - lesson catalog.
- `scripts/learning_tui/models.py` - shared dataclasses.
- `scripts/learning_tui/settings.py` - root paths and env flags.
- `scripts/learning_tui/icons.py` - UI icon constants.
- `scripts/learning_tui/local_speech.py` - terminal-native Vosk + sounddevice speech capture.

Soul files:

- `SOUL.md` - active project soul pointer and session contract.
- `narrative/souls/dr-stein.md` - active project soul.
- `narrative/souls/speech-native-builder.md` - previous speech-focused soul; keep as historical context.

Styles:

- `scripts/06_learning_tui.css`

## Visual Context System

Core invariant: a user can point at a visible UI region and produce a copy-ready prompt that maps to a stable source identifier.

Current behavior:

- `Alt+i` toggles VCS dev mode.
- Dev mode shows clickable ids directly on screen.
- The theme shifts while VCS is active.
- The top banner provides a `VCS Quick Prompt` capture action beside mic/device status.
- Copied prompts must include target id, route, source file, source hint, and transcript/request text.
- Menu shell should behave like a chat/composer surface; lesson routes are found through slash-command suggestions, not a separate sidebar.

Do not add runtime-generated ids to the user-facing targeting path. Ids must be stable and searchable in source.

## Speech-To-Text Rule

Logged error: `tui-browser-speech-bridge-mismatch-2026-05-02`.

Do not route terminal-native UX through a browser unless the user explicitly approves that tradeoff. The browser speech bridge was implemented after the user wanted speech-to-text in the terminal, and that was the wrong product move.

For future speech work:

- State the terminal limitation before implementation.
- Prefer terminal-native audio capture if speech-to-text is required.
- Ask before adding a separate browser, web UI, service, or device-permission surface.
- If using native audio, make device selection/status visible in the TUI.
- Show clear capture state: selected device, listening/not listening, live transcript, errors, and copied prompt output.
- Audio devices can be inspected with `./.venv/Scripts/python.exe -m sounddevice`.

## Engineering Rules

- Keep one component or concern per file.
- Prefer existing repo patterns over new abstractions.
- Keep UI changes scoped to the relevant Textual module and CSS.
- After substantive edits, run compile checks and lints for touched files.
- Do not hide implementation limitations behind simulated UI. If input/output is fake, label it as fake or do not ship it.
- Do not remove user changes unless explicitly asked.

## SLM Training Strategy (2026-05-05)

Read decisions `slm-learning-011` through `slm-learning-018` for full
rationale. Operating constraints and direction:

- **VRAM ceiling = 6GB GTX 1660 Ti.** Every model must load and train on
  the baseline GPU. Larger jobs go to free remote (Colab/Kaggle/HF).
  A second 1660 Ti via Razer Core eGPU is being brought up but is not
  yet detected — see `.planning/notes/2026-05-05-egpu-detection-followup.md`.
- **PEFT/LoRA/QLoRA via TRL `SFTTrainer`** for any new fine-tune. The
  bespoke `scripts/16_reasoning_training.py` / `17_dpo_training.py`
  loops stay for the educational from-scratch track only.
- **HF datasets** (FineWeb, The Stack, OpenMathInstruct,
  OpenCodeReasoning, FineMath) replace monorepo-only training data
  for code/math/reasoning tracks. Streaming load to avoid TB downloads.
- **Iterative train -> prune -> retrain -> prune** is the core loop.
  Sparsity is a first-class hyperparameter.
- **MoE with reasoning-specialized experts** is the long-term
  architecture (extends `slm-learning-004`). Only K experts active per
  token to respect the VRAM ceiling.
- **High reasoning > crystallized knowledge.** Slower output is OK if
  it's reliably correct. Reasoning-trace data and CoT-aware evals
  outweigh raw-text corpora and final-answer-only scoring.
- **Synthetic data via stronger LLMs** (Claude-haiku-4-5 for paraphrase,
  Opus/Sonnet for chain-of-thought traces). Quality-filter + dedup before
  mixing into training data.

## Eval Pipeline Conventions

- Inference + eval run on **GPU at temp=0.0 (greedy)** by default.
  See `scripts/eval_checkpoint.py`, `scripts/eval_humaneval.py`,
  `scripts/eval_gsm8k.py`, `scripts/eval_benchmark_matrix.py`.
- `KaelModel(device='auto')` resolves cuda-if-available; never load to
  CPU silently. `MiniLlama.generate` honors `eos_token_id` early-stop.
- Per-checkpoint eval JSONs land next to the checkpoint:
  `experiments/runs/<name>/eval_<benchmark>.json`.
- Sweep ledger in `experiments/INDEX.md`; narrative in
  `experiments/REPORT.md`.
- HumanEval candidate code runs in a fresh subprocess with a 10s
  timeout — that is the safety boundary for model-generated code on
  this machine.

## Current Caution

The browser-based speech bridge was removed. Keep speech-to-text terminal-native unless the user explicitly approves an external browser/web surface. The current terminal-native path uses Vosk + sounddevice with the model under `models/vosk-model-small-en-us-0.15`; `SLM_TUI_AUDIO_DEVICE` can override the default input device.
