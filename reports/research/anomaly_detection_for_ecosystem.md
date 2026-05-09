# Anomaly Detection for the GAD Ecosystem

**Date:** 2026-05-09
**Author:** Claude Code (claude-sonnet-4-6)
**Status:** Shipped — `lib/anomalies/detector.cjs` live

---

## 1. Bottom Line

Anomaly detection is now wired into the GAD ecosystem as `lib/anomalies/detector.cjs` and surfaced through two entry points: `gad anomalies list/describe/baseline` and `gad ecosystem doctor`. The 8-rule engine fires on token-spend spikes, rotation storms, rate-limit storms, stuck handoffs, over-claimed queues, zombie workers, runaway log files, and unexpected process multiplications. This closes the monitoring gap that enabled the 37M-token incident.

---

## 2. Why Now

On 2026-05-09 the operator discovered that 37M codex tokens had been consumed over 6 days — **without a single alert firing**. The data was available: `.planning/.gad-log/token-budgets.jsonl` recorded cumulative token totals across every snapshot. The signal was there; the detection layer was not. The w1 worker log hit 88 MB. Rotation events exceeded 100/hour. None of these facts were aggregated and compared against a baseline. This document records the design decisions made to close that gap.

---

## 3. The 8 Rules

| rule_id | Description | Severity | Data Source | Threshold |
|---|---|---|---|---|
| `token_spend_daily_spike` | Daily token burn > 3× 3-sigma baseline | critical | token-budgets.jsonl | median + 3*stddev, then ×3 |
| `rotation_storm` | >100 account-rotated events / 1h per runtime | critical | worker log.jsonl | 100 events in 60 min |
| `rate_limit_storm` | >50 rate-limit events / 1h per runtime | warn | worker log.jsonl | 50 events in 60 min |
| `stuck_claimed_handoff` | Claimed handoff older than 6h with no work-complete | warn | handoffs/claimed/ + worker logs | 6h age |
| `claims_exceed_capacity` | Claimed count > live worker count | warn | handoffs/claimed/ + status.json | claimed > workers |
| `zombie_workers` | status=RUNNING but PID dead in OS | warn | status.json + process.kill(0) | any zombie |
| `log_file_growth_spike` | Any log file >50 MB | warn | .gad-log/ + worker log.jsonl | 50 MB |
| `unexpected_process_count` | Alive worker PIDs > 2× registered worker count | warn | status.json | multiplier ×2 |

---

## 4. Baseline Mechanics

The `computeBaseline({ baseDir, days })` function reads `token-budgets.jsonl` and derives daily incremental spend by diffing consecutive cumulative totals (one entry per calendar day, taking the daily maximum). From the resulting array of daily-spend samples:

- **median** = middle value of sorted array
- **stddev** = population standard deviation
- **p95_threshold** = median + 3 × stddev (the 3-sigma upper bound for "normal")
- **spike threshold** = p95_threshold × 3 (3× above the 3-sigma ceiling)

Default lookback is 14 days. For process/rotation rules, the window is 1 hour (behavioral signals change faster than spend patterns).

On a fresh install with no historical data, `sample_count = 0` and the spike rule does not fire (safe default).

---

## 5. Surface

Two entry points:

**`gad anomalies` command:**
- `gad anomalies list [--projectid] [--lookback-h N] [--severity warn|critical] [--json]` — run all rules, print SITREP table
- `gad anomalies describe <rule_id>` — explain a specific rule
- `gad anomalies baseline [--days 14] [--json]` — show baseline statistics (what the system considers normal)

**`gad ecosystem doctor` integration:**
- After the existing process/env checks, `runDoctor` calls `detectAnomalies({ lookback_h: 24 })` and prints an `=== ANOMALIES ===` section. If none fired: `ANOMALIES: none`. JSON mode includes the full `anomalies` array.

---

## 6. Operator Response Model

| Severity | Action |
|---|---|
| `info` | Logged only. Visible in `gad anomalies list` but no surface-level alert. |
| `warn` | Surfaced in `gad anomalies list` SITREP + in `gad ecosystem doctor` output. No automatic action. |
| `critical` | Surfaced prominently. Candidate for auto-action: `rotation_storm` critical = park the affected runtime (`gad team park <runtime>`). `token_spend_daily_spike` critical = surface inline in Kael chat + log to ERRORS-AND-ATTEMPTS. |

Current implementation surfaces only; auto-action is an open extension point (no behavior changes without explicit operator direction).

---

## 7. Open Questions

1. **Which rules should auto-action vs surface-only?** `rotation_storm` at 100 events/h is the strongest candidate for auto-park. Need operator sign-off on automated runtime parking.

2. **Baseline lookback tuning.** 14d for spend vs 1h for process events. Should process windows adapt to session frequency? A session-active scalar could normalize rotation counts by handoff throughput.

3. **Anomalies as preference-pair training data for gad ask.** Each fired anomaly + operator resolution could become a (anomaly-description, correct-action) pair for the gad ask model. Recommend a future phase to wire `gad anomalies list` output into the delta-train curator pipeline as a labeled incident dataset.

4. **Token cap in USD.** The `anomalies.daily_premium_token_cap_usd` setting (default $50) requires a token→USD conversion table keyed by runtime. Codex pricing differs from Anthropic. Until that lookup table ships, the USD cap is a reserved key — the detector uses raw token counts.

5. **Anomaly deduplication.** Back-to-back `gad ecosystem doctor` calls will re-fire the same anomalies. A fingerprint + cooldown window (e.g., 30min suppression) would prevent alert fatigue when the operator is actively working an incident.
