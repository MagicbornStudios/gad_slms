# Nous Research / Hermes Integration Design
**Date:** 2026-05-09
**Author:** Claude Code (Gilgamesh-lane)
**Status:** DRAFT — operator review required before Day-1 execution

---

## 1. Bottom Line

Nous Research is executing the same program as slm-learning at open-weights frontier scale: build autonomous agents with persistent memory, train them with RL environments and DPO datasets, and distribute the training infrastructure itself as open tooling. The gap between their work and ours is scale and public distribution, not direction — which means we can adopt their models as drop-in comparator baselines today, contribute our owned datasets and methodology back through their open channels, and build a reciprocal relationship that accelerates both sides without diluting our proprietary data moat.

---

## 2. Convergence Map

| Nous artifact | slm-learning equivalent | Adoption mode |
|---|---|---|
| Hermes Agent (MIT, Feb 2026) | Kael — autonomous, server-resident, memory via dataset tower | Inspiration + selectively port interaction patterns (memory schemas, skill-storage format) |
| NousCoder-14B (Qwen-3-14B post-trained, Jan 2026) | kael-14b-game-implementation-vN (planned) | Direct fallback + eval baseline; run through scaling_ladder suite Day 2 |
| Hermes-4-14B (Aug 2025, Apache 2.0) | kael-of-tarro-v1-intended (qwen2.5-coder-7b-instruct base) | Fallback when our 14B adapter underperforms; same task_shapes |
| Hermes-4-Llama-3.1-70B (Aug 2025) | Gilgamesh (Anthropic Opus, rate-limited) | Rate-limit fallback for planning/architecture tasks |
| Hermes-4 Technical Report | souls_houses_factions_framework.md + soul_routes.toml | Format alignment: their hybrid reasoning ON/OFF maps to our task_shape routing |
| Hermes-3 Dataset (complete pretraining data, Jul 2025) | our delta_packets + decision_dataset + agent_trace | Format alignment for cross-pollination; potential SFT seed |
| Atropos (LM RL Environments, Apr 2025) | our Layer 7 verifier + RL dataset scaffolding | Adopt Atropos env contract; publish gad_tools as an Atropos environment |
| Psyche Network (distributed training, May 2025) | our Modal-hosted single-node CPT | Evaluate as secondary training lane OR redundancy once our dataset > 500K tokens |
| Genstruct-7B (synthetic data gen, Mar 2024) | our delta-packet generation pipeline | Use as teacher signal for SFT data synthesis — amplify seed examples 10-50x |
| DeMo / DisTrO (decoupled momentum papers) | (none yet — we use local LoRA + standard AdamW) | Adopt DeMo for multi-account distributed CPT once Layer 2 dataset is large enough |
| Hermes-4.3-Seed-36B (Psyche-trained, Dec 2025) | (no equivalent) | Monitor: first model trained on Psyche Network, validates that infra for future adoption |
| Nomos 1 (30B mathematician, Dec 2025) | (none — math reasoning not a current lane) | Future: Layer 6 reasoning dataset if math eval enters our scaling ladder |

---

## 3. Adoption Tiers

### (a) Hermes-4-14B as Kael's serving fallback

The immediate production win. When our gad-trained Kael adapter underperforms on tool_action or code-generation tasks, the fallback chain in `soul_routes.toml` should route to `hermes-4-14b-local` before escalating to Anthropic. Hermes-4 supports hybrid reasoning (thinking tags switchable) and is fine-tuned for function-calling — the exact task_shapes Kael handles most. Apache 2.0 license permits commercial serving.

Deployment path: Modal vLLM serve with OpenAI-compat `/v1` endpoint. Model: `NousResearch/Hermes-4-14B` from HuggingFace. The soul_routes entry (`hermes-4-14b-local`) is live in the TOML; the Modal serve script (`slm_learning/modal_app/hermes_4_14b_serve.py`) is the remaining gap.

Graduation gate: retire this fallback once our `lora-kael-14b-vN` adapter scores within 2pp of Hermes-4-14B on HumanEval pass@1 using the same eval harness.

### (b) NousCoder-14B as our canonical 14B reference baseline

NousCoder-14B (Qwen-3-14B post-trained on olympiad coding) is the strongest publicly available 14B code model as of January 2026. It defines the ceiling our kael-14b adapter is climbing toward.

Concrete action: run NousCoder-14B through our `scaling_ladder` eval suite — HumanEval clean, MBPP, gad_tools JSON accuracy, tool_action_json format compliance — and record the baseline scores in `slm_learning/data/registry/benchmark_scores.json`. Every subsequent kael-14b adapter run is compared against this number. When we hit within 2pp, the `nouscoder-14b-local` soul entry retires and we declare our 14B lane independent.

This is the most disciplined thing we can do with the Nous relationship: treat their best public model as the bar, measure honestly against it, and publish the delta. That transparency makes our eventual contribution credible.

### (c) Genstruct-7B for delta-packet synthesis

Our delta-packet pipeline generates SFT training rows from operator traces and planning artifacts. The bottleneck is seed count — a single gad session produces 5-20 high-quality examples, not enough for a training run. Genstruct-7B is purpose-built to expand a few seed examples into structured instruction-following data at scale.

Integration pattern: after each operator session produces delta_packets, run them through Genstruct-7B as a teacher to generate 10-50 synthetic variants per seed, filtered by our existing schema validator. This is additive — Genstruct output supplements but never replaces real operator traces. The real traces are DPO-preferred; Genstruct variants are SFT fill. This pattern directly addresses our dataset scarcity problem without any new data collection infrastructure.

---

## 4. Contribution-Back Proposal

Five concrete contributions GAD can make to Nous Research in the next 6 months, ordered by effort:

### (i) Tool-use preference dataset — HuggingFace publication

Our `slm_learning/schemas/tool_use_preference.schema.json` shaped data contains cheap-tool-vs-foraging preference pairs capturing when an agent should call a tool versus attempt to answer from context. This is directly usable by Atropos RL environments and by the Hermes fine-tuning pipeline. Publish as a HuggingFace dataset under CC-BY-4.0 once we accumulate ≥100 rows. Starting with 10 seed rows now establishes the dataset and creates a citation anchor.

The `conceptual_failure_mode` field in our schema — capturing the reasoning error type when the agent makes the wrong choice — is not present in any published preference dataset we're aware of. That's the differentiating contribution.

### (ii) Decision DPO dataset — `decision_preference.schema.json` rows

Our decision dataset captures architecture-level choices with rejected alternatives and the reasoning that differentiated them. Nous's Hermes models are trained heavily on instruction-following and function-calling; architectural decision reasoning is underrepresented in their training data by design (they target developers, not planners). Publishing 50-200 high-quality decision DPO rows fills a gap in their data distribution and provides a cite-able contribution to the community.

### (iii) Atropos environment: gad_tools

Wrap our gad CLI verification layer into an Atropos-compatible RL environment. Atropos provides the reward signal infrastructure; we provide the environment (agent calls gad CLI tools, gets pass/fail + score feedback). The environment exposes: `gad tasks add`, `gad decisions add`, `gad state log`, and `gad verify`. An agent trained on this environment learns to drive the GAD planning loop autonomously.

Publication: open-source the env as `atropos-gad-tools` on GitHub, submit to the Atropos environment registry. This is a direct contribution to the Nous ecosystem and establishes GAD as a credible planning-domain benchmark.

### (iv) Skill-based continual pretraining methodology note

Our Data Dungeon's per-skill weighted CPT — where each training layer emphasizes skill-relevant token distributions rather than uniform corpus mixing — may be novel in the open-weights community. Nous's published training reports describe dataset mixing but not per-skill weighting. Publish a 2-4 page methodology note (not a full paper) describing the approach, the skill_pressure metric, and our ladder-gate graduation system. Submit to the Nous community forum and arXiv (cs.LG, brief).

This is low effort relative to impact: the methodology is already implemented and documented in `slm_learning/reports/research/staged_continual_pretraining.md` and `skill_pressure_correlation.md`.

### (v) Soul-route + adapter-stack pattern as reference architecture

The soul/route decoupling shipped today in `soul_routes.toml` — where a soul's personality/voice is defined in narrative and its serving stack (base model + adapter + endpoint + graduation gate) is defined separately in the registry — is reusable by any open-weights organization running multiple agent personas. Nous runs Hermes Agent with persistent memory; they have the persona concept but no published routing layer.

Offer this as a community post on the Nous Discord + GitHub Discussions: "How we decouple soul identity from model serving for multi-persona agent systems." Include the TOML schema, the graduation gate pattern, and the fallback chain design. No code release required — the design pattern is the contribution.

---

## 5. Risk and License Matrix

| Model | License | Commercial use | Contamination risk |
|---|---|---|---|
| Hermes-4-14B | Apache 2.0 (verify HF card `NousResearch/Hermes-4-14B`) | Permitted, attribution required | Moderate — Hermes-3 dataset (Jul 2025) likely overlaps HumanEval/MBPP. Do not use HumanEval as sole eval; supplement with gad_tools + tool_action_json which Nous has not trained on |
| NousCoder-14B | Apache 2.0 (Qwen-3 base = Apache 2.0; verify post-train license) | Permitted, attribution required | High for competitive programming evals — specifically trained on olympiad data. Use MBPP and gad_tools as primary comparison; treat HumanEval score with contamination caveat |
| Hermes-4-Llama-3.1-70B | Apache 2.0 (verify HF card; Llama 3.1 base = Meta Research License — verify compatibility) | Apache 2.0 layer permits commercial use IF Meta base license is compatible — verify before serving commercially | Same as Hermes-4-14B; 70B variant likely used same dataset with more compute |
| Hermes-3 Dataset | Check HF dataset card — may be research-only | Do not assume commercial use without explicit check | Broad pretraining corpus; may overlap with our retain banks. Run contamination check before using as SFT seed |
| Genstruct-7B | Apache 2.0 (verify) | Permitted | Low — data synthesis model, not a benchmark competitor |
| Atropos | Apache 2.0 (GitHub: NousResearch/atropos) | Permitted | N/A — framework, not a model |

**Open action:** before any commercial serving of Llama-3.1-based models, verify that the Meta Research License for Llama 3.1 permits downstream commercial serving under Apache 2.0. This is a known gray area in the open-weights ecosystem.

---

## 6. Concrete Next-Week Plan

| Day | Action | Output | Owner |
|---|---|---|---|
| Day 1 | Modal-deploy Hermes-4-14B; wire as `hermes-4-14b-local` fallback in Kael's soul_routes chain | `slm_learning/modal_app/hermes_4_14b_serve.py` deployed; endpoint URL in soul_routes.toml | operator / Dr. Stein lane |
| Day 2 | Run NousCoder-14B through scaling_ladder eval suite (HumanEval, MBPP, gad_tools, tool_action_json) | baseline scores in `benchmark_scores.json` under `nouscoder-14b-2026-01` key | Dr. Stein lane |
| Day 3 | Sketch Atropos env wrapper for gad_tools; publish as GitHub gist | `atropos_gad_tools_env.py` gist link; design note in `.planning/notes/` | operator |
| Day 4 | Open HuggingFace dataset for tool_use_preference; seed with 10 rows from existing delta_packets | `benjamingarrard5279/gad-tool-use-preference` dataset on HF | operator |
| Day 5 | Submit community post to Nous Discord summarizing soul-route pattern; link to soul_routes.toml schema | Post URL logged in `.planning/notes/2026-05-14-nous-community-post.md` | operator |

Day 1 is the critical path — everything else (fallback chain, graduation gate baselining, contribution credibility) depends on having the Hermes endpoint live.

---

## 7. Open Questions

**Q1: Host capacity.** Can we afford to serve 14B locally (personal GPU) vs Modal? At Modal A10G pricing (~$1.10/hr), a lightly-used fallback endpoint costs ~$26/month if kept warm 24hr. Recommendation: Modal with cold-start acceptable for fallback use; warm only during active training runs.

**Q2: License alignment for commercial use.** The Llama 3.1 base license (Meta Research License) has a 700M monthly active user threshold clause and attribution requirements that interact non-trivially with Apache 2.0 overlayers. If GAD products cross the MAU threshold (unlikely soon but not impossible if Kael scales), review required. NousCoder-14B on Qwen-3-14B base (Apache 2.0 base) has cleaner commercial posture.

**Q3: Contamination in our retain banks.** Nous's Hermes-3 dataset is publicly available and broad. If we fine-tune on data that Hermes was also pretrained on, our eval comparisons become meaningless. Before publishing any "our adapter beats Hermes" claims, run overlap detection between our delta_packet corpus and any Nous-published training data. This is also a contribution opportunity: publish our contamination-check methodology.

**Q4: Psyche Network vs Modal.** Psyche is Nous's open distributed training infrastructure. We currently use Modal for single-node jobs. If our Layer 2 dataset reaches 5M+ tokens and we want to run a meaningful CPT run, Psyche may be the right infra — especially if Nous provides researcher access. Track but don't commit yet; our immediate bottleneck is data, not compute.

**Q5: Contribution reciprocity timing.** Nous is an active research org shipping quarterly. Publishing a tool-use preference dataset with 10 rows and a community post about soul-routing in May 2026 establishes presence. But the credible contribution window for Atropos env + methodology note is 3-6 months out, once our scaling_ladder results are reproducible. Don't over-promise on contribution timeline; under-promise and deliver when the data is real.
