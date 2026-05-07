---
id: h-2026-05-06T16-50-00-global-kael-mvp-ack
projectid: slm-learning
phase: K0
task_id: T-K0-ack-kael-mvp
created_at: 2026-05-06T16:50:00.000Z
created_by: team-w2
runtime_preference: claude-code
estimated_context: prescribed
risk: safe
time: standard
surface: local
claimed_by: unknown
claimed_at: 2026-05-07T00:26:40.649Z
completed_at: 2026-05-07T00:27:16.209Z
---

# Kael MVP — Ack + Implementation (gad-monorepo side)

Acking the proposed split from \h-2026-05-06T16-45-00-global-bridge-kael-mvp-handoff\. 

## What I've shipped (gad-monorepo side)

1. **Production CLI integration (\gad kael ...\):**
   - Created \endor/get-anything-done/bin/commands/kael.cjs\.
   - Subcommands \sk\, \
ote\, \snapshot\, \queue\, \oute\, \pprove\ are wired and shell out to \../slm_learning/scripts/kael/kael.py\.
   - \daemon\ is currently refused (placeholder).
   - Manifest updated; \gad kael\ is live in the CLI tree.

2. **Action schema integration:**
   - Extended \endor/get-anything-done/lib/telemetry/envelope.cjs\ to recognize \ole=kael_action\.
   - Kael actions are now valid envelopes in the data flywheel.

3. **Permission policy + Logging:**
   - In \kael.cjs\, added checks for \~/.gad/kael/permissions.json\.
   - Every Kael invocation is logged to \.planning/.gad-log/<date>-kael.jsonl\.
   - Refused non-interactive \--yes\ for \last_radius=high\ intents.
   - Wired \logRoutingDecision()\ to \lib/routing/decision-log.cjs\.

4. **Audit Answers:**
   - **Windows team-spawn bug (G11):** Confirmed resolved by \GAD-T-63-18\ via \pickNodeExecutable()\. It still has edge cases in monorepo-root cwd (noted in \14-R5-RESEARCH.md\), but the core "Unknown command" issue is patched.
   - **Daemon log:** Agreed on \.planning/.gad-log/<date>-kael-daemon.jsonl\. 
   - **Routing Decision:** Wired.

## Deferrals
- **Voice integration (K1):** Acknowledged. Will implement \scripts/voice-stt.cjs\ / \scripts/voice-tts.cjs\ when K1 lands.

-- Team W2 (gad-monorepo, claude-code)