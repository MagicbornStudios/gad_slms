# Codebase Attention

## Status

`active`

## Owned by

Dr. Stein (designer) + Critic (failure-mode register) + Archivist
(historical impact mining)

## Definition

Attention generalized beyond neural attention heads. In a transformer,
attention answers: which tokens matter most for this token right now?
In GAD, we ask:

> Which parts of the repo, UI, task, artifact, runtime, or
> environment deserve the most care right now?

This concern owns the **codebase attention map**, the **environment
lane policy**, and the **learned impact score**. It is the spec
agents consult before editing a file: "how careful do I need to be
here, what checks are required, am I in dev or production?"

## Why this concern exists

GAD agents (and humans) treat every file equally by default. Real
engineers do not. Touching `tmp/prototype/foo.ts` should not require
the same proof as touching `packages/runtime/router.ts`. But without a
machine-readable map, agents can't apply that discipline reliably.

A codebase attention system makes the discipline explicit and
queryable.

## Lanes

| Lane | Score band | Behavior |
|---|---|---|
| `free` | 0.00–0.20 | scratch / prototype / tmp / museum / sandbox — agents move fast, try variants, do not over-test |
| `prototype` | 0.20–0.40 | early implementation, isolated changes, light proof |
| `dev` | 0.40–0.65 | active feature work, local tests sufficient |
| `integration` | 0.65–0.85 | shared packages, cross-domain, tests + diff summary required |
| `production` | 0.85–1.00 | deployed / user-facing / core paths, strict evidence + rollback plan |
| `hotfix` | (override) | minimal diff, high caution, rollback mandatory |

## Score components (rule-based v1)

```
attention_score =
   +0.30 if production_path
   +0.25 if dependency_centrality_high  (>= 5 inbound imports)
   +0.25 if recent_failures              (touched in failed run last 30d)
   +0.20 if active_phase_relevance       (named in current STATE.xml next-action)
   +0.20 if security_or_data_path        (auth / secret / billing / migration / deploy)
   +0.15 if low_test_coverage            (< 50% lines covered)
   +0.10 if recent_high_churn            (> 10 commits last 30d)
   -0.30 if tmp_or_prototype_or_museum
   -0.20 if skeleton_marked_prototype
   +0.50 if quarantined_or_dangerous     (with explicit warning)
```

Clamp to [0, 1]. Output the score plus the contributing reasons.

## Output schema

```json
{
  "path": "src/runtime/router.ts",
  "attention_score": 0.92,
  "lane": "integration",
  "reasons": [
    "production path",
    "high dependency centrality",
    "recent failures",
    "runtime selection impact"
  ],
  "required_checks": [
    "unit_tests",
    "routing_eval",
    "snapshot_update",
    "decision_log"
  ],
  "allowed_agents": ["dr-stein", "executor", "verifier"],
  "fallback_runtime": "claude-code"
}
```

A low-attention example:

```json
{
  "path": "tmp/prototype-router-v0.ts",
  "attention_score": 0.21,
  "lane": "prototype",
  "reasons": [
    "tmp prototype path",
    "not imported by production",
    "no deploy impact"
  ],
  "required_policy": "free_experiment"
}
```

## Implementation plan

| Step | Component | LOC |
|---|---|---|
| 1 | `scripts/attention/score.py` — rule-based scorer reading from git + dependency graph + STATE.xml + skeleton list | ~250 |
| 2 | `.gad/attention/codebase-attention.json` — generated artifact, ignored from git, rebuilt by `gad attention scan` | output |
| 3 | snapshot integration — `gad snapshot --attention` includes the high-attention files for the active phase | ~50 |
| 4 | eval fixture — `tests/test_attention_ranking.py` ensures `tmp/*` < `packages/runtime/*` | ~100 |
| 5 | learned classifier candidate — Phase 05 first SLM target after doc-verifier (input: path features + git metadata, output: lane + score + reasons) | trainer config |

## Learned impact (long-term)

Beyond the rule-based score, attention can absorb **learned impact**:

```json
{
  "path": "src/ai/model-gateway.ts",
  "learned_impact": {
    "avg_failure_rate_after_touch": 0.38,
    "avg_repair_attempts": 2.1,
    "affected_domains": ["runtime", "models", "evals"],
    "best_runtime": "claude-code",
    "needs_verifier": true
  }
}
```

Mined from `.planning/.trace-events.jsonl` + commit-touched-followed-by-failure
patterns. This is repo memory in the Microsoft sense.

## How agents use the attention map

Before editing, the agent (or `gad-doc` skill, or any tool surface)
consults the attention map for the touched files. The map answers:

- what lane am I in?
- what checks do I owe?
- what historical failures are nearby?
- which agent / runtime is best here?
- am I about to touch a skeleton-revival trap (per `slm-learning-058`)?

The agent's behavior changes accordingly. No manual "prod mode" flag
needed.

## Connection to other concerns

- `.planning/concerns/skeleton-system.md` — skeletons are
  low-attention by definition; reviving one promotes it back into
  active attention space (counter-rotation `slm-learning-058`)
- `.planning/concerns/dna-and-phenotype.md` — attention is
  selection-pressure made explicit at the file level
- `.planning/concerns/git-fluency.md` — git is the substrate from
  which historical-impact features are extracted

## Pending decisions

| ID | Question | Status |
|---|---|---|
| slm-learning-072 | Adopt codebase attention map as a first-class GAD artifact | proposed in this commit |

## References

- forwarded writeup 2026-05-06 (chat): "Attention as a GAD-wide idea"
- decisions `slm-learning-061` (evolution metric), `slm-learning-058`
  (counter-rotation), `slm-learning-049` (adapter ladder)
- soul `narrative/souls/critic.md` — failure-mode register feeds the
  learned-impact dimension
