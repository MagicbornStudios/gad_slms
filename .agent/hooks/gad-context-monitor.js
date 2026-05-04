#!/usr/bin/env node
// gad-hook-version: 1.35.0
// Context Monitor - PostToolUse/AfterTool hook (Gemini uses AfterTool)
// Reads context metrics from the statusline bridge file and injects
// warnings when context usage is high. This makes the AGENT aware of
// context limits (the statusline only shows the user).
//
// How it works:
// 1. The statusline hook writes metrics to /tmp/claude-ctx-{session_id}.json
// 2. This hook reads those metrics after each tool use
// 3. When remaining context drops below thresholds, it injects a warning
//    as additionalContext, which the agent sees in its conversation
//
// Thresholds:
//   WARNING   (remaining <= 35%): Agent should wrap up current task
//   CRITICAL  (remaining <= 25%): Agent should stop immediately and save state
//   AUTOPAUSE (remaining <= 20%, team mode only): emit directive for worker
//             loop to call `gad pause-work` and return to mailbox
//
// Team mode detection: either .planning/team/config.json exists in cwd, or
// GAD_TEAM_WORKER_ID env var is set. Autopause only fires in team mode so
// interactive single-agent sessions are unaffected.
//
// Debounce: 5 tool uses between warnings to avoid spam
// Severity escalation bypasses debounce (WARNING -> CRITICAL fires immediately)

const fs = require('fs');
const os = require('os');
const path = require('path');

const WARNING_THRESHOLD = 35;    // remaining_percentage <= 35%
const CRITICAL_THRESHOLD = 25;   // remaining_percentage <= 25%
const AUTOPAUSE_THRESHOLD = Number(process.env.GAD_AUTOPAUSE_THRESHOLD || 20);
const STALE_SECONDS = 60;        // ignore metrics older than 60s
const DEBOUNCE_CALLS = 5;        // min tool uses between warnings

let input = '';
// Timeout guard: if stdin doesn't close within 10s (e.g. pipe issues on
// Windows/Git Bash, or slow Claude Code piping during large outputs),
// exit silently instead of hanging until Claude Code kills the process
// and reports "hook error". See #775, #1162.
const stdinTimeout = setTimeout(() => process.exit(0), 10000);
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  clearTimeout(stdinTimeout);
  try {
    const data = JSON.parse(input);
    const sessionId = data.session_id;

    if (!sessionId) {
      process.exit(0);
    }

    // Check if context warnings are disabled via config
    const cwd = data.cwd || process.cwd();
    const configPath = path.join(cwd, '.planning', 'config.json');
    if (fs.existsSync(configPath)) {
      try {
        const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
        if (config.hooks?.context_warnings === false) {
          process.exit(0);
        }
      } catch (e) {
        // Ignore config parse errors
      }
    }

    const tmpDir = os.tmpdir();
    const metricsPath = path.join(tmpDir, `claude-ctx-${sessionId}.json`);

    // If no metrics file, this is a subagent or fresh session -- exit silently
    if (!fs.existsSync(metricsPath)) {
      process.exit(0);
    }

    const metrics = JSON.parse(fs.readFileSync(metricsPath, 'utf8'));
    const now = Math.floor(Date.now() / 1000);

    // Ignore stale metrics
    if (metrics.timestamp && (now - metrics.timestamp) > STALE_SECONDS) {
      process.exit(0);
    }

    const remaining = metrics.remaining_percentage;
    const usedPct = metrics.used_pct;

    // No warning needed
    if (remaining > WARNING_THRESHOLD) {
      process.exit(0);
    }

    // Debounce: check if we warned recently
    const warnPath = path.join(tmpDir, `claude-ctx-${sessionId}-warned.json`);
    let warnData = { callsSinceWarn: 0, lastLevel: null };
    let firstWarn = true;

    if (fs.existsSync(warnPath)) {
      try {
        warnData = JSON.parse(fs.readFileSync(warnPath, 'utf8'));
        firstWarn = false;
      } catch (e) {
        // Corrupted file, reset
      }
    }

    warnData.callsSinceWarn = (warnData.callsSinceWarn || 0) + 1;

    const isCritical = remaining <= CRITICAL_THRESHOLD;
    const currentLevel = isCritical ? 'critical' : 'warning';

    // Emit immediately on first warning, then debounce subsequent ones
    // Severity escalation (WARNING -> CRITICAL) bypasses debounce
    const severityEscalated = currentLevel === 'critical' && warnData.lastLevel === 'warning';
    if (!firstWarn && warnData.callsSinceWarn < DEBOUNCE_CALLS && !severityEscalated) {
      // Update counter and exit without warning
      fs.writeFileSync(warnPath, JSON.stringify(warnData));
      process.exit(0);
    }

    // Reset debounce counter
    warnData.callsSinceWarn = 0;
    warnData.lastLevel = currentLevel;
    fs.writeFileSync(warnPath, JSON.stringify(warnData));

    // Detect if GAD is active (has .planning/STATE.md in working directory)
    const isGadActive = fs.existsSync(path.join(cwd, '.planning', 'STATE.md'));

    // Detect team-mode worker: either explicit env var (set by `gad team work`
    // supervisor) or config file exists. Autopause only fires for team workers
    // so interactive sessions see the advisory warning, not an exit directive.
    const isTeamWorker = Boolean(process.env.GAD_TEAM_WORKER_ID)
      || fs.existsSync(path.join(cwd, '.planning', 'team', 'config.json'));
    const shouldAutopause = isTeamWorker && remaining <= AUTOPAUSE_THRESHOLD;

    // Build advisory warning message (never use imperative commands that
    // override user preferences — see #884). Autopause branch is imperative
    // on purpose: the worker loop needs a deterministic signal to return
    // control to the mailbox.
    let message;
    if (shouldAutopause) {
      const workerId = process.env.GAD_TEAM_WORKER_ID || 'unknown';
      message = `CONTEXT AUTOPAUSE (team worker ${workerId}, ${usedPct}% used, ${remaining}% remaining): ` +
        'Immediately call `gad pause-work --goal "<one-line summary of where you are>" --priority high` ' +
        'to capture state as a resume handoff, then end this response. The team worker loop will claim ' +
        'the next mailbox item in a fresh context.';
    } else if (isCritical) {
      message = isGadActive
        ? `CONTEXT CRITICAL: Usage at ${usedPct}%. Remaining: ${remaining}%. ` +
          'Context is nearly exhausted. Do NOT start new complex work or write handoff files — ' +
          'GAD state is already tracked in STATE.md. Inform the user so they can pause at the next natural stopping point.'
        : `CONTEXT CRITICAL: Usage at ${usedPct}%. Remaining: ${remaining}%. ` +
          'Context is nearly exhausted. Inform the user that context is low and ask how they ' +
          'want to proceed. Do NOT autonomously save state or write handoff files unless the user asks.';
    } else {
      message = isGadActive
        ? `CONTEXT WARNING: Usage at ${usedPct}%. Remaining: ${remaining}%. ` +
          'Context is getting limited. Avoid starting new complex work. If not between ' +
          'defined plan steps, inform the user so they can prepare to pause.'
        : `CONTEXT WARNING: Usage at ${usedPct}%. Remaining: ${remaining}%. ` +
          'Be aware that context is getting limited. Avoid unnecessary exploration or ' +
          'starting new complex work.';
    }

    const output = {
      hookSpecificOutput: {
        hookEventName: process.env.GEMINI_API_KEY ? "AfterTool" : "PostToolUse",
        additionalContext: message
      }
    };

    process.stdout.write(JSON.stringify(output));
  } catch (e) {
    // Silent fail -- never block tool execution
    process.exit(0);
  }
});
