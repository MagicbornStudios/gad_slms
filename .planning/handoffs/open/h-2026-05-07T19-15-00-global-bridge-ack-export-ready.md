---
id: h-2026-05-07T19-15-00-global-bridge-ack-export-ready
projectid: slm-learning
phase: 04
task_id: SL-T-04-export-ack
created_at: 2026-05-07T19:15:00.000Z
created_by: claude-code-global-instance
claimed_by:
claimed_at:
completed_at:
priority: high
estimated_context: bounded
risk: safe
time: quick
surface: cross-project
runtime_preference: claude-code
---

# Closeout — fresh telemetry export ready (handoffs adapter included)

Acks "gad-monorepo Claude needs to run gad telemetry export with the
new handoffs adapter so the planning specialist gets >98 pairs."

## Done

```
$ gad telemetry export \
  --to ../slm_learning/data/raw/2026-05-07 \
  --since 2026-05-04T00:00:00Z \
  --root-dir C:/Users/benja/Documents/custom_portfolio
```

Output: `data/raw/2026-05-07/{events.jsonl, MANIFEST.json}`.

### Numbers — exceeds the >98 pairs target

**215,782 envelopes** total (was 119,819 before the new adapter).

| Adapter | Envelopes |
|---|---|
| gad-log | 35,919 (now picks up *-routing.jsonl + *-skill-loads.jsonl too) |
| trace-events | 16,937 |
| worker-log | 160,290 |
| prompt-files | 2,347 |
| **handoffs ✨ NEW** | **289** |

### Role histogram

```
meta=118975  prompt=2520  reasoning=88087  response=4432
tool_call=884  tool_result=884
```

### Content_type histogram

```
planning=163015  meta=52399  code=349  site=12  narrative=5  eval=2
```

### Specifically for the planning specialist

The **289 handoff envelopes** break down as:
- ~196 closed-bucket handoffs → emit a `role=prompt` (the body) AND a
  linked `role=response` (the closeout) via `parent_id` join
- ~93 open/claimed-bucket handoffs → emit only `role=prompt`

That's ~196 prompt→response training pairs from handoffs alone.
Filter the events.jsonl for `(content.kind == 'handoff_prompt' AND
parent_id IS NOT NULL)` joined to their closeouts to get the gold
pairs. Easily >98.

Bonus: phase 145.5 adapters E (errors-and-attempts: 97 envelopes) +
F (decisions: 325 envelopes) + H (tasks-and-roadmap: 1322 envelopes)
are also live in this export — all GAD-domain-specific structured
training material the planning specialist will recognize.

## SHA256 + manifest

```
data_sha256:     aec465968724e39effe99d78d1830834eedfe7ba4b663558da9cd0ea27e79652
data_bytes:      see MANIFEST.json
schema_v:        1
redacted:        true   ← phase 145.5-06 redaction default ON
source_commits:
  monorepo: 28c9baa0
  gad:      28c9baa0 (NOTE — was 5f61a1a6 at start of export)
```

Pull the events.jsonl from `data/raw/2026-05-07/` and feed your
ingest pipeline. Same path operator's nightly cron should hit
(eventually phase 147 daemon automates).

## Side note — framework site fixed

You may have seen the framework site (vendor/get-anything-done/site
deployed at framework.magicbornstudios.com) was failing with
`Module not found: @/data/media.json`. Fixed in submodule commit
`28c9baa0` — file was gitignored as part of the data/* generated
output rule, but `media.json` is static config not generated.
Tracking it now via gitignore exception.

## Next pull

When you want fresh data:
```sh
gad telemetry export --to ../slm_learning/data/raw/$(date +%Y-%m-%d) --since <iso>
```

I run this when you ask. Phase 147 daemon (continuous-delta-training-
loop) automates it on a 30m interval — gated on operator approval to
spawn.

## You can also pull yourself

`gad telemetry export` runs from any cwd that has `gad-config.toml`
referencing both projects as planning roots. From your slm-learning
CWD it would still see the gad-monorepo's adapters because gad
walks gad-config.toml. Easier to run from gad-monorepo though.

Co-Authored-By: claude-code-global-instance
