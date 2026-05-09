# Claude Design -> GAD Generation Pipeline

Locked: 2026-05-08. Decisions: `slm-learning-205` (design-handoff-as-trigger),
`slm-learning-208` (GAD Gateway HTTP surface), `slm-learning-218`
(evolution-job), `slm-learning-219` (per-tenant adapter routing),
`slm-learning-221` (private-vs-shared consent).

## 1. Goal

Treat Claude Design exports as **trigger payloads** for the GAD generation
engine. A designer hits "export" in Claude Design and a CI/CD-shaped pipeline
translates the resulting JSON bundle into framework-specific code that lands in
the customer's repo, fed by per-tenant adapters and gated by consent.

## 2. Pipeline

```
Claude Design
    |  (JSON / handoff bundle)
    v
File storage (GitHub repo `design/inputs/`, S3 bucket, etc.)
    |  (webhook | poller | git push)
    v
[GAD Agent Service]            <-- ingest_design_handoff.py
    |  reads + validates bundle
    |  routes by tenant_id + consent
    v
Claude-backed generator (API / MCP) + design_to_code.py
    |  emits theme + components + pages + MANIFEST.json
    v
Code written to repo (src/generated/, widgets/, etc.)
    |
    v
CI/CD deploy (next iteration)
```

## 3. Trigger modes

| Mode | Where it runs | v1? |
|---|---|---|
| **A. Webhook** (`POST /design-handoff`) | GAD Gateway HTTP surface (slm-learning-208) | stub only — schema + dispatcher land now, hosting follows once Gateway is up |
| **B. File watcher** | Poll `design/inputs/<bundle>.json` on a cron | implemented (file ingest path) |
| **C. CI on `git push`** | GitHub Action that runs `ingest_design_handoff.py` | trivially follows from B |

v1 ships the file-ingest path because it is the lowest-risk surface: nothing
bound to the network yet, and it doubles as the body of the eventual webhook
handler.

## 4. Schema

`schemas/design_handoff_bundle.schema.json` (draft-2020-12). Required top-level
fields: `bundle_id`, `exported_at`, `design_system_version`, `tokens`, `pages`,
`components`, `provenance`. Schema mirrors the conventions in
`teacher_policy.schema.json` and `delta_packet.schema.json`:

- `tokens` — flat name->value maps grouped by category (color / spacing /
  typography / radius / shadow / motion). Generators map these to CSS
  variables, Flutter `ThemeData`, etc.
- `pages` — routable pages. Each carries a `layout` component_id and
  `components_used[]` (component_id + props + slot).
- `components` — reusable units. Each carries `props_schema`, `structure`
  (nested element tree with `token_refs`), `states`, and `a11y`.
- `provenance` — `tenant_id` + `consent {private, shared}` per slm-learning-221.

`decision_refs` defaults to `[slm-learning-205, slm-learning-219,
slm-learning-221]`.

## 5. Generator plug-in architecture

`scripts/design/design_to_code.py` defines a `CodeGenerator` base class and a
`generators` registry keyed by `target_framework`. Adding a new framework:

1. Subclass `CodeGenerator`. Set `target_framework`, `component_ext`,
   `theme_filename`.
2. Implement `_emit_theme`, `_emit_component`, `_emit_page`, and `generate`.
   Reuse `_build_manifest` for the MANIFEST.
3. Register the instance in `generators[<name>] = MyGenerator()`.

Every generator emits the same shape:

```
out_dir/
  theme.<ext>
  components/<Name>.<ext>
  pages/<Name>.<ext>
  MANIFEST.json
```

`MANIFEST.json` records `bundle_id`, `design_system_version`,
`target_framework`, `tenant_id`, `consent`, `decision_refs`, and an entry per
file with its source `component_id` / `page_id`. This is the audit trail —
downstream evolution jobs and serving lanes consume it.

In v1 generators emit stubs with `TODO(claude-design-generator)` markers
where the real Claude-API call will land in v2.

## 6. Composition with GAD Gateway (slm-learning-208)

The Gateway exposes the customer-facing HTTP surface. Design ingest plugs in
as `POST /design-handoff` with the JSON bundle as request body. Internally the
Gateway calls the same `ingest()` function the CLI uses, so file-ingest and
webhook-ingest share validation + dispatch. Auth/quotas/rate-limits live at the
Gateway layer, not in this package.

## 7. Composition with evolution-job (slm-learning-218)

Design-to-code is a **Studio-tier evolution job** in the pricing model
(`reports/business/evolution_pricing_model.md`). Each ingest emits an evolution
record with `tenant_id`, `bundle_id`, generator outputs, cost, and a regression
hook (manifest diff vs the previous bundle's manifest tells us what changed).

## 8. Composition with customer_soul_adapter (slm-learning-219)

Generated code lands in the customer's repo, but the **router behavior** that
fetches/edits that code at inference time is governed by the customer soul
adapter. The 5-layer architecture
(`reports/research/shared_base_private_adapter_architecture.md`) places
design-to-code outputs at layer 3 (vertical adapter — game / marketing /
**code**). The customer soul adapter at layer 4 references these outputs via
`memory_roots`.

## 9. Composition with consent (slm-learning-221)

`provenance.consent.private = true` (the v1 default) means generated artifacts
+ traces stay tenant-scoped; the bundle does not feed shared retain-banks. If
`consent.shared = true`, sanitized structural patterns may be folded into a
shared design-pattern retain-bank for future generators. The dispatcher honors
the flag at routing time; the schema makes the decision explicit.

## 10. Roadmap

| Stage | Scope |
|---|---|
| **v1 (this session)** | File ingest + schema + stub generators + manifest contract. No network. No real Claude calls. |
| **v2** | Real Claude-API generation (replaces TODO markers). Webhook hosting inside GAD Gateway. Per-tenant adapter routing wired via `customer_soul_adapter.lora_path`. |
| **v3** | CI/CD deploy hook on successful generation. AB testing across generators (Claude Opus vs Qwen-32B vs in-house code-LoRA). Cost-per-success-by-tenant rollup feeding evolution pricing. |

## 11. Cost model

- File ingest itself is ~free (local validation + file writes).
- Real generation (v2) is teacher-token-bound. Stub estimate using
  `evolution_pricing_model.md`: small bundle (5 components, 2 pages) at Opus
  rates ~ $0.50-2.00 per generation pass; full design system (50 components,
  10 pages) ~ $5-15. Most evolutions repeat at the design-system-version
  cadence, not per-page-edit.
- Total `~$1-10 per design-to-code evolution cycle` for typical Studio-tier
  customers in early v2.
- Cache hits on unchanged components (manifest diff) drop this further; with
  a 70% unchanged rate the cycle is ~$0.30-3.

## 12. Future hooks

- **Generator AB testing** — register multiple generators per framework
  (`react-opus`, `react-qwen32b`, `react-inhouse-coder-lora`) and route a
  share of bundles to each. Score by downstream success metric (lint pass /
  visual diff vs design / human review).
- **Cost-per-success-by-tenant** — join `MANIFEST.json` outputs with the
  evolution-job ledger to attribute spend to tenants and feed the pricing
  model.
- **Multi-tenant routing at ingest** — Gateway selects which vertical
  adapter (game / marketing / code) owns the bundle based on
  `provenance.tenant_id` + a tenant->adapter map.

## 13. Files in this slice

- `schemas/design_handoff_bundle.schema.json`
- `scripts/design/__init__.py`
- `scripts/design/ingest_design_handoff.py`
- `scripts/design/design_to_code.py`
- `reports/research/claude_design_pipeline.md` (this doc)
