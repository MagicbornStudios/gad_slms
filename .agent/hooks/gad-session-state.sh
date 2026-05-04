#!/usr/bin/env bash
# gad-hook-version: 1.33.0
# SessionStart hook — emit soul banner + daily teaching nudge + unclaimed
# handoff pointer. Keeps output <15 lines. No network, no LLM. Exits 0
# even on failure so the session always starts.
#
# Driven by tasks 63-05 (soul + tip) and 63-02 (handoff surface). The
# STATE.md-head reminder from the earlier opt-in hook is superseded by
# `gad snapshot` which every agent runs on session open per CLAUDE.md.

set -uo pipefail

cwd="${PWD:-$(pwd)}"

# Active soul — repo-root SOUL.md is the pointer per decision gad-256/257.
soul_file="$cwd/SOUL.md"
if [ -f "$soul_file" ]; then
  soul_line="$(head -n 1 "$soul_file" 2>/dev/null | sed 's/^# Active Soul — //; s/^# //')"
  if [ -n "$soul_line" ]; then
    printf 'Active soul: %s (SOUL.md)\n' "$soul_line"
  fi
fi

# Daily teaching nudge — title only, deterministic (teachings-reader zero-cost).
if command -v gad >/dev/null 2>&1; then
  tip_title="$(gad tip --headers 2>/dev/null | head -n 1)"
  if [ -n "$tip_title" ]; then
    printf 'Daily teaching: %s — run `gad tip` for the body.\n' "$tip_title"
  fi

  # Unclaimed handoff nudge (task 63-02). Silent if gad binary predates
  # the handoffs subcommand (exit code 1 from `gad handoffs list`).
  handoff_json="$(gad handoffs list --json 2>/dev/null)"
  if [ -n "$handoff_json" ]; then
    handoff_count="$(printf '%s' "$handoff_json" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{const a=JSON.parse(d);process.stdout.write(String(Array.isArray(a)?a.length:''))}catch{process.stdout.write('')}})" 2>/dev/null)"
    if [ -n "$handoff_count" ] && [ "$handoff_count" != "0" ]; then
      printf 'Unclaimed handoffs: %s — run `gad handoffs list` to pick one up.\n' "$handoff_count"
    fi
  fi
fi

exit 0
