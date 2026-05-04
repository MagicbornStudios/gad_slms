---
name: gad-proto-skill-battery
description: >-
  Run a per-proto-skill discoverability + supersession test battery. For each
  staged proto-skill (or promoted-from-proto skill), spawn a cold subagent that
  tries to discover the skill from a paraphrased trigger derived from its own
  description, then spawn a second cold agent that checks whether any OTHER
  proto-skill supersedes it. Produces findability + execution-sufficiency
  scores and a shed_score identifying eviction candidates. Runs automatically
  at the end of each `gad evolution evolve` cycle — the natural feedback loop
  as proto-skills enter and leave the project. Fires on "run proto-skill
  battery", "test proto-skills", "shed audit", or as the trailing hook in
  evolution-evolve workflow step 9. Different from `gad-discovery-test`: this
  battery is scoped to proto-skills only and the arm-2 question is
  proto-vs-proto supersession, NOT proto-vs-canonical replacement (canonical
  is framework-specific; projects have their own skill ecosystems that grow
  and obsolete each other).
lane: meta
type: meta-framework
workflow: workflows/proto-skill-battery.md
---

# gad-proto-skill-battery

**Workflow:** [workflows/proto-skill-battery.md](../../workflows/proto-skill-battery.md)

Fire when:
- `gad evolution evolve` completes and has newly-drafted or newly-promoted proto-skills
- operator says "run the proto-skill battery", "shed audit", "test proto-skills"
- periodic regression check (same cadence as evolution cycles — not on every commit)

Run the workflow. All procedural detail, agent prompts, scoring rubric, and
shed thresholds live in the workflow file per the canonical skill shape
(references/skill-shape.md, decision gad-190).
