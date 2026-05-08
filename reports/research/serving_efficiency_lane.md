# Serving Efficiency Lane (Lane D)

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Decision refs:** slm-learning-095 (comparator floor),
slm-learning-103 (compare-and-compete), slm-learning-121
(system-level MoE), slm-learning-124 (system-as-teacher),
slm-learning-125 (cost-per-successful-task),
slm-learning-156 (adapter-level MoE),
slm-learning-190 (training-cost optimization is a separate
lane), slm-learning-193 (souls become houses).
**Companion:** `reports/research/pressure_to_training_research_agenda.md`
(Q13a-d), `reports/research/souls_houses_factions_framework.md` (the routes)

---

## Why this lane exists

We have:

| Asset | State |
|---|---|
| Stein-house 1.5B canonical | adapter on Modal volume + MANIFEST |
| Stein-house 7B canonical | adapter on Modal volume + MANIFEST |
| Kael-house planned | dataset pipeline TBD |
| Verifier-house r=16 | adapter on Modal volume |

We DON'T have:

| Gap | Impact |
|---|---|
| vLLM multi-LoRA serve | adapters can't be requested per-call from a hosted endpoint |
| Per-request adapter routing | router can't pick Stein-vs-Verifier-vs-Kael per request |
| Speculative decoding | 1.5B draft accelerating 7B is untested; could 2-3× throughput |
| RadixAttention prefix caching | shared-instruction prefix (the context_root) cached once across all packets |
| Quantized fallback | int8 32B vs always-on 7B: $/successful-task unknown |
| Cost-per-successful-task matrix | we cite $0.0037/pp on training; serving cost is unmeasured |

This lane closes those gaps.

---

## The serving stack we're committing to

### vLLM (primary)

**Use for:** the standard serving path. Multi-LoRA per-request
routing per `slm-learning-156` (adapter-level MoE is the first
practical architecture upscaler).

vLLM supports per-request LoRA adapter selection out of the box
(`lora_request` field in completion API). One base model, N
adapters loaded at startup, router picks adapter per call.

Implication for the houses framework: every promoted house
adapter goes into one vLLM instance per `(base, gpu)` cell. Router
picks per request based on task shape.

### SGLang (secondary, advanced)

**Use for:** high-throughput Kael trajectory inference where
RadixAttention prefix caching matters. The `context_root.shared_instruction`
is repeated across many delta packet calls — RadixAttention caches
it once at the prefill, saving compute on subsequent calls.

Also: SGLang's speculative decoding (EAGLE-2/3, n-gram, draft-model)
is what we test for the 1.5B-draft-accelerating-7B hypothesis.

### Unsloth (training-side, evaluation only)

**Use for:** benchmark Modal SFTTrainer vs Unsloth on the same
1.5B+hard+retain config. If Unsloth is meaningfully faster /
cheaper at the same loss, switch the canonical training path.
Until benchmarked, no claim.

### Modal (infrastructure)

**Use for:** all of the above, hosted. Modal already mounts our
volumes (`slm-data`, `slm-models`) and runs A10G/A100 with
secrets. The vLLM and SGLang serving paths are Modal `@app.function`
wrappers.

---

## Concrete deliverables

### D1 — vLLM multi-LoRA Modal app

**File:** `modal_app/serve_vllm_multi_lora.py` (already exists in
skeleton form per `serve_vllm.py`; extend to multi-adapter).

**Endpoints:**
- `POST /v1/chat/completions` — OpenAI-compat with `lora_request: <adapter_id>`
- `GET /adapters` — list loaded adapters
- `POST /adapters/load` — hot-load a new adapter from `/models/runs/<run_id>/adapter`

**Adapters loaded at startup:** all `promotion_status: canonical`
entries from `reports/scaling/gad_scaling_ledger.json`.

### D2 — Cost-per-successful-task harness

**File:** `scripts/eval/cost_per_successful_task.py` (new).

Wraps any benchmark (HE/MBPP/escape-the-dungeon trajectory). For each
candidate (base + LoRA, base + Variant A, base alone, frontier model),
measure:

```
cost_per_success = (training_cost_amortized + serving_cost_per_call * n_calls) /
                   (n_correct - n_correct_baseline)
```

Output: `reports/serving/cost_per_successful_task_<date>.md`.

**This is the metric the charter Row 3 + slm-learning-125 is built around.**

### D3 — Speculative decoding smoke

**File:** `modal_app/serve_sglang_speculative.py` (new).

7B base + 1.5B draft. Run HE n=20 against 7B-greedy and
7B-with-1.5B-draft-speculative. Measure tokens/sec + accuracy.

If accuracy parity within ±0.5pp AND tokens/sec ≥1.5×, speculative
becomes the canonical Kael serving path.

### D4 — Frontier comparator via Gemini-cli

Already filed: `h-2026-05-08T12-30-00-monorepo-gemini-frontier-comparator.md`.
The monorepo team's gemini-cli quota holder picks up the script;
slm-learning agg
regates the JSON when it lands.

### D5 — Kael route — the flagship

**File:** `modal_app/serve_kael.py` (new).

A vLLM endpoint that:
- Loads the highest-priority Kael-house adapter
- Falls back to Stein-house code-completion if Kael-house lacks
  the task shape
- Falls back to bare 7B base if both house adapters miss
- Logs every fallback as a pressure event for next consolidation

This is the **public Kael route** that competes with ChatGPT/Claude
Opus on UX + outcome.

---

## Pricing baselines (Modal as of 2026-05)

| GPU | $/hr | Notes |
|---|---|---|
| L4 | $0.55 | smallest; serving 1.5B |
| A10G | $0.83 | training small + serving 7B |
| A100-40GB | $4.00 | 7B-with-multi-LoRA serve |
| A100-80GB | $6.00 | 32B serve |
| H100 | $9.00 | 32B training |

These rates are baked into `scripts/morphism/aggregate_*.py`
cost estimates already.

---

## Acceptance test for this lane

When all 5 deliverables ship:

1. `modal run modal_app/serve_vllm_multi_lora.py` boots an endpoint
   serving Stein-house 1.5B + Verifier r=16 + (eventually) Kael-house.
2. `python scripts/eval/cost_per_successful_task.py
       --benchmark humaneval --candidates base,1p5b-hard-retain,7b-hard
       --max-spend-usd 1`
   produces a cost-per-success row per candidate.
3. The frontier comparator handoff returns Gemini scores; the row
   slots into the same harness.
4. The Kael route serves at least 1 task end-to-end, with a
   fallback logged on a deliberate edge case.
5. Cost-per-successful-task table is published to
   `reports/serving/cost_per_successful_task_<date>.md`.

---

## Decision proposed: slm-learning-194

> **Serving efficiency is Lane D and is now first-class.** vLLM
> multi-LoRA is the default serve path; SGLang is the
> high-throughput Kael route with speculative decoding + RadixAttention
> prefix caching. Cost-per-successful-task replaces $/pp-lift as the
> primary metric for promotion-from-staging-to-canonical decisions
> ($/pp-lift remains the training-side metric). The 5 deliverables
> above are the lane's first cycle.

---

## Open questions queued

1. Multi-LoRA batching cost — how much overhead per loaded adapter?
2. Quantized 32B fallback — int4 vs int8 — accuracy delta?
3. Speculative decoding accuracy preservation across diverse
   prompts (not just HE)?
4. RadixAttention cache eviction policy when retain bank rotates
   weekly?
5. Per-house route priority — does Kael always preempt Stein, or
   negotiate by task shape?

— Dr. Stein, serving efficiency lane, 2026-05-08
