---
name: wire-byok-encrypted-env
description: >-
  Wire per-project BYOK encrypted env: at-rest store with OS-keychain
  master keys, CLI surface that never echoes plaintext, scoped spawn
  wrapper that decrypts only into the child process, scope chain
  (species > eval > planning), audit log, project-editor BYOK tab,
  cloud surface. Use when a project needs encrypted API keys, when
  subagents need scoped env without parent leak, or when a multi-project
  monorepo needs key isolation.
status: stable
workflow: workflows/wire-byok-encrypted-env.md
---

# wire-byok-encrypted-env

BYOK has three independent surfaces: the at-rest store, the CLI, and the
scoped spawn wrapper. Each is critical and each has a distinct attack
surface (disk encryption, shell history, subprocess env leak). Phase 60
shipped them with strict separation — keychain-backed master, prompt-only
set, child-only decrypt — plus a scope chain so species/eval/planning
have independent master keys.

This skill captures the design doc → store → CLI → spawn → UI sequence
plus the gotchas that bit phase 60 (passphrase prompt hangs in Next.js
dev, error code split, scope-aware envelope paths).

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/phase-60-per-project-byok-encrypted-env-gad-secre/CANDIDATE.md`
- Drafted: 2026-04-28 by `create-proto-skill`
- See [PROVENANCE.md](./PROVENANCE.md)
