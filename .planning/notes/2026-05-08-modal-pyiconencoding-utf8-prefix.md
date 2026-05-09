# Modal CLI on Windows Bash: prepend BOTH `MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8` always

There are TWO Windows-Bash gotchas with Modal CLI, and both must be addressed every invocation.

**Gotcha 1 — PYTHONIOENCODING=utf-8.** Modal's CLI prints a Unicode checkmark on success which crashes the cp1252 charmap encoder Windows uses by default. Without `PYTHONIOENCODING=utf-8` set in the subprocess env, the CLI exits 0 BEFORE the Modal job is actually submitted (the app gets registered but 0 tasks queue). PowerShell's `$env:PYTHONIOENCODING` handles it; Bash subprocesses need the prefix in the same command line.

**Gotcha 2 — MSYS_NO_PATHCONV=1.** Git Bash's MSYS layer rewrites any leading-slash argument like `/models/runs/<id>/adapter` into `C:/Program Files/Git/models/runs/<id>/adapter` before the binary sees it. For Modal volume paths and `--adapter-id /models/...` args, this corrupts the value and downstream HF / Modal fails with `HFValidationError: Repo id must be in the form 'repo_name' or 'namespace/repo_name': 'C:/Program Files/Git/models/...'`. PowerShell does NOT have this problem.

Both bit us 2026-05-08:
- Round 1: PYTHONIOENCODING-less fires of 5 Modal training jobs registered ephemeral apps but submitted 0 tasks. Fix: add `PYTHONIOENCODING=utf-8` prefix.
- Round 2: 6 eval jobs trained but eval failed with HFValidationError when `--adapter-id /models/...` got mangled by MSYS. Fix: add `MSYS_NO_PATHCONV=1` prefix.

**The rule:** every Modal CLI invocation from Bash on Windows uses BOTH:
```bash
MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m modal run ...
```

Or skip the issue entirely by using PowerShell with `$env:PYTHONIOENCODING = 'utf-8'` (PowerShell needs no MSYS_NO_PATHCONV — no MSYS layer).

Candidate for promotion to a skill (modal-cli-windows-prefix). Refs: slm-learning-105, error msys-pathconv-translates-modal-volume-paths-2026-05-08, error refactor-introduced-modal-import-bug-2026-05-08.
