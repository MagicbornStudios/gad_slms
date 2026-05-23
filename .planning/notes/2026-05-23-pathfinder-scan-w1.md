# Pathfinder scan output — W1 backlog convergence (slm-learning, 2026-05-23)

Scan-id: `pf-2026-05-23T06-25-55`
Scope: `handoffs/open/` (4 high-prio phase-04 clusters)
Scout: Pathfinder soul (main-thread cheap-scan, no subagent)
Trigger: operator wave-plan dispatch, W1 mandate

## Reuse clusters

```json
{
  "scan_id": "pf-2026-05-23T06-25-55",
  "scope": "handoffs",
  "reuse_clusters": [
    {
      "cluster_name": "trace-event-envelope",
      "artifacts": [
        "h-2026-05-06T09-30-00-slm-learning-bridge",
        "h-2026-05-09T02-12-53-slm-learning-gateway-wiring",
        "h-2026-05-06T10-00-00-workstream-d-per-domain-adapters"
      ],
      "shared_abstraction_candidate": "scripts/_shared/envelope.py — wrap + validate(schema_v, sha256)",
      "originator": "h-2026-05-06T09-30-00-slm-learning-bridge",
      "second_toucher": "h-2026-05-09T02-12-53-slm-learning-gateway-wiring",
      "confidence": "high",
      "hand_off_to": "refactor"
    },
    {
      "cluster_name": "registry-loader-lookup",
      "artifacts": [
        "h-2026-05-09T02-12-53-slm-learning-gateway-wiring",
        "h-2026-05-06T10-00-00-workstream-d-per-domain-adapters"
      ],
      "shared_abstraction_candidate": "scripts/_shared/registry.py — load + lookup(**filters) + schema-validated",
      "originator": "h-2026-05-09T02-12-53-slm-learning-gateway-wiring",
      "second_toucher": "h-2026-05-06T10-00-00-workstream-d-per-domain-adapters",
      "confidence": "high",
      "hand_off_to": "refactor"
    },
    {
      "cluster_name": "cli-runner-structured-exit",
      "artifacts": [
        "h-2026-05-09T02-12-53-slm-learning-gateway-wiring",
        "h-2026-05-06T10-00-00-workstream-d-per-domain-adapters"
      ],
      "shared_abstraction_candidate": "scripts/_shared/cli_runner.py — @cli_command decorator + structured stderr JSON on exception",
      "originator": "h-2026-05-09T02-12-53-slm-learning-gateway-wiring",
      "second_toucher": "h-2026-05-06T10-00-00-workstream-d-per-domain-adapters",
      "confidence": "medium",
      "hand_off_to": "refactor"
    }
  ],
  "unexplored_edges": [
    {"id": "phase-05-continuous-local-delta-lab", "blocking": false, "cheap_reorder_candidate": true},
    {"id": "phase-06-swe-bench-integration", "blocking": false, "cheap_reorder_candidate": false}
  ],
  "convergence_warnings": [
    "evolution-loop handoff (h-2026-05-09T01-39-05) overlaps gateway-wiring on `gad evolution evolve` invocation but is single-use, NOT a refactor pair"
  ],
  "dead_ends": [
    "h-2026-05-05T04-38-02-slm-learning-00 (phase 00, no clear reuse)",
    "h-2026-05-05T05-40-41-slm-learning-02 (phase 02, no clear reuse)",
    "h-2026-05-07T15-50-09-slm-learning-04 (codex-cli runtime, prescribed-context — non-refactor scope)"
  ],
  "recommended_next_scan": "After W1 lands 6 commits, re-scan with focus on phase-05 (Continuous Local Delta Lab) for the post-refactor reuse pattern — likely candidate adapter eval pipeline + promotion gate."
}
```

## Notes

- Scan was cheap (~6 grep calls + 4 head reads). No expensive model used.
- Cluster A originator (bridge handoff) was created first chronologically and ALSO has the most-explicit schema spec. Strong originator signal.
- Cluster B + C share the same originator + second-toucher pair (gateway-wiring → adapters), which means both refactor lifts can be done in a single sitting by the same worker.
- Cluster C confidence is `medium` because gateway-wiring's CLI structure is less explicit in the handoff body than the schema is — Refactor soul should read `scripts/gateway/cli.py` BEFORE committing the extract to confirm the shape is actually shared.
- Dead-ends should be handed to Archivist soul in W3 for sweep-close (after Refactor + Dr Stein W2 lands).
