# Hosting cost strategy

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Decision refs:** slm-learning-218 (paid evolutions subsidize cheap
daily inference), slm-learning-220 (dedicated GPU only after proven
utilization; default is serverless/burst), slm-learning-105 (hardware
policy; >100MB to Modal volume), slm-learning-168 (hybrid runtime),
slm-learning-197 (teacher policy: Opus is the teacher; open Qwen is
labeler/comparator/inspector — keeps closed-API spend bounded).
**Companion artifacts:** `reports/business/evolution_pricing_model.md`,
`reports/research/shared_base_private_adapter_architecture.md`,
`schemas/tenant_model_route.schema.json`,
`benchmarks/cost_per_success_by_tenant.yaml`.

---

## 1. Operating thesis

> "Cheap daily inference for everyone, expensive 'evolution' jobs for
> power users/studios, and the surplus from evolutions subsidizes the
> shared model/router infrastructure." — operator direction, 2026-05-08.

The unit economics force three layers, in this order:

1. **Layer A — Serverless hosted APIs** for high-end open-weight
   models (Qwen, DeepSeek, Llama, etc.) and for closed teachers
   (Anthropic, OpenAI, Google) where we never want to own the GPU.
2. **Layer B — Serverless GPU / autoscale** (RunPod Serverless,
   Modal, Vast serverless) for custom LoRA / adapter serving and
   for evolution batch jobs.
3. **Layer C — Dedicated GPU** (RunPod active workers, Lambda,
   rented boxes) only after a tenant or shared route proves
   sustained utilization.

Default routing is **A then B**. C is earned, not assumed.

---

## 2. The three layers — when, why, how much

### Layer A — Serverless hosted APIs

**Best for:** getting started, variable traffic, no ops burden.
**Provider style:** Together AI, OpenRouter-style hosted APIs,
Anthropic / OpenAI / Google direct.

**Use cases:**

| Use case | Provider class | Pricing data point |
|---|---|---|
| Closed-API teacher (Opus 4.5 gold labels) | Anthropic direct | $5 / $25 per Mtok in/out |
| Closed-API premium teacher (Sonnet 4.6 fallback) | Anthropic direct | $3 / $15 per Mtok |
| Closed-API bulk labeler (Haiku 4.5) | Anthropic direct | $1 / $5 per Mtok |
| Open-weight high-end coder (Qwen3-Coder-Next) | Together AI | $0.50 / $1.20 per Mtok |
| Open-weight throughput model (Qwen3 235B A22B FP8) | Together AI | $0.20 / $0.60 per Mtok |
| Free-tier comparator row (Charter Row 8) | OpenRouter free | $0.00 (rate-limited) |

**Why default here first:**

- No idle cost. We pay per token.
- Provider amortizes GPU across all their tenants — strictly cheaper
  than us renting a GPU for an underused route.
- Lets us prove demand before committing to capacity.

**Hard cap (per slm-learning-220):** any single open-weight route on
Layer A that bills more than the equivalent dedicated GPU would
cost is escalation-eligible to Layer C — but only after 14 days of
sustained traffic, not on a single spike.

---

### Layer B — Serverless GPU / autoscale

**Best for:** custom adapters, bursty use, evolution jobs, anything
that needs **our own weights + LoRAs** loaded.

**Provider style:** RunPod Serverless, Modal, Vast serverless.

**Pricing reference (RunPod Serverless flex):**

| Hardware | $/sec flex | $/sec active worker (~25% disc.) | Indicative $/hr flex |
|---|---|---|---|
| L4 / A5000 / 3090 | $0.00019 | ~$0.00014 | $0.68 |
| A100 80GB | $0.00076 | ~$0.00057 | $2.74 |
| H100 Pro | $0.00116 | ~$0.00087 | $4.18 |

**Use cases:**

| Use case | Hardware class | Why this layer |
|---|---|---|
| Tenant-private adapter inference (1.5B–7B base + customer LoRA) | L4 / A5000 / 3090 | Cold-start tolerable for low-RPM tenants; per-second billing crushes idle cost |
| Burst code-completion peak | A100 80GB | Headroom for peak; falls back to A on cooldown |
| Evolution training job (LoRA / morphism / consolidation) | A100 80GB or H100 Pro | Wall-time priced; shutdown on completion |
| Eval / regression journal sweep | L4 fleet | Embarrassingly parallel; cheap GPUs win |

**Modal specifics:** Volume-backed cache for base weights + LoRAs
per slm-learning-105. Modal volume is the canonical store for
adapters >100MB. Cold-start cost amortized by warm-pool of base
weights.

**Hard cap:** evolution jobs MUST land cost in `evolution_job` record
(`schemas/evolution_job.schema.json`) so margin per evolution is
auditable per `evolution_pricing_model.md`.

---

### Layer C — Dedicated GPU

**Best for:** steady traffic, low-latency requirements, high-usage
customers (Studio / Enterprise tier).

**Provider style:** RunPod active workers, Lambda Labs, rented GPU
boxes, HuggingFace dedicated endpoints.

**Pricing reference:**

| Provider | Hardware | $/hr | $/month always-on (1 replica) |
|---|---|---|---|
| HF dedicated endpoints | small GPU | ~$0.50 | ~$365 |
| Lambda | A100 single GPU | ~$1.29 | ~$941 |
| Lambda | H100 single GPU | $3+ | ~$2,190+ |
| RunPod active worker A100 | A100 80GB | ~$2.05 (25% disc on $2.74) | ~$1,496 |

**Promotion criteria (slm-learning-220):** route promotes to Layer C
when ALL of:

1. 14-day sustained utilization > 50% of equivalent dedicated GPU.
2. Cost-per-successful-task under target threshold (see
   `benchmarks/cost_per_success_by_tenant.yaml`).
3. Tenant on Studio or Enterprise tier with dedicated-inference SLA
   in their pricing terms.

**Demotion criteria:** if 7-day utilization drops below 25%, route
demotes back to Layer B at the next billing cycle.

---

## 3. Order of adoption (operator direction)

| Step | Layer | Why now |
|---|---|---|
| 1 | A (hosted APIs) | Zero capex; teacher + comparator rows day one |
| 2 | B (RunPod / Modal) | First customer adapters; evolution jobs |
| 3 | B with vLLM / SGLang multi-LoRA on shared base | Cost collapses once we serve N tenants on one base |
| 4 | C (dedicated) | Only after step 3 utilization proves it |

This sequencing means we never carry idle GPUs to win our first
customer, and we never get trapped in Layer A when a tenant grows
beyond it.

---

## 4. Cost-control disciplines

| Discipline | Mechanism |
|---|---|
| Cost-per-successful-task tracked per tenant route | `benchmarks/cost_per_success_by_tenant.yaml` |
| Margin per evolution recorded per job | `schemas/evolution_job.schema.json::cost_breakdown` + `revenue_usd` |
| Fallback rate (escalation to Opus / Sonnet) tracked per route | `schemas/tenant_model_route.schema.json::fallback_policy` |
| Cache hit rate (root+delta cache, prompt cache) tracked per route | `tenant_model_route.schema.json::caching` |
| Adapter promotion rate (proportion of evolutions that ship) | `evolution_job.schema.json::outcome.promoted` |
| Tenant GPU utilization (Layer C only) | dedicated worker telemetry export |
| Subscription dollars avoided (Studio tier replaces Claude Pro etc.) | tenant-level KPI in `evolution_pricing_model.md` |

These metrics, once a tenant has 30 days of data, drive promotion
between A → B → C and tier upgrades on the customer side.

---

## 5. Anti-patterns we are explicitly avoiding

| Anti-pattern | Why no |
|---|---|
| Renting an A100 for a tenant before they have 14 days of traffic | slm-learning-220 — utilization unproven; Layer A or B almost always cheaper |
| Running closed-API teacher (Opus) on hot path for routine traffic | Burns margin; Opus is teacher/escalation, not hot path (slm-learning-197) |
| Deploying our own base on Vast.ai for production traffic | Marketplace pricing varies; not consumer-production reliable |
| Storing adapters >100MB on local laptop disk | slm-learning-105 — disk at 93% |
| Always-on HF dedicated endpoint for a low-RPM tenant | $365/month idle is a margin-killer at Starter / Creator tier pricing |

---

## 6. Routing summary

```
Daily inference (any tier)
  → Layer A hosted API (Together / OpenRouter) for shared open-weight
  → Layer B serverless GPU + multi-LoRA vLLM for tenant-private adapter
  → Layer C dedicated GPU only if tenant is Studio+ AND utilization > 50%

Evolution jobs (Creator+ tiers)
  → Layer B serverless (Modal / RunPod) batch
  → Cost stamped to evolution_job record
  → Margin computed against tier price

Teacher / labeler / comparator (internal)
  → Layer A direct (Anthropic / OpenAI / Google / Together)
  → Per slm-learning-197 teacher policy
```

— Dr. Stein, hosting cost strategy, 2026-05-08
