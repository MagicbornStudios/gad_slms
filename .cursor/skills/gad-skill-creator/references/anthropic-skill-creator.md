# Anthropic Skill Creator Reference

This GAD skill creator is built on top of the Anthropic skill-creator.
The full methodology is installed at `.cursor/skills/skill-creator/`.

## Key files to read when needed

| File | When to read |
|---|---|
| `.cursor/skills/skill-creator/SKILL.md` | Full creation + eval loop methodology |
| `.cursor/skills/skill-creator/references/schemas.md` | JSON schemas for evals.json, grading.json, benchmark.json |
| `.cursor/skills/skill-creator/agents/grader.md` | How to grade assertion results |
| `.cursor/skills/skill-creator/agents/comparator.md` | Blind A/B comparison |
| `.cursor/skills/skill-creator/agents/analyzer.md` | Analyzing benchmark results |

## External references

| Resource | URL | Use |
|---|---|---|
| agentskills.io | https://agentskills.io/home | Cross-client skill interoperability standard |
| Anthropic Skills Guide | resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf | Canonical skill quality reference (decision gad-70) |

## GAD CLI commands relevant to skill creation

```sh
gad eval setup --project <name>    # Scaffold eval project
gad eval run <project>             # Run eval
gad eval score --project <name>    # Score results
gad eval list                      # List all eval projects
gad eval skill <name>              # Per-skill eval harness (gad-87)
```
