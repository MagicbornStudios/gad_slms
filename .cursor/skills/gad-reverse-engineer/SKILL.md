---
name: gad-reverse-engineer
description: Analyze any codebase (local or GitHub URL) and extract implementation-agnostic requirements plus system-skill contracts for clean-room reimplementation
lane: [dev, meta]
type: meta-framework
argument-hint: --path <local-path> | --repo <github-url> [--branch <branch>]
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Agent
workflow: workflows/reverse-engineer.md
---


# gad-reverse-engineer

**Workflow:** [workflows/reverse-engineer.md](../../workflows/reverse-engineer.md)

Run the workflow. All procedural detail, examples, and tool sequencing live in the workflow file per the canonical skill shape (references/skill-shape.md, decision gad-190).

## Extraction tiers

The workflow uses a tiered extraction pipeline; highest available tier wins:

| Tier | Condition | Extractor | Speed |
|------|-----------|-----------|-------|
| 1 (native) | Target has `.planning/` XML | `lib/graph-extractor.cjs` / `gad query` | Fastest |
| 2 (pdf) | Target contains PDFs | `pdf-parse` (npm, installed) | Fast |
| 3 (graphify) | Python + `graphify` available | `graphify` CLI (external) | Slow |
| Fallback | None of the above | Manual 5-pass deep analysis | Manual |

## Evidence priority (first-class inputs)

Requirement extraction must prioritize evidence in this order:

1. GAD planning artifacts (`.planning/` XML, `planning/` docs, requirements/roadmap/state/decisions)
2. Architecture docs (`architecture.md`, `ARCHITECTURE.md`, ADR-style docs)
3. Product and engineering docs (`docs/`, design notes, specs)
4. Source code (`src/`, app code, tests, configs)

## Outputs

- `REQUIREMENTS.xml` - stable IDs (REQ-NNN)
- `DECISIONS.xml` - inferred architectural decisions (RE-D-NNN)
- `SYSTEM-SKILLS.md` - reusable system-skill contracts (trigger, invariant, required behaviors, non-goals) without prescribing exact implementation
- `notes/` - pitfalls, tech debt, gotchas (one file per topic)
- `graph.json` - knowledge graph of analyzed codebase
