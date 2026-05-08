# Continuous Upscaling Strategy

**Owner**: Dr. Stein  
**Status**: operational framework (locked 2026-05-08)  
**References**: slm-learning-122, 124, 125, 126, 153-163

## The Principle: Upscaling Is Not Bigger Checkpoints

"Bigger" does not mean "train a larger checkpoint once and ship it."

Continuous upscaling means: every cycle adds **something**. More training data, harder examples, new specialist adapters, deeper reasoning capability, wider tool coverage, faster fallback, longer context, stronger distillation teachers, richer architecture. A 7B model with 12 specialists is bigger than a 32B model without composition. A 1.5B model that routes between 8 experts and calls a 32B teacher for hard cases is operationally bigger than an isolated 7B.

The operator's directive: stop deciding "small vs big" abstractly. Build the ladder.

## Three Honest Parameter Counts

Every model report must state:

1. **active_parameters_per_call**: The weights loaded into VRAM during forward pass. Example: "7B active base with 64M specialist adapter parameters loaded = 7.064B active per call."

2. **total_deployed_parameters**: Everything available in the system. Example: "7B base + 8 specialists × 256M each = 9.048B total deployed (only K=2 active per token via MoE router)."

3. **trainable_parameters_last_run**: What was actually fine-tuned in the most recent training. Example: "LoRA r=16 on 7B base = 22M trainable; 32B base QLoRA 4-bit = 45M trainable."

Use these terms precisely in all reports and Delta Graph entries. Never claim "9B model" when you mean "7B base + 2M adapter parameters." The confusion kills reproducibility and inflates claims.

## The Six-Lane Continuous Upscaling Program

### Lane 1: Adapter Graph Growth (Primary, Immediate)

**The mechanism**: Each month, train 2-4 new LoRA/QLoRA specialists on novel data or hard negatives. Compose them via router or merge. Stack increases total_deployed.

**Metrics**:
- Adapters in flight: LoRAs on HF Hub primary, pending merger tests
- Router accuracy on routing.jsonl: +pp per month
- Merge-candidate pairs identified: 3-5 ripe for testing

**2026-05 baseline**:
- tool-use-v2 (r=32)
- cli-v2 (r=16)
- doc-verifier-r16
- math-specialist (pending)

**By 2026-08 target**: 8-12 specialists, 3+ proven merge policies, router at 95%+ accuracy on owned tasks.

**Cost per specialist**: $0-5 (local) or $2-8 (Modal A10G for 7B base), zero marginal inference cost (LoRA stored on hub, loaded on-demand).

---

### Lane 2: Bigger Dense Bases as Fallback / Teacher

**The mechanism**: Maintain fallback bases at 32B and eventually 72B (on Modal, not local). Use them for:
- Teacher distillation (generate hard-example traces for 7B specialists)
- Few-shot routing when 7B underperforms
- Safety gating on critical paths
- Merge validation (does merging two 7B specialists beat the 32B baseline?)

**Metrics**:
- 32B base available on Modal: ~5s cold-start, ~1s warm
- Distillation pipeline: N hard examples → teacher CoT traces
- Fallback invocation rate: track when 7B-active refers up

**2026-05 baseline**:
- Qwen2.5-Coder-7B canonical base
- No 32B deployed yet

**By 2026-08 target**: 32B base on Modal + inference wrapper; 1000+ hard-example distillation pairs per quarter; fallback rate < 5% on owned tasks.

**Cost per quarter**: $10-15 Modal inference only; $40-60 if training a 32B delta.

---

### Lane 3: System Distills Into Smaller (Rinse-Repeat)

**The mechanism**: A 7B active system with router + fallback beats frontier on narrow lanes. Use its outputs to SFT a 3B. Use the 3B to bootstrap a 1.5B on the same lane. Ship the smallest one that passes eval gate.

**Metrics**:
- Distillation efficiency: bits per model step (smaller model learns teacher outputs at fixed cost)
- Eval laddering: 7B → 3B → 1.5B pass rate trajectory
- Param-efficiency frontier: performance per M active parameters

**2026-05 baseline**:
- 7B trained, no distillation attempted yet

**By 2026-08 target**: 3B candidate on 2 lanes; 1.5B candidate on 1 lane; shipping smallest viable model per lane.

**Cost per ladder**: $3-5 distillation + training all three tiers.

---

### Lane 4: Hard-Example Data for Stronger Bases

**The mechanism**: Mine regression journal + failed tasks → curate hard negatives → synthesize harder variants via LLM → mix into base training. Upstream data quality lifts the entire adapter stack.

**Metrics**:
- Hard-example corpus size: target 10k+ cases where eval showed failure
- Synthesis quality filter: keep top 50% by frontier-model agreement
- Regression journal size: every failed training run contributes at least 20 cases

**2026-05 baseline**:
- Regression journals populated: 5+ runs
- Hard-example synthesis: ad hoc, not systematic

**By 2026-08 target**: 5k+ hard examples mined; synthesis pipeline automated; integrated into EXP-003 (SERA trajectories).

**Cost**: $5-10 Claude haiku + Opus for synthesis per quarter.

---

### Lane 5: Function-Preserving Morphism (Tiny-First)

**The mechanism**: Start with smallest viable base (0.5B). Prove morphism (identity-initialized expansion) works at tiny scale. Then ladder: 0.5B → 1.5B → 3B → 7B, each expansion reusing prior morphism technique.

**Thesis**: Growing a trained model via insertion of identity layers + retraining costs less than training from scratch, and preserves learned features. Enables continuous upscaling without forgetting.

**Metrics**:
- Init function preservation: model(x) ≈ baseline(x) ± epsilon at initialization
- Training efficiency: cost_per_param_added relative to baseline training
- Eval lift: does post-morphism training beat re-training baseline at new size?

**2026-05 baseline**:
- No morphism prototype yet; will be EXP-009 (morphism_prototype_plan.md)

**By 2026-07 target**: 0.5B morphism validated; 1.5B morph SFT complete; morphism cost < baseline by 20%.

**By 2026-08 target**: 3B morphed from 1.5B; integrated into standard upscaling path.

**Cost per morphism**: ~50% the cost of training the target size from scratch (amortized over future ladders).

---

### Lane 6: Dense-to-MoE Upcycling (Later)

**The mechanism**: Once a dense 7B or 32B checkpoint is stable, upcycle it into MoE. Existing dense layers become expert cores; insert a learned router; retrain router + expert gates only. This is the technical path to 7B → 9B-effective (8 experts, K=2 active) without full retraining.

**Thesis**: Upcycling leverages existing knowledge while adding compositional flexibility. More experts = bigger total_deployed; fewer active = same active_parameters_per_call.

**Metrics**:
- Expert specialization: per-expert % of inference on each task class
- Router entropy: does learned router create clear expert separation?
- Eval lift: K-expert MoE vs dense baseline

**2026-05 baseline**:
- No upcycled MoE yet

**By 2026-10 target**: 1-2 stable MoE candidates; clear expert specialization (code, math, planning, reasoning, tools); proof that MoE activation aligns with task class.

**Cost per upcycle**: $3-8 Modal (training router only).

---

## Wording Rules (Mandatory)

Use these exact phrasings:

| Phrase | Meaning | Example |
|--------|---------|---------|
| "X active" | Forward-pass VRAM footprint during inference | "7B active base" or "7B base + 64M active adapter" |
| "Y total_deployed" | All parameters available to the system | "9B total_deployed across 8 specialists" |
| "Z trainable" | Last fine-tune scope | "22M trainable (LoRA r=16 on 7B)" |
| "N inference cost per call" | Wall time or USD per forward pass | "$0.0012 per call" or "125ms avg latency" |
| "spec → expert" | A specialist is always a LoRA/adapter; an expert is always MoE | "math-specialist-v2 LoRA" not "math expert" (yet) |

**Red flags** (never use):
- "7B → 9B model" (implies full retraining of larger checkpoint)
- "9B model" (unclear if active or deployed)
- "our 10B system" (conflates system size with model size)

---

## Proof Artifact: The Scaling Ledger

Every upscaling cycle produces a Delta Graph entry + Scaling Ledger row:

```json
{
  "delta_id": "coder-stage25-morphism-3b",
  "base": "Qwen2.5-Coder-1.5B",
  "morphism_method": "identity-projection-expansion",
  "active_parameters": 3_000_000_000,
  "total_deployed": 3_200_000_000,
  "trainable_parameters_last_run": 48_000_000,
  "parents": ["coder-stage25-1p5b-v2"],
  "cost_usd": 4.50,
  "wall_hours": 2.3,
  "evals": {
    "humaneval": 0.56,
    "mbpp": 0.62,
    "gad_tools": "28/30"
  },
  "ts_trained": "2026-07-15T...",
  "scaling_notes": "Morphed from 1.5B via 2 identity-projection layers; 18% training cost vs baseline; +3pp HumanEval"
}
```

The Scaling Ledger (`models/SCALING_LEDGER.jsonl`) is the durable proof that continuous upscaling happened. No entry = no cycle completed.

---

## Tying Back to Six Lanes: The Monthly Cadence

| Week | Lane | Action | Proof |
|------|------|--------|-------|
| 1 | L1 (Adapter growth) | Author + train 1-2 new specialists | LoRA on HF Hub + Delta Graph entry |
| 2 | L4 (Hard examples) | Mine regression journal; curate 500+ cases | hard_examples.jsonl committed |
| 3 | L2 (Bigger base) | Run 10 hard examples on 32B teacher; distill | distillation_pairs.jsonl |
| 4 | L3 (Distill down) | Train 3B on distillation pairs; eval | Delta Graph + evals.public |
| 5 | L5 (Morphism) | Test morphism on 3B → 5B; measure cost | morphism_cost_report.json |
| 6 | L6 (MoE upcycle) | Retrain router on existing specialists | MoE candidate Delta Graph |

By month's end: 1 new LoRA + 1 distillation cycle + 1 downward ladder rung + 1 morphism test + 1 MoE experiment = system is demonstrably bigger in at least 3 dimensions.

---

## Decision References

- **slm-learning-122**: Continuous upscaling principle (abstract)
- **slm-learning-124**: Adapter graph as primary growth mechanism
- **slm-learning-125**: Fallback systems + teacher distillation policy
- **slm-learning-126**: Hard-example mining + synthesis pipeline
- **slm-learning-153-163**: Morphism experiments (series)

## Gaps

1. **Scaling Ledger schema**: needs formal JSON schema + validation
2. **Monthly audit ritual**: need a gad task to stamp completion
3. **Morphism proof-of-concept**: depends on EXP-009 prototype completion
4. **MoE upcycling script**: router training harness not yet authored
5. **32B Modal serving**: vLLM wrapper not yet wired
