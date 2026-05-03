# Agent Guide

## gad

Use `gad` as the durable planning and project-memory CLI for this repo.

Project id: `slm_learning`

Read `SOUL.md` first, then read the active soul body at
`narrative/souls/dr-stein.md`. Gilgamesh remains the broader/default leader,
but this project-specific soul is Dr. Stein: a mad scientist responsible for
creating SLMs, souls, and reasoning loops from this project itself.

High-value commands:

- `gad` - print the full command surface.
- `gad projects list` - confirm registered projects and project ids.
- `gad state show --projectid slm_learning` - view current milestone, status, and next action.
- `gad tasks list --projectid slm_learning` - inspect planned/in-progress work.
- `gad errors list --projectid slm_learning` - review prior mistakes before implementing related work.
- `gad errors add --projectid slm_learning --id <slug> --title <title> --context <text> --failure <text> --rule <text>` - log implementation errors with a future rule.
- `gad issues list --projectid slm_learning` - review durable planning issues.
- `gad issues add --projectid slm_learning` - capture a planning issue when a requirement or defect should persist.
- `gad decisions list --projectid slm_learning` - review durable decisions.
- `gad requirements list --projectid slm_learning` - inspect captured requirements.
- `gad snapshot --projectid slm_learning` - get the canonical orientation snapshot when available.
- `gad startup --projectid slm_learning --no-side-effects` - read-only session orientation fallback.
- `gad tui` - launch the interactive GAD terminal orchestrator.

The current planning scaffold is in `.planning/`:

- `.planning/STATE.xml`
- `.planning/TASK-REGISTRY.xml`
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
- `scripts/learning_tui/vcs_footer.py` - VCS footer UI.
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
- The footer provides a `VCS Quick Prompt` capture action.
- Copied prompts must include target id, route, source file, source hint, and transcript/request text.
- Menu shell should behave like a chat/composer surface; lesson routes can be slash commands.

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

## Current Caution

The browser-based speech bridge was removed. Keep speech-to-text terminal-native unless the user explicitly approves an external browser/web surface. The current terminal-native path uses Vosk + sounddevice with the model under `models/vosk-model-small-en-us-0.15`; `SLM_TUI_AUDIO_DEVICE` can override the default input device.
