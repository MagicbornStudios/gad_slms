#!/usr/bin/env node
// Refresh ~/.cache/gad/pressure-<projectid>.json so the GAD statusline
// shows real evolution pressure for this project.
//
// Why this exists:
//   - The gad-statusline.js hook reads ~/.cache/gad/pressure-<id>.json,
//     keyed by the kebab-case project id from gad-config.toml.
//   - Some gad CLI writers emit the same file but keyed with underscores
//     ("slm_learning"), so the kebab lookup misses and the statusline
//     reports a stale 0.02 score even when there's real pressure.
//   - Pure operational pressure (rate limits, handoff failures) doesn't
//     reflect evolution candidate pressure (proto-skill candidates,
//     unused skills flagged for shedding), so the score also needs to
//     fold in `gad evolution scan` output.
//
// Run after a planning churn or before a session to refresh the bar:
//   node scripts/refresh_pressure.js [projectid]

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

const projectId = process.argv[2] || 'slm-learning';
const cacheDir = path.join(os.homedir(), '.cache', 'gad');
fs.mkdirSync(cacheDir, { recursive: true });

const underscoreId = projectId.replace(/-/g, '_');
const oldPath = path.join(cacheDir, `pressure-${underscoreId}.json`);
const newPath = path.join(cacheDir, `pressure-${projectId}.json`);

let base = {
  breakdown: {
    rate_limits: 0,
    open_handoffs: 0,
    handoffs_with_unclaims: 0,
    worker_failures: 0,
    errors_recent: 0,
    errors_open: 0,
  },
};
if (fs.existsSync(oldPath)) {
  try {
    base = JSON.parse(fs.readFileSync(oldPath, 'utf8'));
  } catch (e) {}
}

let scan = { candidateCount: 0, shedCount: 0, scan: { candidates: [] } };
try {
  const out = execSync(
    `gad evolution scan --projectid ${projectId} --json`,
    { stdio: ['ignore', 'pipe', 'ignore'] },
  ).toString();
  scan = JSON.parse(out);
} catch (e) {}

const opScore = Number(base.score) || 0;
const evoScore = Math.min(
  1,
  (scan.candidateCount || 0) * 0.2 + (scan.shedCount || 0) / 200,
);
const score = Math.min(1, Math.max(opScore, evoScore));

const topCandidate = scan.scan && scan.scan.candidates && scan.scan.candidates[0];
const topPhase = topCandidate
  ? String(topCandidate.phase || 'placeholder')
  : (base.top_phase || 'placeholder');

const snapshot = {
  updated_at: new Date().toISOString(),
  projectid: projectId,
  score,
  top_phase: topPhase,
  top_phase_score: scan.candidateCount > 0 ? Math.min(1, scan.candidateCount * 0.25) : 0,
  breakdown: {
    ...base.breakdown,
    evo_candidates: scan.candidateCount || 0,
    evo_shed: scan.shedCount || 0,
  },
};

fs.writeFileSync(newPath, JSON.stringify(snapshot, null, 2));
console.log(`Wrote ${newPath}`);
console.log(`score=${score.toFixed(2)} top_phase=${topPhase} evo_candidates=${snapshot.breakdown.evo_candidates} evo_shed=${snapshot.breakdown.evo_shed}`);
