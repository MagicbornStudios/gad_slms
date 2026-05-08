# Skills as First-Class Training Artifacts

**Status**: Foundational concept document  
**Decision Refs**: slm-learning-128, slm-learning-129, slm-learning-131  
**Last Updated**: 2026-05-08

---

## What Is a Skill?

A **skill** is a reusable, domain-specific procedure that solves a repeatable problem with measurable outcomes. In slm-learning, skills are not just documentation or context—they are **first-class training artifacts** that encode domain knowledge, decision gates, and learning signals into the SLM training pipeline.

Unlike prompts (which are context-dependent) or tools (which are abstract utilities), skills are **concrete, versioned, and measurable**. A skill has a procedure, failure modes, evaluation criteria, and decision references. Over time, skills become training data—either directly (as instruction examples) or indirectly (as traces that generate preference pairs).

---

## The Six Levels of Skill Use

Skills evolve through increasing integration with the training pipeline:

### Level 1: Prompt Context
The skill is documented in text, given as context to an LLM prompt. The model may invoke the skill correctly or not, entirely dependent on token-level lottery.

**Example**: "When training a coder, validate the dataset output contract before starting."

**Cost**: Free (documentation is tiny)  
**Signal**: None (we never know if the model read it or understood)  
**Use case**: Initial skill authorship; baseline documentation

### Level 2: Trace Label
Skill invocations are tagged in execution logs and telemetry with a `trace_label` from the skill definition. Human reviewers can see when the skill fired and whether it succeeded.

**Example**: Every training run's manifest includes `"trace_labels": ["benchmark-gated-training", "gate-pass"]`

**Cost**: Minimal (add 1 JSON field per execution)  
**Signal**: Moderate (we can correlate skill invocations with downstream outcomes)  
**Use case**: Observability, pressure-signal correlation

### Level 3: SFT Data
The skill's procedure is converted into instruction-following examples and added to the training corpus. The model learns to follow the steps.

**Example**: 200 synthetically generated examples: `{"input": "You are training a coder on OCR data. What must you do before firing training?", "output": "Validate the dataset output contract..."}` from the skill's procedure steps.

**Cost**: ~1-2 hours of generation + curation per skill  
**Signal**: High (the model learns the procedure; downstream evals show if it's useful)  
**Use case**: Specializing the model for procedural reasoning in the domain

### Level 4: Execution Trace
Live execution of the skill produces a detailed trace: input state → step 1 → step 2 → ... → output state. These traces become training data showing the model the actual procedure, with intermediate states, errors, and recoveries.

**Example**: A real training run's full log: "Validator ran on dataset: 98% contract match → proceed. 1.5B probe trained: HE 20/50 → acceptable. LoRA trained on 3B: HE 40/50 → lift observed. Decision: promote to 7B eval."

**Cost**: Intrinsic (traces are byproducts of skill execution)  
**Signal**: Very High (the model sees both success and failure paths)  
**Use case**: Teaching the model when and how to apply the skill in context

### Level 5: Preference Data
Executed traces are compared: successful invocations vs. failed ones, or different variants of the same procedure. The differences are labeled as preference pairs (chosen vs. rejected).

**Example**: Two 7B coder LoRA training runs: one with output-contract validation (HE +8pp, MBPP +3pp) vs. one without (HE -34pp, MBPP -5pp). The validated run is **chosen**, the unvalidated run is **rejected**. The model learns the contrast: validation prevents catastrophic regression.

**Cost**: Requires 2+ variants; automated via `preference_pair_policy` field  
**Signal**: Highest (the model learns the causal path, not just the procedure)  
**Use case**: Aligning the model's values; DPO training

### Level 6: Skill-as-Token
The skill itself becomes a learned token or routing decision in the model's weights. Rather than executing procedurally, the model recognizes "this situation requires the benchmark-gated-training skill" and implicitly follows the procedure (learned in its weights).

**Example**: A frontier model sees "we have a new coder candidate; before promoting to 32B, we should..." and the model's decision routing automatically selects the benchmark-gated-training pathway, skipping the explicit steps because they're baked into the model's representations.

**Cost**: Very High (requires training/fine-tuning; depends on level 5 foundation)  
**Signal**: Maximum (the model has internalized the skill as knowledge)  
**Use case**: Long-term model evolution; moving fast at inference

---

## Skill → Gene → Phenotype → Fitness: The DNA Framing

Skills are like **genes** in a population:

- **Gene** = the skill definition (skill.yaml)
- **Phenotype** = a trace of the skill being executed (the log, the outputs, the states)
- **Fitness** = the evaluation metrics that measure whether the phenotype succeeded

The skill definition encodes the "intent" (the procedure should be followed). The execution trace shows the "realization" (what actually happened). The eval metrics show the "fitness" (did it work?).

Over generations (training runs), skills that produce high-fitness phenotypes are selected, refined, and incorporated into the model's weights. Skills that produce low-fitness phenotypes are abandoned or redesigned.

---

## How a Skill Becomes Training Data

```
Skill authored              Skill versioned                Traces collected         SFT data mined
(skill.yaml)        →       (schema validated)    →        (real runs)       →      (instruction pairs)
                                                                                            ↓
Preference pairs            DPO training                  Model learns                Model routes implicitly
mined from traces     →      on chosen/rejected    →       causality              →    (level 6)
(contrast learning)         pairs
```

**Timeline example: benchmark-gated-training**

1. **Authorship (2026-05-08)**: Skill definition written based on actual decisions slm-learning-097, 103, 107, 108, 110.
2. **Versioning (2026-05-08)**: Schema validated; examples added from this session's fn_norm 1.5B success, fn_norm 7B failure, tooluse-v2 contract mismatch.
3. **Traces (2026-05-08 onwards)**: Every training run logs its procedure step-by-step. If it invokes `benchmark-gated-training`, the trace is labeled and stored.
4. **SFT mining (phase 05)**: 200-500 instruction examples generated from traces + skill procedure. Model learns: "When you see 'new coder candidate', run these 8 steps in order."
5. **Preference mining (phase 05)**: Pair up successful runs (gate-pass) with failed runs (gate-fail). Extract contrasts. Model learns: "Contracts matter; evals matter; loss alone does not."
6. **DPO training (phase 06)**: Retrain model on preference pairs. Model learns the **why** behind the procedure—the causal path from validation → eval → decision.
7. **Token routing (phase 07+)**: Over 2-3 full retraining cycles, the skill procedure becomes implicit in the model's weights. By then, frontier models will have a routing layer that selects this skill automatically.

---

## When to Author a Skill (And When Not To)

**Author a skill IF:**
- ✓ The procedure **repeats** in the codebase (appears in 2+ commits or decision records)
- ✓ Outcomes are **measurable** (eval lift, contract pass, decision logged)
- ✓ Failure modes are **identifiable** (we can point to what goes wrong)
- ✓ It **encodes domain knowledge** (the procedure is non-obvious; a frontier model wouldn't know it)

**Do NOT author a skill if:**
- ✗ The procedure is one-off (happens once; unlikely to repeat)
- ✗ Outcomes are invisible or mixed (no clear pass/fail)
- ✗ It's just a tool wrapper (skills are higher-level; use tools for CLI operations)
- ✗ It's common sense (a frontier model already knows this; no learning signal)

---

## Cross-Links and Pressure Mechanics

### Skill Pressure and Evolution
See **`reports/research/skill_pressure_evolution_signal.md`** for the framework that correlates skill invocations with downstream learning signals (eval lift, decision logged, commits, handoffs completed).

The metric:
```
net_signal_score = (eval_lift × 0.4 + decisions × 0.3 + commits × 0.2 + handoffs × 0.1) / invocations
```

Skills with score > 0.5 are **high-signal accelerators** worth investing in. Skills with score < 0.1 are **eviction candidates**.

### Pressure Formula Calibration
**`reports/research/pressure_formula_calibration.md`** (being written this turn) documents the tuning of the signal weights. Example: should eval_lift weight be 0.4 or 0.5? If a skill correlates with decision logging but never with eval lift, is that high-pressure or low-pressure? The calibration document is the formal answer.

### Training Decisions
- **slm-learning-128**: Skills must generate measurable learning signal or be shedded
- **slm-learning-129**: Multi-project skill portfolio strategy (which skills drive value universally? which are domain-specific?)
- **slm-learning-131** (TBD): Skill versioning and deprecation policy

---

## The First Canonical Skill: benchmark-gated-training

The first skill we author is **`benchmark-gated-training`** because we just lived through it this session:

- The fn_norm 1.5B success (HE +6.7pp, MBPP +3.0pp) shows the procedure can work
- The fn_norm 7B failure (HE -34pp, MBPP -5pp despite clean loss curve) shows why the gate matters
- The tooluse-v2 contract mismatch shows what happens when you skip validation
- Four decision records justify it: slm-learning-097, 103, 107, 108, 110, 113, 119, 126

This skill is the foundation for all future scaling decisions. See `skills/benchmark-gated-training.skill.yaml`.

---

## Success Criteria for This Infrastructure

- [ ] skill.schema.json validates all skill definitions (3 example skills pass)
- [ ] First canonical skill (benchmark-gated-training) captures actual procedure faithfully
- [ ] Skill traces can be annotated in training runs (new `trace_labels` field)
- [ ] SFT mining script can extract 200+ instruction pairs from existing decision records
- [ ] Preference pairs from contrasts (successful vs. failed invocations) can be mined
- [ ] Phase 05 DPO training can consume preference pairs and improve decision-routing eval
- [ ] Multi-project skill registry (phase 08+) starts with this 3-file foundation

---

## References

- `schemas/skill.schema.json` — JSON Schema for skill definitions
- `skills/benchmark-gated-training.skill.yaml` — First canonical skill
- `reports/research/skill_pressure_evolution_signal.md` — Pressure signal framework
- `reports/research/pressure_formula_calibration.md` — Weight tuning for correlation metric
- **slm-learning-128**: Skills must generate measurable learning signal
- **slm-learning-129**: Multi-project skill portfolio strategy
- **slm-learning-097**: Two-shot $50 discipline (benchmark-gated scaling)
- **slm-learning-103**: Compare-and-compete discipline (model promotion gates)
- **slm-learning-107**: Benchmark-gated scaling (32B requires public-benchmark lift at 7B)
- **slm-learning-108**: Output contracts mandatory (dataset validation before training)
- **slm-learning-110**: fn_normalized OCR is 1.5B benefit, not scale recipe
- **slm-learning-113**: fn_normalized OCR is a 1.5B benefit not a scale recipe (7B gate fail)
- **slm-learning-119**: Tooluse-v2 contract-mismatch finding (natural_language vs gad_cli_command)
- **slm-learning-126**: Contract validator blocks training (strict match < 95%)

---

**End of Document**

This document establishes the conceptual foundation. The two companion files (schema + canonical skill) translate this into executable artifacts.
