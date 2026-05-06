# Skeleton System

## Status

`pending-decisions`

## Owned by

`archivist`

## Definition

A **skeleton** is a code/doc/spec/skill/branch artifact that has died
or been deliberately archived but is preserved because it carries
information about a previous form of the system. Skeletons are the
fossil record. They are mineable, citable, and sometimes revivable.

The repository is the dig site. Git is the stratigraphy. The
**museum/zoo** (current candidate: `tmp/`) is where extracted
skeletons get cataloged for re-use.

This concern owns:

- the definition of "dead" (what makes an artifact a skeleton)
- the rules for where skeletons live
- the rules for reviving a skeleton
- the rules for mining skeletons (turning fossils into present-day
  evidence for new decisions)

## Why we need this

Coding agents (and humans) repeatedly:

- delete code that turns out to have been load-bearing
- forget that a previous form already solved a problem we are now
  re-solving
- fail to learn from failed branches because the failure is
  unannotated
- conflate "no longer used" with "should be deleted"

A skeleton system makes "deprecated" a first-class state, not an
implicit one.

## Provisional skeleton signals

Until decision D1 settles scope, working signals are:

- no inbound imports / call sites in the live tree
- no commits to the file in the last N days (N pending)
- explicit `# SKELETON:` or `# DEPRECATED:` marker
- file referenced only from notes/decisions (history-only)
- unit test coverage zero AND no integration coverage
- file last touched only by automated reformatters

A skeleton classifier would AND/OR these signals based on policy.

## Provisional storage layout

Pending decisions D2 + D11. Candidate layouts:

| Layout | Pros | Cons |
|---|---|---|
| in-place marker (`# SKELETON: ...`) | minimal disruption, git history intact | clutters live tree |
| move to `tmp/skeletons/` | clean live tree | path moves break old grep references |
| both: marker first, move on age threshold | progressive interment | more machinery |
| `archive/` (no museum/zoo split) | simpler | loses the "alive but caged" vs "frozen" distinction |
| `tmp/museum/` (frozen) + `tmp/zoo/` (deprecated-but-on-life-support) | preserves intent | naming overhead |

## Provisional revival rules

Pending decision D3. Working stance:

- a skeleton can be cited as evidence freely
- a skeleton can be re-imported only after a written hypothesis
  explains why it is alive again
- a revived skeleton must annotate **what changed in the world** that
  justifies revival
- counter-rotation: if a skeleton is revived twice, the third
  attempt requires the council to refuse or accept explicitly

## Mining (use as evidence)

Skeletons are not just storage. They are training data and decision
substrate:

- preference-pair data (the live form vs the dead form, with the
  reason for the death as the preference signal)
- failure post-mortems for Dr. Stein experiments
- repo-archaeology training corpus for the git-fluency capability
- counter-examples for promotion gates (this WAS promoted and it died
  — what was missed?)

## Pending decisions

| ID | Question |
|---|---|
| D1 | What artifact types count as skeletons (code only / +docs / +specs / +branches / +skills / all)? |
| D2 | Storage policy (in-place / move / both)? |
| D3 | Revival rules (free / gated / counter-rotation)? |
| D10 | Should models be scored on skeleton recognition (don't call dead functions)? |
| D11 | tmp namespace (`tmp/museum/` + `tmp/zoo/` / unified `archive/` / current ad-hoc tmp)? |
| D12 | One-time backward sweep over the existing repo, or forward-only? |

## References

- `narrative/souls/archivist.md` — owning soul
- `.planning/concerns/dna-and-phenotype.md` — biology metaphor that
  this concern instantiates (skeletons = fossils)
- `.planning/notes/2026-05-06-evolution-skeletons-and-souls.md` —
  introductory note
