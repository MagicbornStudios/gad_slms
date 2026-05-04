---
name: merge-skill
status: experimental
origin: human-authored
description: >-
  Fuse two or more existing skills into a single tailored skill. Use when you
  discover overlapping skills in the catalog (same trigger keywords, same
  target workflow, same failure modes being addressed) or when you want to
  take a fundamental skill like scientific-method or debug and attune it to
  a specific project domain (e.g. merging scientific-method into a kaplay
  rune-spellcrafting workflow produces a scientific-method-for-kaplay-forge
  variant). Merging is the preferred response to skill collision — do not
  let duplicate skills accumulate in the catalog. Merge them, deprecate the
  originals in CHANGELOG, and update any inheriting runs. Per decision
  gad-73 this is one of the three fundamental skills (find-skills +
  merge-skill + create-skill) that together enable the emergent-evolution
  hypothesis to be tested in practice.
lane: meta
type: meta-framework
---

# merge-skill

**Experimental — awaiting evaluation harness per decision gad-86.**

Merging is what stops the skill catalog from drowning in near-duplicates. The user's ChatGPT analysis (captured as decision gad-81) names skill collision as the primary failure mode of large skill libraries: two skills with overlapping descriptions produce ambiguous routing, the agent picks wrong or thrashes between them, context budget is wasted on both. Merging is the fix.

## When to merge

Merge when any of these is true:

- **Description overlap**: two skills trigger on nearly the same keywords or use cases. If a new user read both descriptions they could not tell which to use.
- **Functional overlap**: both skills produce similar outputs from similar inputs, with only minor implementation differences. The differences are not worth two files.
- **Foundational attunement**: you want to take a generic skill (e.g. `debug`) and produce a project-tailored variant (e.g. `debug-for-kaplay-rune-forge`). The original stays, the merged variant is new.
- **Experimental convergence**: two experimental skills (per gad-86) addressed the same problem from different angles during different sessions. Their evaluations show similar effectiveness. Merge them into a canonical version.

Do NOT merge when:

- The two skills intentionally handle different edge cases. A skill for "greenfield creation" and a skill for "brownfield refactor" should stay separate even though they sound related.
- One is canonical (has passing evaluations per gad-86) and the other is experimental. The canonical one wins — deprecate the experimental as superseded rather than merging.
- They belong to different categories per Anthropic's three-category taxonomy (doc-creation / workflow-automation / mcp-enhancement from gad-70). Cross-category merges usually produce muddled skills.

## Procedure

### Step 1 — Identify the merge

Detect the overlap. Two signals:

```sh
# Catalog-based: ask find-skills for similar skills
gad skill find "<keywords from the overlap>"

# Structural-based: read both SKILL.md frontmatters
cat skills/<skill-a>/SKILL.md
cat skills/<skill-b>/SKILL.md
```

Write down the answer to this question for yourself: **"What can each of these skills do that the other cannot?"** If the answer is "nothing," they are merge candidates. If there is a real distinction, document it as a comment on both and do NOT merge.

### Step 1b — Consult agentskills.io guidance

Before drafting the merge, check the agentskills.io standard (https://agentskills.io/home) for professional guidance on skill structure, naming, and interoperability. The Anthropic skills guide (resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf, decision gad-70) is also canonical reference. Use these as the quality bar — the merged skill should meet or exceed the standards described in both documents.

### Step 2 — Draft the merged skill

Create a new SKILL.md at `skills/<merged-name>/SKILL.md`. The merged name should be:

- **Shorter than either input** when possible (a merge signals simplification)
- **More specific** when the merge is foundational-into-project (e.g. `debug` + kaplay context → `kaplay-debug`)
- **Never** use `merged-` or `combined-` as a prefix — those leak implementation detail

The merged skill's frontmatter:

```yaml
---
name: <merged-name>
status: experimental
origin: human-authored   # or "emergent" if you are an agent without explicit user request
authored-by: <user or agent>
authored-on: <ISO date>
description: >-
  <compose a new description that unifies the two inputs. Name the trigger
  keywords from both. Name the failure modes both addressed. Be more
  specific than either original to avoid re-introducing overlap.>
supersedes: [<skill-a>, <skill-b>]
---
```

The `supersedes` array is load-bearing — it lets `find-skills` skip the inputs in favor of the merge, and it lets the prebuild mark the originals as deprecated.

The body of the merged SKILL.md should:

1. State the merged purpose in one paragraph.
2. Have a "When to use" section that unifies the trigger conditions from both inputs without weakening either.
3. Walk through the procedure end-to-end, ideally as a single coherent workflow rather than two stitched procedures.
4. Cite the sources (both inputs) in a "History" section at the bottom. This preserves attribution.

### Step 3 — Deprecate the originals

For each input skill, add a frontmatter flag:

```yaml
---
name: <original-name>
status: deprecated
superseded-by: <merged-name>
deprecated-on: <ISO date>
---
```

Do NOT delete the original SKILL.md files. They are historical artifacts — future sessions looking at the lineage need to see what existed before. The prebuild filters deprecated skills out of the default catalog view but keeps them in the `all skills` filter.

### Step 4 — Update CHANGELOG

Append an entry to `skills/CHANGELOG.md` (create the file if it does not exist):

```markdown
## <YYYY-MM-DD> — merge: <merged-name>

**Merged:** `<skill-a>` + `<skill-b>` → `<merged-name>`
**Rationale:** <one sentence explaining the overlap>
**Inherited by:** <list of eval projects or runs that inherited either input, if any>
**Verification:** <pending evaluation harness per gad-87, or: "passed with delta.pass_rate = X">
```

The CHANGELOG is how future agent sessions see that skills were merged without spelunking git history.

### Step 5 — Run the evaluation harness (when it exists)

Once the `gad eval skill <name>` harness lands (tracked as a new task), run it against the merged skill:

```sh
gad eval skill <merged-name>
```

The harness reads the merged skill's `evals/evals.json`, runs with_skill vs without_skill in clean subagent contexts, and emits `benchmark.json`. If the merged skill's `delta.pass_rate > 0`, it graduates from experimental to canonical per gad-86.

If the merged skill UNDERPERFORMS the originals (negative delta), the merge was a mistake. Revert:

1. Flip the merged skill's status back to `status: experimental` or delete it.
2. Unflag both inputs (remove `superseded-by`).
3. Document the failed merge attempt in CHANGELOG with lessons.

### Step 6 — Notify inheriting runs

If either input skill was inherited by any eval project under `evals/<project>/template/skills/`, update those templates to inherit the merged skill instead. The prebuild's `SKILL_INHERITANCE` map will reflect the change on the next build and the site's /skills page will show the new lineage.

## Frontmatter discipline — colons in descriptions

This is the trap that burned multiple session-authored skills before gad-35. Never put an unquoted colon in a description:

```yaml
# ❌ BROKEN — js-yaml parses "when:" as a key separator
description: Use when: the user asks about kaplay runes

# ✓ FIXED — folded block scalar treats the body as opaque
description: >-
  Use when the user asks about kaplay runes. Any colon inside is safe because
  this is a folded block scalar.
```

Always use `>-` (folded block scalar, chomp-final-newline). Test your merged skill's frontmatter with `node -e "require('js-yaml').load(require('fs').readFileSync(process.argv[1], 'utf8').match(/^---\n([\s\S]*?)\n---/)[1])" skills/<name>/SKILL.md` before committing.

## Anti-patterns

- **Merging three or more skills at once** — too many moving parts, hard to grade. Merge pairwise.
- **Merging across categories** (doc-creation + workflow-automation). The merged skill ends up muddled. Keep them separate.
- **Merging canonical skills together** — canonical skills already survived the evaluation harness. Merging them is a regression unless the merge itself is evaluated and beats both.
- **Using merge-skill to "clean up" a catalog without evidence** — merge because overlap is measured (description similarity score, failed routing in practice), not because you think the names look similar.
- **Forgetting `supersedes:` in the frontmatter** — without it, `find-skills` still surfaces the deprecated inputs and the overlap problem persists.

## History

This skill was authored on 2026-04-09 after decision gad-73 named the fundamental triumvirate (find-skills + merge-skill + create-skill). It is the merging half of the gad-68 emergent-evolution hypothesis: the claim that skills evolve by merging fundamentals into project-tailored variants. Until this skill exists and has a working evaluation harness, gad-68 has no concrete mechanism to test.

**Current state:** experimental. No evaluation harness has been run against it. Test cases and an `evals/evals.json` are the next authoring step. Once the `gad eval skill` CLI lands (gad-87), run this skill through it and graduate it to canonical if it passes.
