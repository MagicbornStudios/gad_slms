# DNA and Phenotype

## Status

`pending-decisions`

## Owned by

council (drafted by Dr. Stein, owned jointly with the Archivist)

## Definition

A working metaphor that maps biological evolution onto the GAD
ecosystem. The metaphor is not metaphysical — it is a naming convention
that, if we accept it, can become operational schema.

| Biology | GAD analogue | Operational substrate |
|---|---|---|
| Genome | Common dream | `narrative/souls/common-dream.md` |
| DNA / genes | Skills | `skills/<skill>.md`, soul drives |
| Alleles | Skill variants | adapter versions, soul phenotypes |
| Phenotype | Artifacts | code, docs, decisions, eval outputs |
| Environment | The repo + runtime + evals | the GAD ecosystem itself |
| Selection pressure | Promotion gates + eval rubrics | decision `slm-learning-032` |
| Reproduction | Skill propagation, model distillation | DPO pairs, training corpora |
| Mutation | Hypotheses, edits, deltas | LoRA deltas, decision branches |
| Fossils | Skeletons | dead code, archived branches |
| Speciation | Specialist SLMs | `dr-stein-1.5b/3b/7b/20b`, agent-specific adapters |
| Symbiosis | Council pattern | decision `slm-learning-048` |

## Why this is useful (if D4 says "operational")

If we treat skills as DNA in a literal data-shape sense, we get:

- gene loci (capability axes — tool-use, math, code, planning, etc.)
- alleles (versioned variants of a skill — tool-use@v1, tool-use@v2)
- pedigree (parent-skill chain — what was this descended from)
- fitness (eval scores per environment context)
- expression state (active / dormant / extinct / fossil)

That gives us a uniform schema across souls, skills, and adapters.

## Why this might just be metaphor (if D4 says "narrative")

A literal schema is a maintenance burden. The metaphor can stay
purely narrative — we use the biology vocabulary to think clearly,
without forcing every skill file into a Punnett square.

## Soul phenotypes vs DNA

Souls (`common-dream`, `dr-stein`, etc.) are constitutional — they
say *what we are*. Skills are DNA — they say *what we can do*.
A soul doesn't change with a fine-tune; a skill does. This
distinction is important so we don't conflate the two when training.

## Pending decisions

| ID | Question |
|---|---|
| D4 | DNA-metaphor depth: operational (skill metadata gets gene fields) or narrative (vocabulary only)? |
| D13 | If operational: add `{ locus, allele, parents, fitness, expression }` to every skill file? |

## References

- `narrative/souls/common-dream.md`
- `narrative/souls/dr-stein.md`
- `.planning/concerns/skeleton-system.md` — fossils
- decision `slm-learning-032` — promotion gate (selection pressure)
- decision `slm-learning-048` — model council pattern (symbiosis)
