# SLM Learning TUI

This adds a Textual terminal UI that lets you search lessons through a slash-command composer, run lesson commands, inspect output, stop a running command, clear output, and go back to the Dr. Stein lab shell. Lesson search results live in a fixed-height suggestions panel so the composer does not jump while you type. Lesson screens use a chat-first layout with a right-side artifact/output rail.

## One-command flow

From the project root:

```bash
npm run dev
```

or:

```bash
pnpm dev
```

The first run will:

1. create `.venv` if missing,
2. install the TUI dependencies,
3. install the model dependencies,
4. launch the lesson terminal UI in Textual dev mode.

## Useful commands

```bash
npm run dev        # setup if needed, then run with Textual dev mode
npm run start      # setup if needed, then run normally
npm run setup      # force dependency installation
npm run serve      # run through textual serve for browser access
npm run reset-setup # delete .venv so setup can rebuild it
```

## Keys

Menu:

- Type `/`, `/les`, or `/lesson <query>` to search lessons, then choose a ranked result.
- `Alt+i` toggles VCS dev mode.
- `Esc`, `q`, or the compact `×` button quits.

Lesson screen:

- `r` runs the lesson command.
- `s` stops the current command.
- `c` clears output.
- `b` goes back.
- `Alt+i` toggles VCS dev mode.
- `l` locks or unlocks the selected visual context target.
- `Esc`, `q`, or the compact `×` button quits.

## Visual Context System

The TUI includes dev-only visual context controls by default. Set `SLM_TUI_VCS=0` to hide VCS surfaces and avoid mounting the capture footer.

In VCS dev mode, stable ids become visible directly on the UI and the theme shifts amber/purple so you can tell targeting is active. The top banner shows route and local mic details. Click an id label on screen, then click `Quick Prompt` in the footer to start capture. The TUI uses local Vosk speech-to-text through the default terminal microphone input, with optional typed fallback. Stopping capture copies a compact prompt with target metadata and transcript.

To inspect audio devices:

```bash
./.venv/Scripts/python.exe -m sounddevice
```

Set `SLM_TUI_AUDIO_DEVICE` to a sounddevice device index/name to override the default input, for example `SLM_TUI_AUDIO_DEVICE=20 npm run dev`.

## Python version note

If PyTorch fails to install on Python 3.14, install Python 3.11 or 3.12 and rebuild:

```bash
npm run reset-setup
PYTHON=python3.12 npm run dev
```

On Windows with the Python launcher:

```powershell
npm run reset-setup
$env:PYTHON="py"
npm run dev
```
