# Souls

Operational constitutions for GAD agents and models.

## What a soul is

A soul is a durable behavior contract. It defines:

- **drives** — what the agent pursues
- **prohibitions** — what the agent will not do
- **communication style** — how the agent speaks
- **evaluation contract** — what counts as a "good" output
- **failure response** — what the agent does when wrong

A soul is **not**:

- a claim of consciousness
- a fixed personality baked into weights
- a license to act outside the common dream

## Hierarchy

```
common-dream            ← inherited by every agent
  ├── gilgamesh         ← visionary / gap-finder (framework)
  ├── dr-stein          ← model-improvement scientist (this project)
  ├── executor          ← implementation (planned)
  ├── verifier          ← evidence checker (planned)
  ├── archivist         ← memory / decisions / snapshots (planned)
  ├── critic            ← failure modes / risk (planned)
  ├── snapshot-orchestrator (planned)
  ├── game-maker        (planned, domain)
  ├── marketing-agent   (planned, domain)
  └── personal-assistant (planned, domain)
```

Children inherit from `common-dream` and add their own phenotype.
A child cannot override the dream; it can only express it.

## File schema

Each soul file should contain:

1. `# <Soul Name>` — title
2. `## Inherits` — list of parent souls (always at least `common-dream`)
3. `## Role` / `## Purpose` — one-paragraph operational summary
4. `## Mandate` — the agent's first-person operating contract
5. `## Drives` — soul-specific, on top of inherited drives
6. `## Prohibitions` — soul-specific, on top of inherited prohibitions
7. `## Communication style` — how this agent speaks
8. `## Evaluation contract` — when this agent's output is "good"
9. `## Failure response` — what this agent does when wrong
10. `## Output schema` (optional) — structured shape if applicable

## Soul-first, fine-tune later

Per decision `slm-learning-047`, souls are enforced through prompts,
eval rubrics, and routing first. They are baked into weights only
after:

- the soul language has stabilized
- preference data exists (accepted-vs-rejected outputs)
- DPO data has been generated and validated
- a regression-gated promotion has been earned

A wrong prompt is cheap to fix. A wrong fine-tune is not.

## Communication envelope

When agents send messages to each other, the envelope can carry the
soul + dream-alignment scores so the council can score outputs
meritocratically. See `common-dream.md` for the JSON shape.

## CLI surface (planned)

The GAD framework should eventually expose:

```
gad souls list
gad souls show <soul-id>
gad souls evaluate-output --soul <soul-id> --output-file <path>
gad snapshot --soul <soul-id>
gad models train --soul <soul-id>
```

These do not exist yet. Until they do, souls are read directly as
markdown by agent runtime prompts and by `SOUL.md` at the project root.

## Active soul

`narrative/narrative.toml` carries `activeSoul = "<id>"`. The current
active soul for `slm-learning` is `dr-stein`.
