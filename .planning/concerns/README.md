# Concerns

One file per concern. Each file in this directory describes a
cross-cutting topic that does not belong to a single phase, decision,
or task. Concerns own policy; phases consume policy.

## Why this directory exists

- Phases describe time-bound work.
- Tasks describe units of work.
- Decisions describe commitments.
- Notes describe moments.
- **Concerns describe ongoing rules.**

A concern is the place where "how do we always treat X" lives.

## Naming

`<concern-slug>.md`. Lowercase, kebab-case. One concern per file.

## Schema

Each concern file should contain:

1. `# <Concern Name>` — title
2. `## Status` — one of: `provisional`, `active`, `pending-decisions`, `archived`
3. `## Owned by` — soul (e.g. `archivist`) or "council"
4. `## Definition` — what this concern is, in one paragraph
5. `## Policy` — the operational rules (or "pending — see decisions D#")
6. `## Pending decisions` — list of decision IDs the concern is waiting on
7. `## References` — related decisions, files, notes, code paths

## Current concerns

- `skeleton-system.md` — dead/archived code, the museum/zoo, fossil-mining
- `dna-and-phenotype.md` — biology metaphor mapping (skills as DNA, artifacts as phenotypes)
- `git-fluency.md` — coding-agent git mastery as capability target
- `constitution-impact.md` — open hypothesis: does soul prompting affect training/output quality?

More will be added as the system grows.
