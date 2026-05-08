# Monorepo evolution-prep survey

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Source:** Explore subagent walked sibling project planning surfaces.
**Trigger:** Operator signal "pressure is building up, level up and evolve, same with the monorepo."

## Recommended evolution order

1. **slm-learning** (HIGH readiness) — fire now
2. **grime_time_site** (LOW — stale, blocked on admin close of Phase 03)
3. **custom_portfolio / get-anything-done** (HIGH but dependent on slm-learning Kael-house)

## Per-project verdicts

### 1. slm-learning — fire `gad evolution evolve` now
- Phase 04 substrate landed (probes / vLLM / rule router / corpus extractor)
- Decisions 195–200 closed the framework loop (souls/houses, registry, teacher policy, Kael moat)
- 9 handoffs filed (some already picked up cross-team)
- 62 state-log entries; pressure compounded
- Charter rungs proven at 7B + 1.5B; 3B sweep firing tonight
- **Highest-leverage pre-evolve action:** synthesize cross-project dependencies (Gemini comparator handoff pickup, Kael soul lineage with monorepo D-324/325, multi-task LoRA dataset gaps) into Phase 05 plan.

### 2. grime_time_site — admin close first
- Phase 03 marked in-progress but `.planning/` stale 10 weeks
- No state-log entries since 2026-03-28
- Codebase shows final-touches commits (CRM, billing, auth, seed) without closure
- **Pre-evolve:** `gad phase audit 03` → file missing decisions (demo readiness, Vercel deploy, Supabase connection) → stamp/migrate tasks → THEN evolve

### 3. custom_portfolio (monorepo) — wait for slm-learning Kael-house
- Phase 173 (Kael as operational backbone) ACTIVE and flowing
- Phase 174 registered (multi-soul rooms scaffold)
- Dispatcher LIVE (heartbeat 2026-05-08T21:50)
- 10 proto-skills queued — mostly stale environment-bootstrap runtime preflights
- **Pre-evolve:** wait for slm-learning Phase 05 to land Kael-house definition; then deprecate 10 stale proto-skills + fire Phase 175 (multi-soul daemon + routing). Sequential dependency.

## Cross-project constraint

slm-learning's Phase 05 (Continuous Local Delta Lab) is gated on monorepo soul infrastructure. Monorepo Phase 175 (multi-soul daemon) is gated on slm-learning's Kael-house definition. **Right order:** slm-learning evolves first → unblocks Phase 05 → defines Kael-house → unblocks monorepo Phase 175.

## Real session-level evolution candidates surfaced today

These are the patterns this session generated that deserve skill capture:

| Candidate | Why | Captured as |
|---|---|---|
| Registry as first-class artifact (datasets/model_families/teachers + sync + news) | Replaces implicit "we know about these datasets" with version-controlled JSON | Decision 198 |
| Teacher policy 6-role split (teacher / bulk_labeler / backbone / truth / inspector / comparator) | Prevents the conflation that made the original ChatGPT framing wrong | Decision 197 + teacher_species_policy.md |
| Kael moat thesis (integration depth × speed × cost, NOT benchmark parity) | Reframes optimization target away from impossible HE/MBPP race with Opus | Decision 199 |
| Teacher rows require provenance + accepted_by | Makes "teacher" empirical instead of vibes | Decision 200 |
| Modal CLI on Windows needs `PYTHONIOENCODING=utf-8` (every invocation) | Bit us twice today; charmap encode error kills CLI before job submission | Should be skill — TODO |

— Dr. Stein, monorepo evolution-prep, 2026-05-08
