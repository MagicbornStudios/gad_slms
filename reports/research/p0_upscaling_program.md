# P0 Scaling & Upscaler Initiative: Operating Constitution

**Status:** Active, permanent fixture of research cycles.  
**Owner:** Research directorate.  
**Sponsor:** Operator (declared P0 2026-05-07).

---

## Mandate

> "We build bigger models with lower ones over time (the goal) so model morphism is essential."
> — Operator

Upscaling is the permanent research thread. Every cycle must include at least one low-cost scaling experiment. This document is the durable reference for the 10 scaling lanes, their current state, and the hard rules that govern promotion.

---

## The 10 Scaling Lanes

### Lane 1: Data Scaling
*More/better tokens for same model (Chinchilla-optimal scaling laws).*

**Pros:**
- Predictable ROI via scaling laws (verify token count vs accuracy gain).
- Reuses existing model, adapter infrastructure.
- Low infra cost; mostly data pipeline work.
- Can mix HF datasets (FineWeb, The Stack, OpenMathInstruct) without expensive retraining from scratch.

**Cons:**
- Hits VRAM ceiling faster (batch size limits on 6GB GTX 1660 Ti).
- Requires clean data; garbage input = garbage output.
- Chinchilla-optimal is empirical per domain; no universal recipe.

**Immediate test:**
- Train 3B on FineWeb-100B vs existing dataset; hold LoRA rank constant (r=16); measure HumanEval + code_smoke at iso-walltime.

**Pass criteria:**
- +2pp HumanEval or +1.5pp MBPP at same rank/epoch; cost/task improvement documented.

**Status in slm-learning:**
- Data pipeline exists (modal_app/pull_datasets.py).
- HF dataset integration running in experiments.
- Chinchilla law not yet systematically swept.

---

### Lane 2: Hard-Example Scaling
*Train larger bases only on verified failure clusters.*

**Pros:**
- Proven leverage: slm-learning-119 showed +3.1pp HE / +1.8pp MBPP at 7B for $0.14.
- Focuses compute on actual weak spots (no wasted training on easy examples).
- Works with any base model; orthogonal to other lanes.

**Cons:**
- Requires prior eval to identify failure clusters (can't start blind).
- Filtering logic must be robust; wrong clusters = confounded gains.
- Small dataset means slower convergence; verify generalization on held-out.

**Immediate test:**
- Re-run slm-learning-119 recipe on 3B base; measure whether lane generalizes to smaller model.

**Pass criteria:**
- Repeated success on at least 2 model sizes; cost/task better than uniform training.

**Status in slm-learning:**
- Lane 2 is proven at 7B; decision slm-learning-119 locked.
- Scaling to 3B in progress; decision record in flight.

---

### Lane 3: Parameter Scaling
*Ladder: 1.5B → 3B → 7B → 14B → 32B dense bases.*

**Pros:**
- Direct capacity increase; predictable gains near scaling-law intercept.
- Base models exist on HF Hub; low friction to fetch.
- Ladder architecture ensures smaller sizes smoke-test new recipes before big shots.

**Cons:**
- VRAM doubling per step; 7B → 14B requires new hardware or aggressive quantization during training.
- Bigger base = longer training wall-time (more epochs = more cost).
- 32B requires fallback strategy or system-level MoE (lane 6).

**Immediate test:**
- 1.5B smoke on OpenCodeReasoning; compare to 3B on same data.

**Pass criteria:**
- Predicted 7B gain (from ladder fit) vs actual 7B result within 15%; cost/param analyzed.

**Status in slm-learning:**
- 1.5B → 3B smoke complete (5/5 on code_smoke, latest commit).
- 7B fixed-judge eval in final review.
- 14B/32B not started (gated on 7B lift).

---

### Lane 4: Adapter Scaling
*LoRA rank/target/epoch sweeps on frozen base.*

**Pros:**
- Rank r=8 → r=16 → r=32 is purely hyperparameter; no retraining base.
- Cheap signal; 3x sweep at same base costs 3x the epochs, not 3x training from scratch.
- Adapter-stacking ready for lane 5.

**Cons:**
- Rank hits bottleneck; r>32 on small bases may harm generalization.
- Target-layer selection is empirical; no universal rule (head-only vs full-model).
- Epoch scaling shows diminishing returns past ~5 epochs (documented in regression journals).

**Immediate test:**
- Sweep r={8,16,32} on 3B base, HumanEval + code_smoke, measure ROI per parameter.

**Pass criteria:**
- Identify sweet-spot rank for 3B, with cost/task ratio locked for next cycle.

**Status in slm-learning:**
- r=16 is default; some r=8 logs exist.
- r=32 tested in adapter-MoE prototype (lane 5 prep).
- Systematic sweep not yet run.

---

### Lane 5: Adapter-Level MoE
*Router-selected LoRAs on one base (vLLM per-request routing).*

**Pros:**
- Reuses trained adapters (no new base training).
- vLLM supports per-request routing; no fork-merge hassle.
- Soft specialization: one adapter for code, one for reasoning, router picks at inference time.
- Cost = adapter inference cost only; base shared.

**Cons:**
- Router training is another hyperparameter (loss weight, initialization).
- Inference latency from extra routing logic (small, ~1-2ms per request).
- Adapter interference (adapters trained independently may have gradient conflicts under routing).

**Immediate test:**
- Train 3x r=16 adapters on 3B (code, reasoning, general); static router (one per domain); measure vLLM throughput + accuracy vs single adapter.

**Pass criteria:**
- Combined accuracy ≥ best single adapter; inference latency <10% overhead.

**Status in slm-learning:**
- Lane 5 scaffold drafted (vLLM integration in modal_app).
- No live adapters routed yet.

---

### Lane 6: System-Level MoE
*Router + specialists + 7B/32B fallback.*

**Pros:**
- Hard specialization: deploy multiple 7B models, route based on task.
- No adapter bottleneck; each specialist is full capacity.
- Fallback strategy: uncertain requests → big model; lowers false negatives on ambiguous tasks.

**Cons:**
- VRAM ceiling hit immediately; 2x 7B = 2x 6GB = 12GB local (exceeds laptop).
- Inference cost doubles (2 models, router overhead).
- Requires careful load-balancing; one overloaded specialist throttles system.

**Immediate test:**
- Simulation: mock 7B + 32B fallback on current laptop; measure router latency + memory peak under synthetic load.

**Pass criteria:**
- Fallback triggered <5% of requests; accuracy gain >1pp on ambiguous task cluster.

**Status in slm-learning:**
- Lane 6 is system-research; no live deployment.
- decision slm-learning-121 describes architecture; not yet implemented.

---

### Lane 7: Distillation Scaling
*System-as-teacher; fallback/human corrections become DPO pairs.*

**Pros:**
- Reuses inference pipeline (no new base needed immediately).
- Human corrections are free data (log them); convert to DPO pairs for next fine-tune.
- Bootstraps reasoning without retraining: larger model distills to smaller.

**Cons:**
- Requires human feedback loop (slow; adds latency to training cycle).
- DPO training can be unstable; careful loss-weighting needed.
- Can reinforce teacher's biases; need diverse correction sources.

**Immediate test:**
- Collect 100 fallback-to-claude-3.5-sonnet corrections; build DPO pair dataset; train 3B adapter on it; measure gain on hard-example cluster.

**Pass criteria:**
- DPO-trained adapter beats SFT-only on correction-relevant tasks; cost/correction <$0.50.

**Status in slm-learning:**
- Lane 7 scaffolding started (decision slm-learning-124 in flight).
- Human correction logging not yet automated.

---

### Lane 8: Retrieval/Context Scaling
*Repo memory, skills, skeletons.*

**Pros:**
- No new model training; pure data/prompt engineering.
- Reuses existing codebases (GAD tools, Magicborn, Grime Time).
- Can be applied to any base model; layer-agnostic.

**Cons:**
- Context window is fixed (4K → 8K is architecture change, not scaling).
- Retrieval quality depends on embedding model quality; garbage embeddings = garbage context.
- Overhead: every inference query now hits retrieval; latency cost.

**Immediate test:**
- Add 3-shot codebase skeleton to prompt; measure HumanEval accuracy gain vs no skeleton.

**Pass criteria:**
- +1pp accuracy; latency overhead <200ms (retrieval + embedding).

**Status in slm-learning:**
- Lane 8 is integrated into baseline (prompts include repo skeletons).
- Formal A/B test not yet locked.

---

### Lane 9: Inference Scaling
*Quantization, KV cache, prompt caching, speculative decoding, vLLM/SGLang.*

**Pros:**
- No retraining; pure inference optimization.
- Compound effects: int8 + vLLM + speculative decoding stacks.
- Throughput gain (3-5x on vLLM) is free improvement for latency-sensitive tasks.

**Cons:**
- Accuracy can degrade with quantization (need accuracy regression tests).
- Speculative decoding requires small draft model; adds another model to manage.
- vLLM/SGLang are moving targets; dependency fragility risk.

**Immediate test:**
- Quantize 3B to int8; measure accuracy vs fp16 on HumanEval; measure throughput gain on vLLM.

**Pass criteria:**
- <0.5pp accuracy loss; 3x+ throughput improvement.

**Status in slm-learning:**
- vLLM integration in modal_app (throughput tested).
- int8 quantization not yet in eval pipeline.

---

### Lane 10: Function-Preserving Morphism
*Identity-init expansion, Net2Net widening/deepening, dense-to-MoE upcycling.*

**Pros:**
- Reuses pre-trained weights from smaller model (no random init).
- Function-preserving: 1.5B expanded → 3B runs same code initially.
- Enables 0.5B/1.5B research (tiny models for prototyping; scale up deterministically).

**Cons:**
- Expansion is theoretical; empirical gains unclear (Net2Net papers are dated).
- Implementation complexity: need custom expansion ops (PyTorch modules).
- Post-expansion retraining can unlearn initialized structure if learning rate too high.

**Immediate test:**
- Start with 1.5B checkpoint; expand to 3B with identity+zero init; train on 10% of normal data; measure how quickly it recovers to baseline.

**Pass criteria:**
- 3B-expanded recovers to 1.5B-baseline accuracy within 2 epochs on HumanEval; cost/wall-time better than training 3B from scratch.

**Status in slm-learning:**
- Lane 10 is research-only; no implementation started.
- decision slm-learning-120 (morphism strategy) locked; awaits implementation.

---

## Hard Rules (Locked by Operator)

1. **Upscaling is P0**: Every research cycle must include ≥1 scaling experiment. No deferral except explicit operator waiver.

2. **Internal MoE is research, not first implementation**: Lane 6 (system-level MoE) is locked to decision + simulation until 7B baseline is locked. Lane 5 (adapter-MoE) scaffolds first.

3. **32B LoRA requires 7B lift gate**: Do not train 14B/32B adapters until 7B baseline passes held-out gate (85%+ on code_smoke or equivalent).

4. **Bigger base as fallback is allowed before bigger LoRA**: Lane 6 (fallback to 32B) can run in parallel with lane 4 adapter sweeps; both feed decision logic.

5. **Every scaling experiment must measure cost per successful task**: Raw accuracy is not enough. Report: (USD spent + GPU hours) / (# tasks solved - baseline) for every lane experiment.

6. **Every cycle includes at least ONE scaling experiment**: If a cycle has no active lanes, escalate to operator immediately.

---

## Cross-References

- **`reports/scaling/gad_scaling_ledger.md`**: Durable record of all scaling experiments (being built in parallel; locked weekly).
- **`reports/research/continuous_upscaling_strategy.md`**: Companion doc with morphism prototype plan and lane roadmap.
- **Decisions slm-learning-153 through slm-learning-163**: Research lane decisions (being logged as experiments run).
- **`.planning/research/EXPERIMENTS.json`**: EXP-001 through EXP-010; new scaling exps require EXP-id.

---

## Integration with Compare-and-Compete Discipline

Every scaling promotion candidate (esp. lanes 3, 6, 7) must produce four eval rows per **slm-learning-103**:

1. **Public-leaderboard row** (HumanEval + MBPP + SWE-bench Verified subset).
2. **Frontier comparator row** (same eval vs claude-cli + Big Pickle + OpenRouter free tier + bare base).
3. **Owned-domain row** (GAD tools / doc-verifier / tooluse / Magicborn / Grime Time / Kael).
4. **Lineage row** (parents, training method, cost, wall hours, regression journal URI, outputs corpus URI).

No exceptions. A candidate without the comparator row is not a candidate; it is a vibe.

---

## Next Steps (Immediate, This Cycle)

- [ ] **Lane 2**: Re-run hard-example scaling on 3B; validate slm-learning-119 at smaller model.
- [ ] **Lane 3**: Confirm 7B smoke completes; lock gate for 14B.
- [ ] **Lane 4**: Sweep r={8,16,32} on 3B; document rank/cost sweet-spot.
- [ ] **Lane 5**: Implement vLLM router scaffold; test with 2 pre-trained adapters.
- [ ] **Lane 7**: Automate human-correction logging; build first DPO pair batch.
- [ ] **Lane 10**: Proposal for 1.5B → 3B expansion experiment; author decision doc.

---

**Document version:** 2026-05-07  
**Locked by:** Operator  
**Maintenance:** Weekly sync with gad_scaling_ledger.md and EXPERIMENTS.json
