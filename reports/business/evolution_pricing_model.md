# Evolution pricing model

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Decision refs:** slm-learning-218 (paid evolutions subsidize cheap
daily inference), slm-learning-219 (customer souls = adapters + memory
+ skills + evals, not separate full models), slm-learning-221 (shared
improvements require explicit customer data policy), slm-learning-097
(two-shot $50 discipline), slm-learning-100 (Delta Graph schema),
slm-learning-103 (compare-and-compete discipline), slm-learning-197
(teacher policy).
**Companion artifacts:** `reports/business/hosting_cost_strategy.md`,
`reports/research/shared_base_private_adapter_architecture.md`,
`schemas/evolution_job.schema.json`,
`schemas/customer_soul_adapter.schema.json`,
`benchmarks/cost_per_success_by_tenant.yaml`.

---

## 1. Why pricing tiers exist

The hosting strategy says: cheap daily inference for everyone,
expensive evolution jobs for power users, and the evolution surplus
funds the shared infra. Tiers operationalize that.

The four tiers below differ along five axes:

| Axis | Why it matters |
|---|---|
| Shared vs private model access | Bigger tier = own adapter + memory |
| Evolution credits / cycle cost | Bigger tier = more (or unlimited) evolution cycles |
| Inference layer ceiling | Bigger tier = Layer C dedicated allowed |
| Eval surface | Bigger tier = custom owned-domain evals (Charter Row 7) |
| SLA + support | Bigger tier = dedicated inference, priority queue |

---

## 2. The four tiers

| Tier | Indicative monthly price | What customer pays for | Inference layer | Evolution cadence |
|---|---|---|---|---|
| **Starter** | $0–$29 | shared models, no private evolution | Layer A only | none |
| **Creator** | $49–$199 | small monthly evolution credits, lightweight project soul | Layer A + B (multi-LoRA) | 1 small evolution / month |
| **Studio** | $499–$1,999 + per-evolution | dedicated project soul adapter, periodic evolutions, owned-domain evals | Layer B with reserved capacity, optional Layer C | $500–$5,000+ per evolution cycle, on-demand |
| **Enterprise / Game Studio** | $2,500+ base + custom | private adapters, custom evals, dedicated inference, stronger SLAs, data-policy negotiation | Layer C dedicated | unlimited / reserved compute |

Per-evolution price (Studio) scales with:

- data volume (rows of customer trace ingested)
- private-vs-shared training mode (slm-learning-221)
- eval complexity (frontier judge panel? owned-domain? trajectory eval?)
- artifact generation (game / music / landing / marketing per
  research track F)
- dedicated inference needs (does the resulting adapter need
  Layer C provisioning?)

---

## 3. What each tier funds

This is the unit economics, not the marketing copy.

### Starter

| Item | Cost class |
|---|---|
| Shared base inference | Layer A token spend (Together / OpenRouter) |
| Shared GAD skill adapters | amortized over all tenants |
| Vertical adapters (game / marketing / code / writing) | amortized |
| Router + gateway | shared infra |

**Margin lever:** sheer scale. Starter is a loss-leader-acceptable
tier — the goal is route volume that powers the comparator row and
that funnels users into Creator.

**Funded by:** Studio + Enterprise evolution surplus.

### Creator

| Item | Cost class |
|---|---|
| Everything Starter has | shared |
| Lightweight project soul (small LoRA on shared base) | one-time per ingest |
| 1 small evolution / month | covers ~$5–$20 of evolution compute |
| Usage dashboard | shared infra |

**Margin lever:** evolution credit underutilization. Most Creator
users will not consume all credits; that delta is margin.

### Studio

| Item | Cost class |
|---|---|
| Dedicated project soul adapter | private LoRA, retain bank, eval suite |
| Periodic evolutions (paid per cycle) | $500–$5,000+ each |
| Owned-domain evals (custom eval rubric) | Charter Row 7 row built per tenant |
| Optional Layer C dedicated inference | priced through |

**Margin lever:** per-evolution markup. Each evolution job records
its true compute cost in `schemas/evolution_job.schema.json` and
the price charged. Margin = `revenue_usd − cost_breakdown.total`.

### Enterprise / Game Studio

| Item | Cost class |
|---|---|
| Private adapters with ownership terms | legal-reviewed |
| Custom evals (e.g. game-specific trajectory bank) | bespoke |
| Dedicated inference (Layer C reserved) | passthrough + margin |
| Stronger SLAs, support, data-policy negotiation | services |

**Margin lever:** reserved capacity + services. Layer C cost is
passed through plus a margin; services are billed separately.

---

## 4. The "Project Soul Evolution" product (Phase 2 anchor)

Operator direction names this as the first consumer product. Spec:

| Step | Deliverable |
|---|---|
| 1. Initial project ingest | trace import, repo scan, soul prompt draft |
| 2. Soul profile | `customer_soul_adapter` record (see schema) with `consent_mode`, `tenant_isolation`, `data_deletion_policy` set |
| 3. Style/behavior adapter | LoRA trained on tenant traces; lineage stamped |
| 4. Eval report | HE / MBPP / owned-domain row, before/after |
| 5. Monthly evolution pass | `evolution_job` runs, regression journal updated, adapter version bumped |
| 6. Usage dashboard | cost per task, fallback rate, cache hit rate, adapter promotion rate |

Pricing on this product sits in the Creator–Studio band depending on
ingest volume.

---

## 5. Customer-data policy (slm-learning-221)

Every customer soul record MUST capture:

| Field | Why |
|---|---|
| Explicit consent to train on project data | legal + trust |
| Tenant isolation flag | enforces no cross-tenant leakage at training and serve time |
| Adapter ownership terms | who owns the LoRA on contract end |
| Data deletion policy | retention window, deletion SLA |
| Model export policy | can the customer take their adapter weights? |
| Whether evolution improves shared models | the consent option (private vs shared evolution) |
| Human review for sensitive outputs | game artifacts, generated marketing, etc. |

These are mandatory fields in `schemas/customer_soul_adapter.schema.json`.
A record missing any of them is REJECTED at promotion time.

### Two consent options

| Option | Customer cost | What we get | What customer gets |
|---|---|---|---|
| **Private evolution** | higher | only their adapter improves | full isolation; no signal to shared base |
| **Shared evolution** | lower (discounted) | anonymized / generalized deltas may improve shared models | cheaper price + benefit from collective improvements over time |

The discount on shared evolution is the funding mechanism for shared
base improvements — it explicitly trades a price cut for an
opt-in to contribute generalized signal.

---

## 6. Required metrics

Per operator direction, these metrics must exist for every tenant
and every route:

| Metric | Source | Decision |
|---|---|---|
| Cost per successful task | `benchmarks/cost_per_success_by_tenant.yaml` | slm-learning-218 |
| Cost per evolution | `evolution_job.cost_breakdown.total` | slm-learning-218 |
| Margin per evolution | `revenue_usd − cost_breakdown.total` | slm-learning-218 |
| Fallback rate | `tenant_model_route.fallback_policy` telemetry | slm-learning-218 |
| Cache hit rate | `tenant_model_route.caching` telemetry | slm-learning-218 |
| Adapter promotion rate | `evolution_job.outcome.promoted` over total runs | slm-learning-218 |
| Tenant GPU utilization | Layer C only | slm-learning-220 |
| Subscription dollars avoided | tenant KPI (vs hypothetical Claude Pro etc.) | slm-learning-218 |

---

## 7. Phase plan (operator direction, verbatim)

| Phase | Scope | Anchor |
|---|---|---|
| Phase 1 — Internal dogfood | GAD Gateway, cost-per-task tracking, easy-task routing to small models, open high-end Qwen / Claude as teacher/fallback only, project soul adapters trained from our own traces | this doc + hosting strategy |
| Phase 2 — First consumer product | "Project Soul Evolution" (steps 1–6 in §4) | this doc |
| Phase 3 — Studio tier | $500–$5,000+ per evolution cycle, dedicated project souls, owned-domain evals | this doc |

---

## 8. Anti-patterns

| Anti-pattern | Why no |
|---|---|
| Quoting a flat per-evolution price without ingest-volume tier | margin collapses on the first 100k-row repo |
| Letting a Studio tenant skip the consent fields | slm-learning-221 — non-negotiable |
| Promoting a customer soul adapter without an eval row that beats their bare baseline | slm-learning-103 compare-and-compete refusal |
| Funding shared-base improvements out of Starter revenue | unsustainable; Studio surplus funds shared base |
| Treating "shared evolution" as default-on | opt-in only; discount is the trade |

— Dr. Stein, evolution pricing model, 2026-05-08
