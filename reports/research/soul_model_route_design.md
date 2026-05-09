# Soul / Model / Route Design

**Date:** 2026-05-09
**Owner:** Gilgamesh of Uruk (operator direction 2026-05-09)
**Decision refs:** souls_houses_factions_framework.md (slm-learning-193 proposed), GLOBAL-D-301 (apps/desktop = Kael)
**Companion:** `slm_learning/schemas/soul_route.schema.json`, `slm_learning/data/registry/soul_routes.toml`

---

## 1. Bottom line

Soul routes decouple identity from compute: the narrative system owns WHO a soul is (personality, voice, in-world facts) while the route table owns WHICH MODEL serves it today, allowing the serving model to upgrade — from Anthropic Sonnet to a gad-owned adapter — without touching the narrative. This is the infrastructure that makes "competing with frontier labs by training our own progressively-better base" operationally tractable: every soul starts on a rented API and graduates to owned compute as its house produces canonical adapters.

---

## 2. Architecture

Two layers exist already. A third is new.

```
┌─────────────────────────────────────────────────────────┐
│  gad narrative (EXISTING)                               │
│  souls = personality / voice / in-world facts           │
│  gad narrative enter <projectid>                        │
│  narrative/souls/<soul>.md  ←── prompt prelude          │
└────────────────────┬────────────────────────────────────┘
                     │ soul_id
┌────────────────────▼────────────────────────────────────┐
│  soul routes (NEW — soul_routes.toml / schema)          │
│  routes = base_model + adapter_stack + endpoint         │
│  evolves as gad-owned adapters graduate                 │
│  routing_policy.task_shapes → per-call dispatch         │
└────────────────────┬────────────────────────────────────┘
                     │ resolve: base_model + adapter_stack + endpoint
┌────────────────────▼────────────────────────────────────┐
│  inference call                                         │
│  1. load soul narrative → system prompt prelude         │
│  2. apply adapter_stack in order (vLLM LoRA stack)      │
│  3. fire request at endpoint.url with endpoint.auth_ref │
│  4. record cost/latency to .planning/.gad-log/*.jsonl   │
└─────────────────────────────────────────────────────────┘
```

The key insight is that the adapter stack travels with the soul, not the project. When Kael is added to a new project (`project_scope` array edit), his trained Kael-house adapters come along automatically. The project has no opinion on which model serves Kael — that is the route table's job.

---

## 3. Current routes + graduation gates

| Soul | Today's route | Intended future route | Graduation gate |
|---|---|---|---|
| **Kael of Tarro** | `anthropic / claude-sonnet-4-6` (API) | `modal / qwen2.5-coder-7b-instruct` + `lora-kael-1p5b-v1` (self-hosted) | Kael-house trajectory composite > 0.601 AND human_review >= 0.5 on escape-the-dungeon eval (souls_houses_factions_framework.md) |
| **Gilgamesh of Uruk** | `anthropic / claude-opus-4-7` (API) | TBD — Gilgamesh-house (GAD-strategy faction) needs eval rubric before gate is definable | No gate defined yet; strategy tasks lack the pass@1 clarity of code evals |
| **Dr. Stein** | `modal / qwen2.5-coder-7b-instruct` + `lora-1p5b-hard-retain` (endpoint GAP: not deployed) | Same base, upgrade to 7B rung when scaling ladder fires | 7B eval: HE >= 86.8 AND MBPP >= 84.3 (scaling_ladder_gates.json knee criterion) |

All three have `evolution_state.current_level` set in soul_routes.toml. Dr. Stein is at level 1 (canonical adapter exists, endpoint pending); Kael and Gilgamesh are at level 0 (prompt-only).

---

## 4. Standard soul per GAD project

The proposed standard for new project initialization:

- `gad projects init` drops a default soul-routes stub into `data/registry/soul_routes.toml` pointing at the project's primary soul (from gad-config.toml `[[narrative.roots]]`) with a starter route of `anthropic / claude-sonnet-4-6`.
- Operator swaps the route via `gad souls route set` when a gad-owned adapter qualifies.
- Multiple souls per project are supported: `project_scope` is an array on the soul, not a 1:1 mapping from project. A project that needs both a planner (Gilgamesh) and a coder (Kael) just has two souls in its scope — no duplication of route config.

**CLI surface to implement (next phase — do not implement in this turn):**

```
gad souls list [--projectid <id>] [--json]
  → table: soul_id, soul_name, base_model, adapter_count, evolution_level, endpoint_kind

gad souls show <soul_id> [--json]
  → full route record

gad souls add <soul_id> --name <name> --project <id>
  → registers new soul with starter route (anthropic sonnet default)

gad souls route set <soul_id> --base-provider <p> --base-model <m> --endpoint-url <url> [--auth-ref <var>]
  → patches base_model + endpoint in place; logs change to gad state log

gad souls route show <soul_id>
  → current route summary: base + adapter stack + endpoint + cost/latency policy

gad souls promote <soul_id> --adapter <adapter_id> --evidence-eval <eval_id> [--decision-ref <ref>]
  → appends to adapter_stack, bumps evolution_state.current_level, timestamps promotion_history
```

---

## 5. Cross-project transfer

Transfer is a metadata edit. Steps:

1. Add the target project ID to `project_scope` array on the soul's route record.
2. If the target project has a different active context (e.g. a different `gad-config.toml` root), the narrative system's `gad narrative enter` still works because the soul slug is portable.
3. The adapter stack is unchanged — the soul carries its trained personality and all canonical adapters to the new project. No adapter re-training is required unless the new project has unique pressure profiles that diverge from the existing adapter's training data.

This is the mechanism that allows Kael to serve both `global` (apps/desktop chat shell) and future projects like a customer-facing product without duplicating the Kael-house training pipeline.

---

## 6. Evolution mechanics

`evolution_state.current_level` mirrors the project-level GAD evolution system but is per-soul. The progression:

```
Level 0  prompt-only         base_model = rented API, adapter_stack = []
Level 1  first adapter       canonical adapter from consolidation run, endpoint may still be gap
Level 2  served adapter      endpoint live, adapter_stack[0].status = canonical, cost/latency tracked
Level N  multi-adapter stack  stacked SFT + DPO or domain adapters, all canonical
```

Each promotion requires an `evidence_eval_id` (a consolidation run ID from `schemas/consolidation_run.schema.json`) and a `decision_ref`. This mirrors the existing `scaling_ladder_gates.json` pattern but scoped to the soul rather than the model family.

The promotion history is append-only — no entries are deleted. This gives the training data curator a full audit trail of which adapter version was serving which soul at what time, which is essential for the feedback loop that generates the next delta packet generation.

---

## 7. Open questions for operator decision

**Q1: Merge or subtype `customer_soul_adapter.schema.json`?**
`customer_soul_adapter.schema.json` (draft-07) has `adapter_id`, `tenant_id`, `base_model` (string), `lora_path`, `skills`, `memory_roots`. It is a flat stub. Recommendation: make `customer_private` license_class souls a validated subtype of `soul_route` — add `tenant_id` and `memory_roots` as optional extended fields in `soul_route.schema.json`, then deprecate the standalone schema. This avoids two sources of truth for the same concept.

**Q2: Where does endpoint/auth secret live?**
Three candidates:
- `gad settings` (local env store) — simple, already exists, no extra infra
- BYOK encrypted env (`wire-byok-encrypted-env` skill) — appropriate when secrets are per-customer or multi-tenant
- Separate vault (HashiCorp / AWS Secrets Manager) — overkill until multi-tenant serving goes live

Today: `gad settings` (auth_ref points to env var name). BYOK layer when customer-private souls are in scope.

**Q3: Multi-soul-per-call composition?**
Example: Gilgamesh sets strategy context + Kael executes the tool call within a single request chain. Two options:
- Soul-per-turn: each turn in the conversation resolves a single soul. Simpler; works with `useLocalRuntime` today.
- Tandem souls: a meta-call assembles system prompts from two soul preludes before firing the underlying model. More expensive; useful for cross-cutting handoffs where the planner and executor are different specialists.

Recommendation: start with soul-per-turn. Tandem is a routing_policy extension (`"compose_with": ["gilgamesh-of-uruk"]`) that can be added without schema breakage.

---

## Audit summary: wired vs missing

| Component | Status |
|---|---|
| `gad narrative list/enter` | Wired — 3 souls active (gilgamesh, kael, dr-stein) |
| `SOUL.md` pointer at repo root | Wired |
| Soul route schema | **New — this doc** |
| Soul route registry (TOML) | **New — this doc** |
| `gad souls` CLI subcommand | **Not implemented** — sketched above |
| `model_family_registry.schema.json` | Exists (JSON Schema 2020-12, draft-compliant) |
| `customer_soul_adapter.schema.json` | Exists (draft-07 stub) — recommend merge into soul_route subtype |
| `tenant_model_route.schema.json` | Exists (draft-07 stub) — overlaps routing_policy; recommend deprecate in favor of soul_route.routing_policy |
| Dr. Stein endpoint (Modal vLLM) | **GAP** — adapter canonical, serve config not deployed |
| Kael-house dataset capture pipeline | **GAP** — no training data yet; adapter_stack = [] |
| Gilgamesh-house eval rubric | **GAP** — strategy tasks lack pass@1 clarity |
