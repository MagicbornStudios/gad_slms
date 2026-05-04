---
name: find-skills
status: experimental
origin: human-authored
description: >-
  Discover installed skills relevant to the current task and suggest external
  skills worth installing when no local match exists. Use when you are about
  to attempt a non-trivial task and want to check whether an existing skill
  already solves it, or when you notice you are repeating yourself and suspect
  there should be a skill for this. GAD's find-skills is a thin methodology
  wrapper around the vercel-labs/skills CLI — it delegates actual search and
  listing to npx skills and adds GAD-specific guidance on how to interpret
  the results and which external sources to prefer. Per decisions gad-73
  and gad-85 this is one of the three fundamental skills (find-skills +
  merge-skill + create-skill) that enable the emergent-evolution hypothesis
  to be tested in practice.
lane: meta
type: meta-framework
---

# find-skills

**Experimental — awaiting evaluation harness per decision gad-86.**

## The one-sentence procedure

**`npx skills find "<keywords>"` is the answer.** Everything below is the methodology wrapped around that call.

## Why this skill is a thin wrapper

vercel-labs/skills ([github.com/vercel-labs/skills](https://github.com/vercel-labs/skills)) is the canonical CLI for the open agent-skills ecosystem. It supports 40+ coding agents including every runtime GAD cares about, respects the `skills/` convention from gad-80, handles add/list/find/remove/update/check, and understands GitHub shorthand (`owner/repo`), full URLs, GitLab URLs, and local paths. Per decision gad-85, GAD does NOT reimplement skill discovery — we delegate to `npx skills` and add GAD-specific guidance on when to use it, how to interpret results, and which external sources to trust.

This keeps the skill simple, the installation story consistent with the ecosystem, and GAD's unique value (methodology + evaluation framework + hypothesis testing) is where we put effort instead of reinventing distribution.

## When to load this skill

- You are about to attempt a non-trivial task (a multi-step procedure, a domain-specific workflow, a debugging pattern, a test writing pattern) and want to check whether an existing skill already solves it.
- You notice you are repeating a pattern from an earlier session — suspect there should be a skill for this but you do not remember its name.
- A teammate mentions a skill they used successfully and you want to find it in the ecosystem and install it.
- You are about to write a new skill via `create-skill` and want to check that no existing skill overlaps (gad-81 collision prevention).
- You are deciding whether to `merge-skill` two existing skills and need to see all skills with similar descriptions.

Do NOT load this skill when:

- You know the skill name already. Just load that skill directly.
- You are writing entirely novel research methodology. That is `create-skill` territory — there is nothing to find.

## Procedure

### Step 1 — Search installed skills first

```sh
# Search by keyword in description (fuzzy)
npx skills find "<keywords>"

# List all installed skills in the current project
npx skills list

# Global skills available across all projects
npx skills list -g
```

`npx skills` scans the conventional locations:

- `./<agent>/skills/` (project-scoped, agent-native)
- `./skills/` (project-scoped, cross-client standard)
- `~/.<agent>/skills/` (user-scoped, agent-native)
- `~/skills/` (user-scoped, cross-client standard)
- `~/.config/agents/skills/` (XDG config dir)

It returns matches ranked by description similarity. Each match has a name, description, install source, and location on disk.

**Stop here if the search returns a relevant match.** Install or load the existing skill. Do NOT proceed to the external-source suggestions unless the local results are genuinely insufficient.

### Step 2 — When no local match, suggest external sources

When `npx skills find` returns no relevant results, the request becomes "where should I look next?". Per decision gad-83, find-skills points the user at a small set of trusted external sources in this order:

1. **GAD's own public repo** — `github.com/MagicbornStudios/get-anything-done`. Contains the 27+ workspace skills at `skills/` (post-migration per gad-80). Install:

   ```sh
   npx skills add MagicbornStudios/get-anything-done
   ```

   Or install a specific skill:

   ```sh
   npx skills add MagicbornStudios/get-anything-done --skill <skill-name>
   ```

2. **Anthropic's official skills repo** — `github.com/anthropics/skills`. The canonical reference implementations from Anthropic. Includes `skill-creator`, plus domain skills for PDFs, spreadsheets, presentations, and more. Install:

   ```sh
   npx skills add anthropics/skills --skill <skill-name>
   ```

3. **skill.sh (skills.sh)** — the broader open ecosystem at [skills.sh](https://skills.sh). Browseable, community-authored, mixed quality. Prefer the two above when both have what you need.

**Do NOT** suggest installing from unknown repos without explicit user approval — per decision gad-82 skill security posture, installation is a trust act.

### Step 3 — After install, validate

Once a skill is installed via `npx skills add`, verify:

```sh
# Confirm the install landed where you expected
npx skills list

# Read the skill to understand what it actually does
cat skills/<skill-name>/SKILL.md
```

Read the `SKILL.md` body before using the skill for real work. The name and description in the catalog are tier-1 progressive-disclosure — the full instructions are tier 2 and may surprise you. Also check the frontmatter for:

- `status: experimental | canonical` (per gad-86)
- `origin: human-authored | emergent | inherited`
- `compatibility:` — required system packages, network access, etc.
- `supersedes:` or `superseded-by:` — if the skill is a merge or is deprecated
- any `excluded-from-default-install: true` flags if relevant

### Step 4 — Record what you learned

If you found a useful skill, remember its name for this session. If you searched and found nothing relevant, that is itself a signal — either the skill is truly novel (candidate for `create-skill`), or the search keywords were wrong (try different ones), or the skill exists but has a weird name (search by category).

If the search kept returning the same near-miss skills, that is a `merge-skill` signal — the near-misses are candidates for fusing.

## Common searches

| You are about to... | Try searching for... |
|---|---|
| Debug a failing build | `debug`, `investigate`, `build-failure` |
| Write tests for a module | `test`, `write-tests`, `coverage` |
| Explore an unfamiliar codebase | `map-codebase`, `explore`, `overview` |
| Author a new skill | `create-skill`, `author`, `skill-creator` |
| Plan a multi-step phase | `plan-phase`, `planning`, `roadmap` |
| Sync a statically-generated site | `portfolio-sync`, `prebuild`, `site-sync` |
| Set up a new project | `new-project`, `scaffold`, `bootstrap` |
| Write feature documentation | `write-feature-doc`, `write-tech-doc`, `docs` |
| Verify a phase is done | `verify-phase`, `checkpoint`, `done-criteria` |

If none of these return matches in `npx skills find`, consider that the skill may not exist yet and you are looking at a `create-skill` opportunity.

## Anti-patterns

- **Searching by exact filename** — `npx skills find "portfolio-sync.md"` is worse than `npx skills find "portfolio sync prebuild"`. The CLI matches descriptions, not filenames.
- **Installing everything you find** — context budget is finite. Per gad-81 the target is 3-7 actively-loaded skills per task. More installed does not mean more loaded — progressive disclosure means only the catalog (50-100 tokens per skill) is loaded at session start — but cluttered catalogs make selection ambiguous.
- **Using find-skills when you know the skill name** — just load it directly.
- **Ignoring `status: experimental` in results** — experimental skills have no evaluation evidence. Read their SKILL.md carefully before trusting them.
- **Installing from unknown sources** — per gad-82, unknown repos can inject instructions into the agent's context. Stick to MagicbornStudios/get-anything-done, anthropics/skills, and skills.sh entries you have evaluated.

## What this skill does NOT do

- It does NOT auto-install skills without user approval.
- It does NOT crawl the network looking for skills unsupervised.
- It does NOT attempt to rank skills by quality — it reports what `npx skills find` returns and defers quality judgment to evaluation harness output (per gad-87) where it exists.
- It does NOT implement search logic. That is vercel-labs/skills' job.

## History

Authored 2026-04-09 after decision gad-85 adopted vercel-labs/skills as GAD's canonical user-facing installer. Scoped per decision gad-83 to "installed skills + pointer to trusted external sources." Part of the fundamental triumvirate per gad-73. Depends on vercel-labs/skills being installed globally via `npm i -g skills` or used via `npx skills` (recommended).

**Current state:** experimental. No evaluation harness has been run against it. Test cases that would go in `evals/evals.json` once authored: (1) "I need to do something nobody else has done, where do I start?" → should return zero matches and suggest `create-skill`, (2) "I need to debug a failing kaplay scene" → should return `debug` + `find-sprites` + possibly `map-codebase` as the most relevant local skills, (3) "My teammate mentioned skill-creator from anthropic" → should suggest `npx skills add anthropics/skills --skill skill-creator`.
