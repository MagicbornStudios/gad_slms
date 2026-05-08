# Skill Pressure & Evolution Signal: Framework & Roadmap

**Decision Ref**: slm-learning-128 (Skills must generate measurable learning signal)  
**Author Context**: Operator observation: "we really need to think about the skills and pressure stats and the correlation and find some meaning to them as we want to evolve. If we learn nothing new that is useful, then those skills are meaningless."  
**Status**: Phase-1 Local Analysis (infrastructure gap identified)  
**Date**: 2026-05-07

---

## The Principle

A skill is justified only if it produces measurable downstream learning signal. If a skill is invoked but never correlates with an improved outcome (eval lift, decision logged, contract passed, fallback dropped, handoff completed, state_log entry with positive tags), then keeping it consumes maintenance surface without generating value.

This mirrors the operator's framing exactly: **meaningless skills are those that teach us nothing new that is useful**.

---

## Why This Matters for GAD Evolution

Per `slm-learning-103` (Compare-and-Compete Discipline), every candidate model must produce four evaluation rows or it is refused for promotion. Similarly, every *framework capability* (skill, tool, routing decision) should demonstrate measurable learning signal or be subject to shedding.

Current state:
- `gad evolution shed` identifies 66 skills as candidates for removal (snapshot 2026-05-05)
- No formal mechanism yet exists to correlate skill invocation with learning outcome
- Many skills fly blind: invoked, but their downstream effects are unmeasured or invisible in telemetry

This creates a credibility gap: we claim skills drive evolution, but we cannot prove it.

---

## Proposed Correlation Methodology

### Phase-1: Local Event Correlation

Correlate each skill invocation with downstream events in a 30-minute window:

| Signal Type | Event Kind | Weight | Interpretation |
|---|---|---|---|
| **eval_lift** | `eval_completed` with score delta | 0.4 | Direct proof of improved capability |
| **decisions_logged** | `decision_added` events | 0.3 | Skill surfaced decision point (strategy, tradeoff, regulation) |
| **commits** | `git commit` events | 0.2 | Skill triggered meaningful artifact generation |
| **handoffs_completed** | `handoff_completed` events | 0.1 | Skill unblocked downstream work |

**Net signal score** = (eval_lift × 0.4 + decisions × 0.3 + commits × 0.2 + handoffs × 0.1) / invocations

Skills with score < 0.1 are flagged as **eviction candidates**. Skills with score > 0.5 are **high-signal accelerators** worth investing in (e.g., new training, optimization, composition).

### Phase-2: Aggregate Telemetry (Cross-Project Handoff)

Current telemetry events do not include explicit `skill_invocation` envelopes. The gad CLI telemetry export needs:

1. New event kind: `skill_invocation` with fields:
   ```json
   {
     "kind": "skill_invocation",
     "skill_id": "gad-evolution-evolve",
     "skill_module": "slm_learning.gad_evolution",
     "runtime": "claude-code",
     "session_id": "...",
     "ts": "2026-05-07T...",
     "context": {
       "projectid": "slm-learning",
       "phase": "145",
       "decision_refs": ["slm-learning-128"]
     }
   }
   ```

2. Outcome signal in skill completion event (success/failure, time-to-outcome)

3. Adapter context metadata (which SLM resolved the skill?)

This unblocks phase-2 (aggregate + cross-project signal tracking).

---

## Concrete Signal Types

### 1. Eval Lift Correlation
A skill that triggers training, evaluation, or candidate promotion shows immediate measurable signal.

**Example**: `gad-evolution-evolve` skill → initiates training run → eval completes with 8% lift → net_signal_score = +0.40 per invocation

**Anti-example**: `gad-note` skill invoked daily, never followed by eval or decision → net_signal_score = 0

### 2. Contract-Pass Correlation
Skills that route code through verification gates (SWE-bench contract, HumanEval harness, doc-verifier checks) directly prove capability claims.

**Example**: `verify-clean-clone-site-build` → triggers pre-flight checks → 5 checks pass → net_signal_score = +0.10 per invocation

### 3. Fallback-Rate-Drop Correlation
A skill that reduces the need for human fallback (e.g., automatic fix application, adaptive prompt selection) shows indirect but measurable signal.

**Example**: `gad-debug` invoked on error → suggests fix → fix applied → no human fallback needed → state_log entry "auto_fix_applied=true"

### 4. Decision-Yield Correlation
Skills that surface novel decision points (tradeoffs, policy choices, architecture forks) enable higher-level strategy.

**Example**: `gad-discuss-phase --auto` → surfaces 3 phase assumptions → operator adds 2 decision records → skill net_signal_score = +0.20

---

## External Skill Catalogs: The Operator's Note

The operator mentioned: "we could do this with tons of different skills from skills.sh and agentskills or openclaw skills."

**Recommendation**: Apply the same correlation lens to external skill catalogs before installation.

1. **skills.sh**: Audit the 50+ tool-invocation shims for measurable outcomes
2. **agentskills**: Identify which agent patterns generate contract pass or decision signals
3. **openclaw skills**: Evaluate computer-use traces for downstream eval lift

Each external skill must provide:
- MCP-equivalent telemetry export (what events does it emit?)
- Outcome signal definition (what counts as "success"?)
- Validation dataset (controlled eval on known-good prompts)

**Gate**: No external skill is installed without a phase-gate eval on its correlation signal in a held-out test set.

---

## Integration Roadmap

### Phase 1 (NOW): Local Correlation Analysis
- **Script**: `scripts/research/skill_pressure_correlation.py`
- **Scope**: Reads `.planning/.gad-log/*.jsonl` + `.planning/.provenance/*.jsonl` + `.planning/.trace-events.jsonl`
- **Output**: `reports/research/skill_pressure_correlation.json` + `.md`
- **Limitation**: No explicit skill_invoke events yet (infrastructure gap)
- **Time**: ~1 hour, runs locally, no new dependencies

### Phase 2 (CROSS-PROJECT HANDOFF): GAD CLI Telemetry Extension
- **Owner**: gad CLI maintainers (framework extension)
- **Work**: Add `skill_invocation` event envelope + skill metadata to telemetry export
- **Benefit**: All downstream projects (slm-learning, others) inherit visibility into skill pressure signals
- **Dependency**: Requires gad CLI PR + versioning coordination
- **Gate**: Unblocks phase-3 aggregate analysis

### Phase 3 (DEPENDENT): Aggregate Multi-Project Signal
- **Scope**: Correlate skill pressure signals across slm-learning, other research projects, customer workloads
- **Output**: Cross-project evolution recommendations (which skills drive value universally? which are domain-specific?)
- **Decision**: slm-learning-129 (Multi-project skill portfolio strategy)

### Phase 4 (OPTIONAL): Skill Auto-Shedding Policy
- **Rule**: Skills with score < 0.05 for >30 days are marked deprecated, removed after 60 days
- **Exception**: Infrastructure/setup skills (score invisible but structurally necessary) are exempted by override
- **Benefit**: Automatic code hygiene; forces intentional skill design

---

## Open Questions

1. **Invisible signal**: How do we account for skills that enable work silently (e.g., `gad-settings`, `agent-state-session-hygiene`)? These are structurally necessary but produce zero direct events. Proposed: add explicit "infrastructure" class; exempt from shedding but measure via indirect proxy (session success rate, error rate reduction).

2. **Correlation window**: Is 30 minutes the right window? Some skills (training runs) produce outcomes hours later. Proposed: make window tunable; measure skill-outcome latency distribution first (2-3 runs per skill in controlled setting).

3. **Composite skills**: `gad-discuss-phase --chain` bundles multiple sub-skills. How do we attribute signal to the composite vs. components? Proposed: measure both; report correlation.depth in JSON output.

4. **Seasonal signal**: Skills may have high signal in one phase (e.g., `gad-plan-milestone` during phase-gate) and low signal in another. Raw correlation may miss phase-aware patterns. Proposed: stratify by phase in phase-2 telemetry; defer to phase-3 for cross-phase analysis.

5. **Skill interdependence**: `gad-evolution-evolve` may trigger `gad-milestone` + `gad-task-checkpoint` in sequence. Do we report joint signal or per-skill? Proposed: report both; note dependency graph in JSON metadata.

---

## Phase-1 Implementation (What the Script Does Today)

The `skill_pressure_correlation.py` script:

1. **Reads telemetry**:
   - `gad-log/*.jsonl`: Command history (commit, decision events)
   - `provenance/*.jsonl`: Tool use records with trigger_skill metadata
   - `trace-events.jsonl`: System-level events (eval, skill completion)

2. **Extracts skill invocations**: Looks for `trigger_skill` field in provenance events

3. **Correlates with 30-min window**: For each invocation, scans for downstream:
   - eval_completed with score delta
   - decision_added events
   - git commit commands
   - handoff_completed events
   - state_log entries with positive tags

4. **Computes per-skill metrics**:
   ```
   net_signal_score = (eval_lift × 0.4 + decisions × 0.3 + commits × 0.2 + handoffs × 0.1) / invocations
   ```

5. **Flags eviction candidates**: Skills with score < 0.1

6. **Outputs**:
   - `reports/research/skill_pressure_correlation.json`: Full correlation table (structured for downstream automation)
   - `reports/research/skill_pressure_correlation.md`: Human-readable report with top performers + eviction candidates

### Current Limitation
Because skill_invoke events are not yet in the telemetry envelope, the script will likely report zero or very low signal. This is **not a failure**; it's expected. The script validates the methodology and identifies the infrastructure gap.

**Expected first-run output** (with real telemetry): "Invocations found: 0. Telemetry exists but skill_invoke events not populated. See decision slm-learning-128 for integration roadmap."

---

## Success Criteria (Phase 1)

- [ ] Script runs without error (stdlib only; no deps)
- [ ] Fallback message is clear if telemetry missing (suggests `gad telemetry export` command)
- [ ] JSON output is structured for downstream automation (easy to pipe to dashboard, rules engine, etc.)
- [ ] Markdown report is human-readable and actionable (identifies top skills + eviction candidates)
- [ ] Integration gap is documented (what telemetry extension is needed for phase 2?)
- [ ] Decision record slm-learning-128 is created and referenced

---

## References

- **slm-learning-103**: Compare-and-Compete Discipline (model promotion gates)
- **slm-learning-101**: Six Research Tracks (skills power lanes A-F)
- **slm-learning-106**: Research Intake Protocol (skills are like external code: require review + signal proof)
- **CLAUDE.md "Lane Discipline"**: Single-agent by default; single-skill per task unless explicitly composed
- **AGENTS.md "Evolution Mechanism"**: `gad evolution shed` + evolution pressure from downstream outcomes

---

## Checklist: Integration & Handoff

### For slm-learning lane (NOW):
- [x] Define correlation methodology (this doc)
- [x] Implement phase-1 script (local correlation)
- [ ] Run script on existing telemetry; document findings
- [ ] Create decision record slm-learning-128
- [ ] Handoff integration scope to gad CLI maintainers

### For gad CLI maintainers (FUTURE, CROSS-PROJECT):
- [ ] Extend telemetry export schema to emit `skill_invocation` events
- [ ] Add skill metadata fields (skill_id, module, decision_refs, context)
- [ ] Coordinate versioning with slm-learning phase-2 consumer
- [ ] Document skill telemetry contract in gad CLI docs

### For downstream projects (AFTER phase 2):
- [ ] Consume skill_invocation events in local correlation analysis
- [ ] Publish correlation signal to shared dashboard/registry
- [ ] Gate external skill installations on demonstrated correlation signal
- [ ] Participate in multi-project skill portfolio strategy (phase 3)

---

**End of Document**

Generation time: 2026-05-07  
Methodology version: 1.0  
Next review date: 2026-05-14 (after first run; update with actual findings)
