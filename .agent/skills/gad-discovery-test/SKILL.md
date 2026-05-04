---
name: gad-discovery-test
description: >-
  Run the subagent discovery test battery — spawn N cold agents with distinct
  tasks, restrict their tools to gad CLI + Read-for-CLI-surfaced-paths, and
  measure how findable the skill catalog is to a cold agent. Produces a
  findings report with mean confidence, per-agent read-chain trace, and a
  flow map of which files were reached from which entry points. Fires on
  "run discovery test", "test skill findability", "rerun subagent battery",
  or as a regression test after skill catalog / CLI surface changes. Also
  populates site/data/discovery-findings.json for the planning site
  visualization.
lane: meta
type: meta-framework
workflow: workflows/discovery-test.md
---

# gad-discovery-test

**Workflow:** [workflows/discovery-test.md](../../workflows/discovery-test.md)

Fire when:
- the skill catalog changes (add, rename, delete, promote, demote)
- CLI discovery surface changes (`gad skill list`, `gad skill show`, `gad snapshot`)
- `references/skill-shape.md` or `references/proto-skills.md` changes
- operator asks to "test findability" or "rerun the discovery battery"
- as a periodic regression check to keep mean confidence ≥ 8.5

Run the workflow. All procedural detail, agent prompts, JSON output schema,
and site data integration live in the workflow file per the canonical skill
shape (references/skill-shape.md, decision gad-190).
