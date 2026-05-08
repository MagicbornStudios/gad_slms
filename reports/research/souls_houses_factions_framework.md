# Souls / Houses / Factions Framework

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Decision refs:** slm-learning-045 (souls are operational
constitutions), slm-learning-047 (souls enforced through prompts +
eval rubrics + routing first; fine-tuning later behind regression
gate), slm-learning-048 (model council pattern), slm-learning-101
(six research tracks), slm-learning-121 (system-level MoE),
slm-learning-124 (system-as-teacher), slm-learning-186..192
(consolidation pipeline), slm-learning-193 (proposed below)
**Companion:** `narrative/souls/`, `reports/research/incremental_latent_consolidation.md`,
`reports/research/pressure_to_training_research_agenda.md`

---

## Why this framework now

The consolidation pipeline (slm-learning-186..192) gave us
**typed pressure → typed delta packets → typed retain banks →
small consolidation runs → router**. That covers the **how**.

The souls/houses/factions framework covers the **who** —
which specialist absorbs which pressure, which retain bank
anchors which behavior, which router route serves which
operator-facing role.

GAD already has named souls (Dr. Stein, Kael, Gilgamesh, etc.)
treated as operational constitutions per `slm-learning-045/047/048`.
This doc operationalizes them as **specialist model lanes** with
their own pressure profiles, retain banks, training cadences, and
deployment routes.

---

## Hierarchy

```
faction (research direction / strategic role)
  └── house (long-lived specialist family — owns its pressure profile)
        └── soul (operational identity — uses one or more houses' models)
              └── model (concrete adapter / morphism / serve route)
```

| Layer | Lifetime | Owns | Example |
|---|---|---|---|
| faction | months–years | strategic theme | "GAD-coder", "GAD-artifact", "GAD-tool-action" |
| house | weeks–months | pressure profile + retain bank + delta packets | "Stein-house" (model-improvement scientist), "Kael-house" (computer-use + UI generation) |
| soul | days–weeks | prompt / role / eval rubric | "dr-stein", "kael", "gilgamesh", "verifier" |
| model | hours–days (consolidation) | one trained delta | adapter id `lora-1p5b-stein-2026-05-08` |

A soul is the public face. A house is the durable training
substrate. A model is one consolidation run's output. A faction
is the strategic bucket they're all in.

---

## Houses currently identifiable in slm-learning

| House | Faction | Soul(s) | Pressure source | Status |
|---|---|---|---|---|
| **Stein-house** | GAD-coder | dr-stein | base eval failures (HE/MBPP) | **canonical at 1.5B** (`lora-1p5b-hard-retain` lifted +9.1/+3.0) |
| **Kael-house** | GAD-artifact + GAD-tool-action | kael | computer-use traces, UI generation, game artifacts | **planned** — needs dataset capture pipeline |
| **Gilgamesh-house** | GAD-strategy | gilgamesh | high-level decision routing, multi-agent coordination | **prompt-only today** (no fine-tune yet) |
| **Verifier-house** | GAD-coder + GAD-tool-action | verifier | contract validation failures, doc-verifier r=16 (F1 0.720, slm-learning-090) | **r=16 canonical** at 1.5B (existing) |
| **Archivist-house** | GAD-strategy | archivist | summary / cross-session memory / documentation | **prompt-only today** |
| **Critic-house** | GAD-strategy | critic | regression detection, "this looks wrong" pattern | **prompt-only today** |

Plus the 5 ChatGPT-suggested houses still on the menu:
- **Bestiary-house** (GAD-artifact) — game/Magicborn entity generation
- **Skill-router-house** (GAD-strategy) — picks specialist per request
- **Tech-stack-inference-house** (GAD-coder) — picks framework / repo conventions
- **Music/marketing-house** (GAD-artifact)
- **Repair-house** (GAD-coder) — codebase fix-ups, distinct from base coder

Decision: keep this list open. Each house earns its place by
producing a measurable retain bank + at least one consolidation
run that lifted on its eval.

---

## What each house owns (the contract)

For a house to be considered "real" (not just a soul prompt), it
must produce these durable artifacts:

1. **Pressure profile** — JSON describing the failure clusters
   this house's specialist is meant to absorb. Sourced from
   `gad errors list` filtered to that house's domain + telemetry
   exports + correction logs.
2. **Context root(s)** — at least one entry in
   `data/context_roots/<house>-*.json` per
   `schemas/context_root.schema.json`.
3. **Retain bank** — at least one entry in
   `data/retain-banks/<house>/<benchmark>/<date>/passed.jsonl`
   built by `scripts/data/build_retain_bank.py`.
4. **Delta packet shard** — at least one shard in
   `data/delta_packets/<house>/<failure_type>/<date>/`
   built by `scripts/data/build_delta_packets.py`.
5. **Consolidation run** — at least one
   `consolidation_run.json` per
   `schemas/consolidation_run.schema.json` with promotion verdict
   = canonical or staging.
6. **Soul.md** — operational constitution at
   `narrative/souls/<soul>.md`. Already standard.
7. **Eval rubric** — what "this house's adapter is working" means
   (HE+MBPP for Stein, contract-pass-rate for Verifier,
   trajectory-completion for Kael, etc.).
8. **Route** — vLLM serve config that maps requests to this house's
   adapter (Lane D in `pressure_to_training_research_agenda.md`).

A house without items 1-5 is a **soul** (prompt-only). A house
WITH them is a **specialist lane** that gets a permanent slot in
the consolidation pipeline.

---

## Stein-house — the canonical worked example

This is the shape every other house should mirror.

| Artifact | Path | Status |
|---|---|---|
| Pressure profile | `tmp/diag-2026-05-08/base_he_1p5b_full.json` | built |
| Context root | `data/context_roots/qwen-1p5b-humaneval-function-definition.json` | built |
| Retain bank | `data/retain-banks/1p5b/humaneval/2026-05-08/passed.jsonl` (90 rows) | built |
| Delta packet shard | `data/delta_packets/base_failures/1p5b/humaneval/2026-05-08/` (74 packets) | built |
| Consolidation run | `models/runs/lora-1p5b-hard-retain-2026-05-08/MANIFEST.json` | built |
| Soul.md | `narrative/souls/dr-stein.md` | exists |
| Eval rubric | HE pass@1 + MBPP pass@1 on n=164 | locked |
| Route | TBD — vLLM serve config (Lane D) | **gap** |

**Stein-house's promoted model:** `lora-1p5b-hard-retain-2026-05-08`,
HE 64.0% / MBPP 64.0%, $/pp-lift 0.0037. Canonical
(slm-learning-173).

The other houses below should produce the same artifact set
before they're promoted from soul to house.

---

## Kael-house — flagship next priority

**Why first:** operator note 2026-05-08 — "Kael is becoming the
de-facto face/soul of get-anything-done and is the flagship chat
model competing against ChatGPT and Claude Opus directly... in
experience and outcome leveraging our ecosystem and specializations."

Kael's pressure source is NOT HE/MBPP. Kael's pressure is:

- escape-the-dungeon trajectory failures (composite < 0.5 OR
  human_review < 0.5) per `evals/escape-the-dungeon/species/`
- gad_tools eval failures (current 36.7% baseline; high-pressure)
- bestiary / artifact generation contract violations
- Magicborn / Grime Time site builds that the human reviewer
  scored low

Kael's retain bank is the cases where the bare runtime ALREADY
ships a working artifact (bare/v2 0.601/0.50, emergent/v4 null/0.885).

Kael's delta packets are the differences between failed
trajectories and successful ones, conditioned on the GAD
framework being held constant (Q1 hybrid in
`scaling_proof_charter.md`).

**Kael-house's first deliverable:** a 1.5B (or 3B) adapter that,
when served via vLLM as the code-completion backend behind
claude-cli + GAD framework, lifts the row-7 trajectory composite
above bare's 0.601 baseline.

This is the **flagship** consolidation run — it exercises every
piece of the framework end-to-end on a non-saturated benchmark.

---

## Family-style training across houses

The factions can share **retain banks** but never **delta packets**.

| Sharing rule | Reason |
|---|---|
| Retain banks: SHARED across houses in same faction | preserves overlapping behavior (Stein's MBPP retain rows are also valid retain rows for Verifier on similar shapes) |
| Delta packets: NEVER shared across bases | per slm-learning-189 — each base has its own pressure profile |
| Context roots: SHARED across same `(model_family, benchmark, contract)` triple | composes to less duplication; same root_context_id reused by Stein-house and Verifier-house if both emit function_definition on Qwen 1.5B HE |
| Consolidation runs: per-(house, base, dataset) | full traceability; same house can have many consolidation runs on different dataset+base combinations |

This is the "family" structure — houses inherit retain rows from
the faction, but their delta packets are theirs alone.

---

## Generalizability — when does a house's delta apply elsewhere?

Three rules:

1. **Within-base** (slm-learning-189): a 1.5B Stein delta does NOT
   transfer to 3B Stein. Each base trains on its own pressure
   profile.
2. **Within-faction**: a 1.5B Stein delta MAY transfer to 1.5B
   Verifier IF the failure_type tags overlap (both shape:
   function_definition, contract: function_definition). Tested
   case-by-case; not assumed.
3. **Cross-faction**: a Stein delta does NOT transfer to Kael —
   they're different factions. But the *retain bank format* and
   *pipeline* transfer; only the data is per-faction.

This gives us a controlled answer to "does our model generalize?"
The answer is layered:

- generalizes within retain bank? (yes by construction)
- generalizes within house? (yes if dataset density is high enough)
- generalizes within faction? (sometimes; case-by-case)
- generalizes across factions? (no; build a new faction)

---

## Long-term path

```
Phase 1 (now):  Stein-house canonical at 1.5B
                Kael-house dataset capture pipeline
                Verifier-house already canonical
Phase 2 (next): Kael-house 1.5B canonical via hybrid trajectory test
                Bestiary-house first delta packet shard
                Skill-router-house classifier
Phase 3 (mid): each house has own 1.5B + 3B models
                Adapter-MoE router routes per-request to house
                Cost-per-success matrix shows which house earns its serve cost
Phase 4 (long): larger smoothing pass per faction (Lane E in pressure_to_training_research_agenda.md)
                7B/14B base adaptation absorbs proven house deltas across that faction
                Multimodal-adjacent structured artifacts (slm-learning-191) for Kael-house
```

Higher-end models get built only **after** the small-delta pregame
proves which deltas matter — per slm-learning-194.

---

## Decision proposed: slm-learning-193

> **Souls become houses become specialist lanes.** Every
> operator-facing soul (Stein/Kael/Gilgamesh/Verifier/Archivist/
> Critic) gets a corresponding house (pressure profile + context
> roots + retain bank + delta packet shards + consolidation runs +
> route) before being promoted from prompt-only to served
> specialist. Houses share retain banks within a faction; never
> share delta packets across bases. The flagship Kael-house
> consolidation run is the next priority because Kael is GAD's
> public-facing chat model.

— Dr. Stein, souls/houses/factions framework, 2026-05-08
