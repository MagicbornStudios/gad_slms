---
name: portfolio-sync
description: Keep the public-facing GAD site and generated publishing artifacts in sync with the framework as it evolves. Trigger this skill whenever an eval run finishes, a new finding is written, a skill or agent changes, requirements or decisions move, or planning/docs outputs need regeneration.
lane: prod
type: command-wrapper
---

# portfolio-sync

This skill is effectively the framework publishing sync. Despite the name, it is not just about a portfolio site. Use it for:

- the public GAD site under `site/`
- generated site catalogs and eval data
- downloadable templates and planning zips
- adjacent docs/publication outputs that should reflect the repo's current truth

The public surfaces are built directly from the repo filesystem. There is no CMS, no database, no API. The source of truth is the filesystem.

| What you changed | Where it lives | How the public surface picks it up |
| --- | --- | --- |
| New eval run | `evals/<project>/<version>/TRACE.json` | `build-site-data.mjs` -> `lib/eval-data.generated.ts` |
| New finding | `evals/FINDINGS-YYYY-MM-DD-slug.md` | `build-site-data.mjs` -> findings catalog and route |
| New skill | `skills/<name>/SKILL.md` | scanned into the skills catalog |
| New subagent | `agents/<name>.md` | scanned into the agents catalog |
| Generated compatibility command | `commands/gad/<name>.md` | scanned into the commands catalog |
| Planning state updates | `.planning/*.xml` | surfaced on `/planning` and related site views |
| Docs sink outputs | configured `docs_sink` path | produced by `gad docs compile` / docs compiler |

## When to trigger this skill

- After `gad eval preserve` completes a run and the run should appear publicly.
- After writing a new finding or changing an eval comparison surface.
- After changing skills, agents, commands, templates, or planning state that the site reflects.
- After compiling planning docs or regenerating publishable artifacts that should stay aligned with the repo truth.
- After any work where a visitor would otherwise see stale framework state.

## The sync procedure

1. Make sure the filesystem is the truth.
   Do not hand-edit generated files under `site/lib/*.generated.ts`, `site/public/downloads/`, or any generated docs sink.

2. Regenerate locally:

```sh
cd site
npm run prebuild
```

3. Build locally to verify:

```sh
npx next build
```

4. If playable builds changed, run:

```sh
npm run build:games
```

5. If planning docs must be published into a docs sink, run the docs compiler flow as part of the same publishing pass.

6. Commit the regenerated outputs with a task id or `chore(site):` style commit message.

## What not to do

- Do not hand-edit generated site or docs output.
- Do not hide bad eval results or process failures.
- Do not let public surfaces drift behind framework truth.
- Do not treat this as site-only if the real work is publishing generated docs or artifacts.

## Relationship to nearby skills

- `gad-docs-compile` compiles planning docs into a sink.
- `portfolio-sync` is the broader publication/presentation sync that makes sure the public-facing artifacts match the repo.
- `trace-analysis` inspects telemetry and reports how the framework was used; it does not publish anything by itself.

Treat `npm run prebuild && npx next build` as the public-surface equivalent of a verification step.
