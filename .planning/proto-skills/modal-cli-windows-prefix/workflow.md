# workflow — modal-cli-windows-prefix

## When this fires

You are about to invoke the Modal CLI (`modal run`, `modal volume put`,
`modal app list`, `modal logs`, etc.) on Windows. Detect by:

- `os.name == 'nt'` AND
- shell is one of: Git Bash / MSYS / Cygwin (NOT PowerShell, NOT cmd.exe with
  proper PYTHONIOENCODING set, NOT WSL)

If you are NOT on Windows, this skill is a no-op. If you are on Windows in
PowerShell, only the `PYTHONIOENCODING` half applies.

## The two failure modes you are guarding against

### Mode 1: cp1252 encoding bug (silent task drop)

Modal's CLI prints `✓` characters on every successful operation. The Windows
console defaults to cp1252 ("charmap"), which cannot encode `✓`. The CLI
raises `UnicodeEncodeError` AFTER the operation succeeded but BEFORE the
ephemeral app submits its function call to a task. Result:

- Exit code 0 (the operation that printed succeeded)
- Command "completes" in 8 seconds
- `modal app list` shows the app as `ephemeral` with `0 tasks`
- No actual training/eval/inference ran
- Operator wonders why their Modal jobs are silently no-op-ing

**Symptom:** instant exit + 0 tasks queued = encoding bug.

### Mode 2: MSYS path translation (crash on volume / adapter args)

Git Bash on Windows uses MSYS, which intercepts arguments to native binaries
and rewrites any leading-slash path. `/models/runs/<id>/adapter` becomes
`C:/Program Files/Git/models/runs/<id>/adapter` before Modal sees it. This
corrupts:

- `--adapter-id /models/...` → HuggingFace's `PeftModel.from_pretrained`
  validates this as a repo_id → `HFValidationError: Repo id must be in
  the form 'repo_name' or 'namespace/repo_name': 'C:/Program Files/Git/models/...'`
- `--volume-path /processed/...` → similar corruption when uploading
  datasets to volumes
- Any `/<root>/<path>` argument passed to a Modal command

**Symptom:** Modal volume / adapter / dataset path arguments contain
`C:/Program Files/Git` after the rewrite.

## The fix (always both, every invocation)

Prepend BOTH environment variables in a single command line:

```bash
MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m modal run modal_app/<file>::main --spec-path ... --gpu A10G
```

`MSYS_NO_PATHCONV=1` disables MSYS path translation for this process.
`PYTHONIOENCODING=utf-8` makes the Python subprocess use utf-8 for stdout,
which lets Modal's `✓` checkmarks print without crashing.

## PowerShell preferred

PowerShell does not have an MSYS layer, so it doesn't need
`MSYS_NO_PATHCONV`. It still benefits from setting `PYTHONIOENCODING`
because the upstream Python issue is independent of shell:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\modal.exe run modal_app/<file>::main --spec-path ... --gpu A10G
```

Recommend PowerShell as the default for Modal on Windows. The existing
template at `scripts/morphism/fire_phases_1_to_4.ps1` shows the pattern.

## Pre-flight check (cheap)

Before firing a paid Modal job, run a one-liner that exercises both
prefixes against a no-op Modal command:

```bash
MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m modal app list 2>&1 | head -5
```

If you see the apps table render with `✓` characters intact and no
`UnicodeEncodeError`, the encoding side is fine. If you see any
`C:/Program Files/Git` rewrites in volume mount paths, the path side is
fine for this shell.

## Decision tree

```
On Windows?
  No  → skill is no-op (Linux/Mac don't have either bug)
  Yes:
    Shell is PowerShell?
      Yes → set $env:PYTHONIOENCODING = 'utf-8'; no MSYS prefix needed
      No (Git Bash / MSYS):
        Always prepend MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 to every
        modal invocation in the same command line.
        Inline env-var-only setting (e.g. via `export`) is NOT enough —
        the subprocess inherits but the parent shell's MSYS_NO_PATHCONV
        is checked at exec time. Inline command-line is safer.
```

## Failure modes to recognize

- "Command exits in 8 seconds with code 0 but `modal app list` shows
  0 tasks for the app I just fired" → encoding bug, missing
  `PYTHONIOENCODING=utf-8`.
- "Train succeeded; eval crashes with `HFValidationError: ... C:/Program
  Files/Git/...`" → path translation bug, missing `MSYS_NO_PATHCONV=1`
  on the eval invocation.
- "Volume put succeeds but `modal volume get` from a sibling shell
  shows different paths" → mixed-shell path mismatch; standardize on
  one shell with both prefixes.

## What to avoid

- Setting `MSYS_NO_PATHCONV` via `export` in a parent shell — Bash's
  child-process env inheritance works, but agent-driven subprocess
  launches don't always pick it up. Inline command-line prepend is
  the only reliable form.
- Using Windows-style paths (`C:\models\runs\...`) as Modal volume
  arguments — Modal expects POSIX paths. The fix is the env vars,
  NOT switching to Windows paths.
- Adding `2>&1` redirects without keeping `PYTHONIOENCODING` — the
  redirection pipeline can re-introduce the encoding crash if the
  intermediate filter doesn't preserve utf-8.

## Acceptance test for this skill

After installing/promoting:

1. New project on Windows that uses Modal can run a `gad modal preflight`
   helper and get a clean health check on first try.
2. Existing failing-fire patterns from this session, re-run with the
   wrapped helpers, produce correct behavior on first try.
3. `gad init` for new projects mentions this gotcha in the Windows
   setup checklist by default.
4. Any agent-authored Modal CLI invocation that doesn't include both
   prefixes triggers a lint warning OR is rewritten by a wrapper.

## Refs

- `.planning/notes/2026-05-08-modal-pyiconencoding-utf8-prefix.md`
- `.planning/ERRORS-AND-ATTEMPTS.xml`:
  - `msys-pathconv-translates-modal-volume-paths-2026-05-08`
  - `refactor-introduced-modal-import-bug-2026-05-08`
- Decision `slm-learning-105` (hardware policy mentioning Windows MSYS gotcha)
- Positive example: `scripts/morphism/fire_phases_1_to_4.ps1` (PowerShell pattern)
