# Evolution, skeletons, and souls — orienting note

Date: 2026-05-06.

## What changed today

1. Soul system v1 landed (commit `1d03b47`). Common-dream root,
   Dr. Stein as model-improvement scientist, Gilgamesh stub,
   Archivist soul authored. Decisions `slm-learning-044..048` logged.

2. Hype correction. Earlier framing in the substrate SITREP — "match
   Opus 80–95% on bounded domains" — was too confident. Pulled back
   to: the realistic compounding benefit is **workflow memory that
   survives session boundaries** and **cheap routing on narrow
   shapes**. Capability matching is *not* the goal. Useful narrow
   specialists + good orchestration *is* the goal.

3. New concerns added under `.planning/concerns/`:
   - `skeleton-system.md` — dead/archived artifacts as fossil record
   - `dna-and-phenotype.md` — biology metaphor mapping
   - `git-fluency.md` — git as a first-class capability target
   - `constitution-impact.md` — open hypothesis on whether the soul
     actually moves a measurable needle
   - `README.md` — directory schema + 1-file-per-concern rule

4. Archivist soul (`narrative/souls/archivist.md`) authored. Council
   pattern (decision `slm-learning-048`) needed at least one of the
   non-Stein, non-Gilgamesh members on disk to stop being a promise.

## Biology framing — what we are accepting and what we are not

We are accepting:

- skills behave like DNA: copyable, expressible, versioned, heritable
- artifacts are phenotypes: what the DNA produces in this environment
- skeletons are fossils: dead phenotypes preserved as evidence
- the repo + runtime + evals are the environment
- promotion gates are selection pressure
- the council is symbiosis, not hierarchy

We are not accepting:

- that the metaphor is more than naming convention until decision D4
  promotes it to operational schema
- that "evolution" is a license for unbounded growth — selection
  pressure rejects 90% of mutations on purpose
- that we are building life. We are building a maintenance system
  with biology-inspired vocabulary

## Skeletons specifically

- skeletons live in the repo as dead artifacts (dead code, dead docs,
  abandoned branches)
- the museum/zoo (current candidate: `tmp/`) is where they get
  catalogued for retrieval
- git is the dig site
- mining skeletons produces preference data, post-mortem evidence,
  and counter-examples for promotion gates
- the Archivist owns the skeleton concern

The exact rules (storage, revival, scope, naming) are pending the
decisions D1, D2, D3, D10, D11, D12.

## Open hypothesis — does any of this actually help?

`.planning/concerns/constitution-impact.md` makes the question
explicit: training Dr. Stein with soul prompts vs without should
produce a measurable delta. If it doesn't, the soul stays as
prompt-only forever (which is fine — decision `slm-learning-047`
explicitly anticipates this).

The same logic applies to project evolution. We should track whether
phases that run under explicit constitution prompting evolve faster /
log more skeletons / promote more skills than phases that don't.

## What we are NOT doing yet

- baking the soul into Dr. Stein weights (decision 047)
- migrating souls to the framework repo (pending D7)
- authoring the remaining council souls (pending D8)
- running the constitution-impact A/B/C experiment (pending D5)
- a one-time backward skeleton sweep of the existing repo
  (pending D12)

## Reading order for an agent picking up this thread

1. `SOUL.md`
2. `narrative/souls/common-dream.md`
3. `narrative/souls/dr-stein.md`
4. `narrative/souls/archivist.md`
5. `.planning/concerns/README.md`
6. `.planning/concerns/skeleton-system.md`
7. `.planning/concerns/dna-and-phenotype.md`
8. `.planning/concerns/constitution-impact.md`
9. `.planning/concerns/git-fluency.md`
10. this note
11. `gad snapshot --projectid slm-learning`
