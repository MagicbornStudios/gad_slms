---
name: modal-cli-windows-prefix
description: >-
  Always prepend MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 to every Modal CLI
  invocation on Windows Bash, or use PowerShell with $env:PYTHONIOENCODING.
  Prevents two distinct failure modes: silent task-drop from cp1252 encoding
  on Modal's success-checkmark output (8-second exits with 0 tasks queued),
  and crashed adapter/volume args from MSYS path translation rewriting
  /models/... into C:/Program Files/Git/models/...
status: proto
workflow: ./workflow.md
---

Modal CLI on Windows fails silently or noisily for two distinct reasons —
both fixable by prepending the right env vars to every invocation. This
skill captures the decision tree (Windows vs not, PowerShell vs Bash) and
the pre-flight check, plus the symptom-to-cause mapping so an operator
hitting either failure mode can diagnose in seconds. Bit slm-learning
twice in session 2026-05-08; promoting this to a framework-level skill
because every Modal-using project on Windows benefits from the same
guardrail.

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/modal-cli-windows-prefix/CANDIDATE.md`
- Drafted: 2026-05-09 by `create-proto-skill`
- Lock marker: see `./PROVENANCE.md`
- Errors of record:
  `msys-pathconv-translates-modal-volume-paths-2026-05-08`,
  `refactor-introduced-modal-import-bug-2026-05-08`
- Decisions: `slm-learning-105` (hardware policy)
