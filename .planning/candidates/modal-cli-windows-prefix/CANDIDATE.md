# Candidate: modal-cli-windows-prefix

**Priority:** HIGH (framework-level — every Modal-using project benefits)
**Source pressure:** session 2026-05-08, slm-learning
**Bit us:** 2× this session
**Refs:** slm-learning-105, error `msys-pathconv-translates-modal-volume-paths-2026-05-08`, error `refactor-introduced-modal-import-bug-2026-05-08`, note `2026-05-08-modal-pyiconencoding-utf8-prefix.md`

## Trigger

Any Modal CLI invocation from Bash on Windows (Git Bash / MSYS shell).

## Pattern

ALWAYS prepend BOTH environment variables in the same command line:

```bash
MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m modal run modal_app/<file>::main --spec-path ... --gpu A10G
```

Or use PowerShell with `$env:PYTHONIOENCODING = 'utf-8'` (PowerShell does not need MSYS_NO_PATHCONV — no MSYS layer).

## Why both prefixes are required

### `PYTHONIOENCODING=utf-8`

Modal's CLI prints a Unicode checkmark `✓` on every successful operation
(volume put, function created, app deployed). The Windows console
defaults to cp1252 (charmap) which cannot encode `✓`. Without the
prefix:

- Modal CLI raises `UnicodeEncodeError: 'charmap' codec can't encode character '✓' in position 0`
- The CLI exits with code 0 (because the operation succeeded BEFORE the print failed)
- BUT the python process dies before the ephemeral app submits its task to the function
- Result: ephemeral app gets registered (visible in `modal app list` with state=ephemeral), but it has 0 tasks queued, and your training/eval never runs
- Symptom: command "completes" in 8 seconds, no actual compute happens, you wonder why

### `MSYS_NO_PATHCONV=1`

Git Bash on Windows uses MSYS, which intercepts arguments to native
binaries and rewrites any leading-slash path. Specifically: `/models/runs/<id>/adapter` becomes `C:/Program Files/Git/models/runs/<id>/adapter` before the binary even sees it.

For Modal, this corrupts:
- `--adapter-id /models/...` → HuggingFace's PeftModel.from_pretrained validates this as a repo_id and raises `HFValidationError: Repo id must be in the form 'repo_name' or 'namespace/repo_name': 'C:/Program Files/Git/models/runs/...'`
- `--volume-path /processed/...` → similar corruption when uploading datasets to volumes

Symptom: training succeeds, eval fails fast with HFValidationError, you retry confused.

## Skill body

The skill should:

1. Detect the shell (`bash` on Windows MSYS vs PowerShell vs Linux/Mac).
2. Provide a wrapper / alias / helper function that prepends both prefixes when needed.
3. Provide a pre-flight check: `gad modal preflight` that runs `modal app list 2>&1` with the right prefixes and reports which env vars are set.
4. Document the symptom-to-cause mapping: "8-second exit + 0 tasks queued = encoding bug; HFValidationError with `C:/Program Files/Git` in path = MSYS path translation."
5. Recommend PowerShell as the default for Modal on Windows since it sidesteps both issues (only `$env:PYTHONIOENCODING` needed).

## Example failures

### Failure 1: encoding (round 1, 2026-05-08)

```bash
.venv/Scripts/python.exe -m modal run modal_app/train_lora.py::main --spec-path config.json --gpu A10G
# exits 0 in 8 seconds, "completes"
# modal app list shows: state=ephemeral, tasks=0
# nothing actually trained
```

Fix:
```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m modal run modal_app/train_lora.py::main --spec-path config.json --gpu A10G
# now actually trains, ~3 minutes for small dataset
```

### Failure 2: MSYS path translation (round 2, same session)

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m modal run modal_app/eval_adapter.py::main --adapter-id /models/runs/lora-3b-hard-retain-15-85-2026-05-08/adapter --base-model Qwen/Qwen2.5-Coder-3B-Instruct ...
# trains succeed, eval fails with:
# HFValidationError: Repo id must be in the form 'repo_name' or 'namespace/repo_name': 'C:/Program Files/Git/models/runs/lora-3b-hard-retain-15-85-2026-05-08/adapter'
```

Fix:
```bash
MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m modal run ... --adapter-id /models/runs/...
# now eval runs correctly
```

## Decision tree for the skill

```
Are we on Windows? -> PowerShell (preferred): set $env:PYTHONIOENCODING = 'utf-8'; no MSYS_NO_PATHCONV needed
                  -> Git Bash / MSYS: prepend BOTH MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 every invocation
                  -> WSL: same as Linux (no prefixes needed for Linux paths)
Are we on Linux/Mac? -> No prefixes needed
```

## Files / locations the skill should reference

- `.planning/notes/2026-05-08-modal-pyiconencoding-utf8-prefix.md`
- `.planning/ERRORS-AND-ATTEMPTS.xml` errors:
  - `msys-pathconv-translates-modal-volume-paths-2026-05-08`
  - `refactor-introduced-modal-import-bug-2026-05-08`
- `scripts/morphism/fire_phases_1_to_4.ps1` (existing PowerShell template; use as positive example)

## Acceptance test

After promoting:
1. New project that uses Modal on Windows can run `gad modal preflight` and get a clean check.
2. Re-running the failing-fire patterns from this session with the wrapped helpers produces correct behavior on first try.
3. Documentation in `gad init` for new projects mentions this gotcha by default.
