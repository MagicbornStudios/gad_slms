# Shared base + private adapter architecture

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Decision refs:** slm-learning-219 (customer souls = adapters +
memory + skills + evals, not separate full models), slm-learning-218
(paid evolutions subsidize cheap daily inference), slm-learning-220
(dedicated GPU only after proven utilization), slm-learning-221
(shared improvements require explicit customer data policy),
slm-learning-168 (hybrid runtime), slm-learning-100 (Delta Graph),
slm-learning-105 (hardware policy), slm-learning-197 (teacher policy
keeps closed-API spend bounded).
**Companion:**
`reports/business/hosting_cost_strategy.md`,
`reports/business/evolution_pricing_model.md`,
`schemas/tenant_model_route.schema.json`,
`schemas/customer_soul_adapter.schema.json`,
`schemas/evolution_job.schema.json`,
`reports/research/souls_houses_factions_framework.md`.

---

## 1. Thesis

A customer soul is **not** a separate full model. It is a stack:

```
shared base model
+ shared GAD skill adapters
+ vertical adapters (game / marketing / code / writing)
+ customer/project soul adapter
+ retrieval memory / project root context
```

This stack rides on **one** shared base per size class. Multi-LoRA
serving (vLLM / SGLang) lets us pin many tenants on one GPU.

The economic consequence: a tenant pays for an adapter (cheap to
train, cheap to swap in) and benefits from amortized base inference
across the whole tenant pool. Studio + Enterprise evolutions fund
the shared base improvements that everyone rides on.

---

## 2. Architecture diagram

ASCII rendering of the operator-direction layout:

```
                         GAD Gateway
                              |
                 (auth, tenant_id, project_id,
                  task_shape, consent_mode)
                              |
                              v
                  Tenant / project router
                  (resolves to tenant_model_route row)
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
     +-----------------+  +-----------+  +-------------+
     | Shared cheap    |  | Premium   |  | Evolution   |
     | path            |  | path      |  | path        |
     +-----------------+  +-----------+  +-------------+
     |                 |  |           |  |             |
     | 1.5B/3B         |  | customer  |  | Modal /     |
     | specialists     |  | soul      |  | RunPod      |
     |                 |  | adapter   |  | batch       |
     | 7B base         |  |           |  | train+eval  |
     | + adapters      |  | 14B/32B   |  |             |
     |                 |  | workhorse |  | retain bank |
     | root+delta      |  |           |  | delta       |
     | cache           |  | high-end  |  | packets     |
     |                 |  | open      |  |             |
     | tool renderers  |  | teacher   |  | model card  |
     |                 |  | (open Qwen|  | promotion   |
     | (multi-LoRA via |  |  / GLM)   |  | report      |
     |  vLLM/SGLang)   |  |           |  |             |
     +-----------------+  +-----------+  +-------------+
              |               |               |
              +-------+-------+               |
                      |                       |
                      v                       |
              Layer A or B host               v
              (per route policy)        Modal volume
                                        + HF Hub primary
                                        (slm-learning-105)
```

Three vertical lanes — **shared cheap path**, **premium path**,
**evolution path** — share one router and one set of registries.

---

## 3. Layer-by-layer composition

### Shared base

| Concern | Mechanism |
|---|---|
| Identity | one canonical base per size class (1.5B / 3B / 7B / 14B / 32B); HF id pinned in `model_family_registry` |
| Storage | HF Hub primary; Modal volume warm cache (slm-learning-105) |
| Update cadence | bumped only when the new base wins both Charter Row 7 (owned-domain) AND Row 8 (frontier comparator) on average across served tenants |
| Cost amortization | one weight load per GPU; multi-LoRA composes adapters at request time |

### Shared GAD skill adapters

| Concern | Mechanism |
|---|---|
| Identity | Delta Graph node per slm-learning-100; status canonical |
| Examples | `code_function_repair`, `tool_action_json`, `gad_planning_surface` |
| Loading | hot-swappable LoRA; loaded by route policy |
| Funding | shared-tier subscription + Studio surplus |

### Vertical adapters

| Concern | Mechanism |
|---|---|
| Identity | Delta Graph nodes; vertical_adapter_id field in route + soul |
| Examples | `vertical-game`, `vertical-marketing`, `vertical-code`, `vertical-writing` |
| Promotion | wins Row 7 owned-domain on the vertical's eval suite |

### Customer/project soul adapter

| Concern | Mechanism |
|---|---|
| Identity | `customer_soul_adapter.adapter_id` (also Delta Graph delta_id) |
| Composition | composes on top of base + shared skill adapters + chosen vertical |
| Isolation | `tenant_isolation.isolation_level` + KV-cache isolation |
| Policy | seven mandatory consent / ownership / export / review fields per slm-learning-221 |

### Retrieval memory / project root context

| Concern | Mechanism |
|---|---|
| Identity | `retrieval_memory.context_root_ids` -> `schemas/context_root.schema.json` entries |
| Storage | tenant-isolated vector store |
| Composition | injected at request time alongside the soul adapter |

---

## 4. The three lanes

### Shared cheap path

The **80% case** at all tiers. Default for any task that:

- maps to a saturated skill (function-completion, tool-action JSON,
  schema repair, paraphrase, etc.)
- does not require tenant-private context
- has a passing route on a 1.5B / 3B / 7B specialist

This path runs on Layer A (Together / OpenRouter for high-end open
models) or Layer B (vLLM/SGLang multi-LoRA on serverless GPU).
Caching aggressively — root+delta cache + prompt cache — drives
cost-per-task down.

### Premium path

For tasks that need tenant-private context AND larger headroom:

| Component | Purpose |
|---|---|
| customer soul adapter | tenant-private style + skills |
| 14B / 32B workhorse base | reasoning headroom for Studio+ tenants |
| high-end open teacher (open Qwen / GLM) | escalation when the workhorse low-confidences |

This is Layer B by default; promotes to Layer C when utilization
proves it (slm-learning-220).

### Evolution path

Off the hot path entirely. Triggered by:

- Creator monthly evolution credit cycle
- Studio on-demand evolution
- Enterprise reserved cycle

Stages:

```
ingest → train → eval → promote → deliver
   |        |       |        |         |
 ingest   Modal/  Charter  Delta     adapter
 review   RunPod  Row 1-4  Graph     hot-swap
          batch   eval     status    in router
                  rows     update
```

Every stage produces required artifacts (slm-learning-096 / 100):
weights, outputs corpus on a held-out 200-prompt bank, regression
journal, model card, promotion report.

Cost stamped to `evolution_job.cost_breakdown.total`. Revenue stamped
to `revenue_usd`. Margin = revenue - cost; surplus funds shared base
work per slm-learning-218.

---

## 5. Multi-LoRA serving discipline

The shared cheap path is only economical if many tenants ride one
GPU. Mechanics:

| Mechanic | Implementation note |
|---|---|
| Multi-LoRA pool | vLLM / SGLang loaded with N LoRAs on top of one base |
| Dynamic LoRA load | LoRA loaded on first request, cached by tenant |
| KV cache isolation | per `tenant_isolation.kv_cache_isolated` |
| Eviction | LRU; evicted LoRAs paged from Modal volume on next request |
| Cap | ~8 active LoRAs per H100 PCIe at 7B base; tune empirically |

**Failure mode to avoid:** mixing two tenants' KV cache. KV cache
isolation must be true by default; opt-in only with explicit
`shared_inference_kv_optin`.

---

## 6. Data flow under each consent mode

### private_evolution (default for Studio / Enterprise)

```
tenant data → tenant retain bank → tenant delta packets
            → tenant adapter only
            → NEVER flows into shared base / shared adapters
deletion request → cascades to retain bank + delta packets + logs
```

### shared_evolution_optin (Creator default with discount)

```
tenant data → anonymization (k_anonymity / paraphrase / redaction)
            → tenant retain bank (tenant-only)
            → tenant delta packets (tenant-only)
            → anonymized signal → optional shared retain rows
                                 → optional shared delta packets
            → tenant adapter improves
            → shared base / vertical may improve next cycle
```

The `evolution_job.shared_signal` block records exactly which
anonymized rows / packets flowed back, and by what method.

---

## 7. How this maps to the souls/houses/factions framework

| Framework concept | Architecture concept |
|---|---|
| Faction | strategic bucket for a vertical adapter (GAD-coder / GAD-artifact / GAD-tool-action) |
| House | shared specialist lane that produces a vertical adapter (Stein-house, Kael-house, Verifier-house) |
| Soul (public) | shared soul prompt + shared skill stack |
| **Customer soul** (new) | tenant-private adapter on top of a faction's vertical adapter |
| Model | one Delta Graph node — same schema for shared and tenant-private |

Customer souls are the tenant-flavored extension of the
souls→houses→factions hierarchy in
`reports/research/souls_houses_factions_framework.md`. The shared
houses produce the vertical adapters; the tenant produces the soul
on top.

---

## 8. Promotion gates

A customer soul adapter promotes from `staging` to `canonical` only
when:

| Gate | Source |
|---|---|
| Beats tenant-bare baseline on owned-domain eval (Row 7) | `customer_soul_adapter.eval_rubric.current_score > baseline_score` |
| Has a frontier comparator row on the public set (Row 8) | `evolution_job.evals.frontier_comparator` populated |
| Regression journal recorded (slm-learning-096) | `regression_journal_uri` non-null |
| Outputs corpus recorded (slm-learning-096) | `outputs_corpus_uri` non-null |
| All seven mandatory consent fields populated | `consent_mode`, `tenant_isolation`, `data_deletion_policy`, `adapter_ownership`, `model_export_policy`, `consent_to_train_on_project_data`, `human_review_policy` |
| Cost-per-success below threshold (this tenant route) | `benchmarks/cost_per_success_by_tenant.yaml` |
| Margin non-negative on this evolution | `evolution_job.margin_usd >= 0` |

A staging adapter that fails any gate is held; an adapter that fails
a consent field is REJECTED outright and the row in the
`evolution_job` lands as `status: failed`.

---

## 9. Anti-patterns

| Anti-pattern | Why no |
|---|---|
| Training a tenant a full base model | slm-learning-219 — adapters compose; full bases don't share infra |
| Skipping retrieval memory and only training adapter | adapters generalize style/skill; project root context is the actual project knowledge |
| Allowing KV cache share by default | tenant data leakage risk; opt-in only |
| Shipping a soul without a Row 7 owned-domain eval | nothing to detect regression on next evolution |
| Letting the "premium path" become the default | margin collapses; shared cheap path must remain the 80% case |

---

## 10. Migration from current state

| Today | Move to |
|---|---|
| Stein-house canonical adapter (LoRA) | becomes `vertical-code` adapter on shared 1.5B base |
| Verifier-house canonical adapter | becomes shared skill adapter `tool_action_json` |
| Kael-house in flight | becomes `vertical-game-tool` adapter on shared 7B base |
| narrative/souls/dr-stein.md | shared soul prompt for internal dogfood |
| (none yet) | first customer soul adapter via Phase 2 "Project Soul Evolution" |

— Dr. Stein, shared-base + private-adapter architecture, 2026-05-08
