---
name: eval-skill-install
framework_skill: true
uses_cli: [gad species setup, gad spawn, gad generation preserve]
description: >-
  Install skills into species templates and run evaluations with them.
  Use when the user wants to evaluate a skill by spawning generations with and
  without it, install a skill from a path or URL into a species template,
  point at a skill folder and wrap it as a species, or compare skill versions.
  Triggers on "evaluate this skill", "test this skill", "install skill into
  species", "spawn generation with skill", "compare skill versions".
lane: meta
type: meta-framework
---

# eval-skill-install

Install skills into GAD species templates and spawn generations to measure their impact.
This is the bridge between skill creation and skill evaluation.

## When to use

- You have a skill and want to know if it helps agents
- You want to compare agent performance with vs without a specific skill
- You want to install a skill from a local path, URL, or npx skills format
- You want to add skills to an existing species that already has generations

## Workflow

### 1. Identify the skill to evaluate

```sh
# Local skill
ls skills/<name>/SKILL.md

# Or download from external source
npx skills add <url> --skill <name>
```

### 2. Choose or create a species

```sh
# List existing species
gad species list

# Create a new species for this skill
gad species setup --species <skill-name>-species
```

### 3. Install the skill into the species template

Copy the skill directory into the species template:

```sh
cp -r skills/<skill-name> species/<species>/template/skills/<skill-name>
```

Update the species's `template/AGENTS.md` to reference the installed skill.

### 4. Spawn with-skill vs without-skill

Spawn two generations:
- **With skill**: template includes the skill in its skills/ directory
- **Without skill**: template has no skills/ directory (baseline)

```sh
gad spawn <project>/<species>   # with skill installed
```

For baseline, temporarily remove the skill from template/ and spawn again.

### 5. Score and compare

```sh
gad generation score --species <species>
gad generation scores <species>   # compare across generations
gad generation diff v1 v2          # detailed comparison
```

### 6. Preserve results

```sh
gad generation preserve <species> v<N> --from <worktree-path>
```

## Installing skills from external sources

### Local path
```sh
cp -r /path/to/skill species/<species>/template/skills/
```

### GitHub URL
```sh
npx skills add https://github.com/<org>/<repo> --skill <name>
# Then copy the installed skill to the species template
```

### Into an existing species with source code
If the species already has generations with source code, install the skill
into a new generation's template to test the skill on the same codebase:

```sh
# Copy previous generation's source as starting point
cp -r species/<species>/v<N>/run/src species/<species>/template/src

# Install skill
cp -r skills/<name> species/<species>/template/skills/

# Spawn
gad spawn <project>/<species>
```

## Vocabulary note (post decision gad-212)

- "Species templates" = what were formerly "eval project templates." They carry skills,
  content, context framework, and tech stack.
- "Spawn a generation" = what was formerly "run the eval." Decision gad-219.
- "Evaluation" in the skill name refers to the methodology — the act of measuring whether
  a skill helps agents. That meaning is preserved.
- If your CLI hasn't caught up to the rename yet, `gad eval setup` / `gad eval run` /
  `gad eval preserve` remain as aliases during the transition.
