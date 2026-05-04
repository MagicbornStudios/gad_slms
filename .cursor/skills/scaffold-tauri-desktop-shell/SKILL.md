---
name: scaffold-tauri-desktop-shell
description: >-
  Build a Tauri 2.x desktop shell that wraps an existing Next.js
  planning-app + gad CLI. Bundled-sidecar approach (Tauri spawns the
  Next prod server as a child process), CLI sidecar binding with typed
  Rust commands, xterm.js + node-pty terminal-as-chat, sidenav, publish
  wizard, Clerk auth threaded via env, GitHub Actions MSI build with
  Tauri updater wiring, cross-host package extraction. Use when wrapping
  an existing web app + CLI in a desktop shell or when extracting
  shared surfaces for desktop reuse.
status: stable
workflow: workflows/scaffold-tauri-desktop-shell.md
---

# scaffold-tauri-desktop-shell

Wrapping an existing Next.js + gad CLI stack in a Tauri shell is more
than `tauri init`. The load-bearing pieces are the bundled-sidecar
strategy (vs duplicating UI), the CLI sidecar binding (vs HTTP from
Rust), terminal-as-chat (vs separate chat + terminal panes), and
extracting shared surfaces into cross-host packages so desktop and web
mount the same components.

This skill is the recipe phase 53 followed across 19 tasks. The
guardrails are the bites it took along the way (icon format, PTY
lifetimes, marketplace adapter coupling).

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/phase-53-apps-desktop-tauri-shell-editors-termina/CANDIDATE.md`
- Drafted: 2026-04-28 by `create-proto-skill`
- See [PROVENANCE.md](./PROVENANCE.md)
