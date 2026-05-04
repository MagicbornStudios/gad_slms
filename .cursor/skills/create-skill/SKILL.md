---
name: create-skill
description: >-
  Capture a reusable pattern, recipe, or failure-mode fix as a skill document so future
  agents (including you after a context reset) can apply it without rediscovering it. Use
  this skill whenever you solve a non-obvious problem, discover a working pattern after
  two or more failed attempts, hit a bug whose fix isn't self-evident from the code, or
  finish a piece of work that future runs will likely repeat. Write the skill the moment
  you learn the lesson — not at the end. In bare/emergent eval conditions this is the
  primary mechanism for agent-authored methodology. The agent IS the workflow author, and
  skills are how that authorship persists.
lane: meta
type: meta-framework
---

# create-skill

A skill is a short, concrete methodology document. It captures "when you hit X, do Y,
because Z." Skills are the durable memory of an agent that has no other planning
framework — write them as soon as you learn something worth keeping, not at the end of
a session.

## When to write a skill

Write a skill when ANY of these are true:

- You solved a problem that took more than one attempt.
- You found a pattern that worked where a more obvious one did not.
- You hit a bug whose fix is not self-evident from reading the fixed code.
- You made a design decision that a later agent could reasonably question.
- You built a reusable primitive (scene transition, state composition, loader, etc.).

Do NOT write a skill for:

- Things any agent would already know (e.g. "use const not var").
- One-off fixes specific to a single file that nobody will touch again.
- Speculation about patterns you haven't actually used.

## Quality bar

Skills are compartmentalized systems, not stored answers. See
`references/skill-authoring-patterns.md` (§ Compartmentalized-system-as-skill) for the
full pattern and the proto-skill promotion checklist. The canonical shape reference is
`skills/gad-visual-context-system/SKILL.md`.

Short version: prefer a small, falsifiable requirements contract + a named UX/behavior
pattern + host-agnostic rollout. Skills that can't meet this bar are still useful as
captured answers — just don't try to universalize them.

## Where skills live

```
game/.planning/skills/<kebab-name>.md
```

One skill per file. Kebab-case filename matching the skill's topic.

## YAML frontmatter format (critical)

Every skill starts with a YAML frontmatter block (`---` delimiters) containing `name`
and `description` fields. The skill loader parses these strictly with js-yaml:

- **Descriptions with embedded colons break parsing.** Always use the folded block
  scalar form (`>-`) for descriptions:

  ```yaml
  ---
  name: my-skill
  description: >-
    First paragraph. Colons inside the prose are safe: they don't get parsed as YAML
    keys because the scalar is treated as a single opaque string.
  ---
  ```

- The `>-` is `>` (folded, lines join with spaces) plus `-` (strip trailing newline).
- Indentation matters — the body of the folded scalar must be indented more than
  the `description:` key (two-space convention).

**Test your frontmatter** before shipping:

```sh
node -e "console.log(require('js-yaml').load(require('fs').readFileSync('SKILL.md','utf8').split('---')[1]))"
```

Or let `install.js` do it — it validates every SKILL.md during install and warns on
the exact line and column of any failure.

## Skill structure

Every skill follows the same shape. Keep it short — a skill longer than one screen
is usually two skills. Full shape contract: `references/skill-shape.md`.

```markdown
# <Skill name — imperative or noun phrase>

## When to use
<1-3 bullets describing the trigger>

## The pattern
<The concrete recipe. Code snippet preferred over prose.>

## Why
<One paragraph. The reason this works, or the reason the obvious alternative fails.>

## Failure modes
<Bullets. What goes wrong if you do this slightly wrong. How to recognize it.>

## Related
<Other skills this depends on or supersedes, if any.>
```

## Writing rules

1. **Lead with the trigger.** The "When to use" section must let a future agent decide
   in 5 seconds whether to keep reading.
2. **Show working code, not pseudocode.** Paste the shape that actually worked.
3. **Explain the failure you avoided.** "Why" is the most load-bearing section.
4. **Write it immediately.** If you defer to "the end of the phase," you will forget
   the specific error message and the alternative you tried first.
5. **Update, don't duplicate.** Check existing `.planning/skills/` before creating.
   Update and sharpen rather than adding a near-duplicate.
6. **Delete wrong skills.** A stale skill is worse than no skill — it actively misleads.

## Trace marker contract

When running inside an eval with GAD trace hooks installed, write the skill id to
`.planning/.trace-active-skill` at start and clear it at end. See
`references/skill-authoring-patterns.md` (§ Trace marker contract) for the full
protocol including nested-skill lineage.

## Eval conditions

For `emergent` and `bare` eval condition behaviors, see
`references/skill-authoring-patterns.md` (§ Eval conditions).

## Confirm capture

After writing a skill, log the capture in your working notes:

```
Skill captured: <name>
Trigger: <one-line trigger>
File: game/.planning/skills/<name>.md
```

Then continue with the work that prompted the skill. Skill capture should take under
two minutes — if it takes longer, you are probably writing a design doc, not a skill.
