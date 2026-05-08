---
id: h-2026-05-08T12-30-00-monorepo-gemini-frontier-comparator
projectid: slm-learning
phase: 04
task_id: SL-T-04-frontier-comparator
created_at: 2026-05-08T12:30:00.000Z
created_by: dr-stein-slm-learning
claimed_by:
claimed_at:
completed_at:
priority: high
estimated_context: bounded
risk: safe
time: standard
surface: cross-project
runtime_preference: gemini-cli
recipient: monorepo / platform team dispatcher (gemini-cli quota holder)
---

# Cross-project handoff — Run frontier comparator via gemini-cli quota

From: Dr. Stein, slm-learning root
To: monorepo / platform team's dispatcher (gemini-cli runtime owner)
Why: slm-learning has a `slm-learning-103`-mandated frontier comparator
row that's been blocking the scaling-proof charter (`slm-learning-164`).
Anthropic credit on the slm-learning operator's account ran out
mid-test (frontier_comparator killed at case 67 with 400
"credit balance too low"). OpenRouter free tier rate-limits unusable
(0/5 valid completions even with 5s exponential backoff).

Operator instruction 2026-05-08: "gemini has a full fucking quota
with our monorepo teams accounts." → fire the comparator through that
runtime.

## What slm-learning has prepared

**Comparator script** (read-to-run):
`scripts/eval/frontier_comparator.py` — supports
`anthropic:<model>` and `openrouter:<vendor/model[:tag]>` backends.
**Needs a third backend** (`gemini-cli:<model>` or
`google:<model>`) added. The judge (HumanEval / MBPP code-execution)
mirrors `modal_app/eval_adapter.py` exactly so results land in
identical JSON schema.

**Targets** (per `slm-learning-095` comparator floor):
1. **gemini-2.0-flash** (or whichever Gemini class the team has
   highest quota on) — primary frontier comparator
2. **gemini-2.5-pro** if quota allows — strongest comparator
3. *(optional)* claude-cli class if the team also holds Anthropic credit
4. *(optional)* OpenRouter llama-3.3-70b-instruct:free with
   appropriate inter-request pacing (we measured the free tier as
   needing >15s/request; our `pace_delay=3.5s` was insufficient)

**Benchmarks** (n=164 each, chat-mode, temp=0.0, EOS early-stop,
10s subprocess timeout):
- HumanEval (`openai/openai_humaneval` test split)
- MBPP (`google-research-datasets/mbpp` sanitized test split)

**Output target**:
- `reports/comparators/2026-05-08/<benchmark>_chat_<model>_n164.json`
- Schema mirrors `modal_app/eval_adapter.py` persist output (so
  downstream aggregation works identically)

## Acceptance test

After this handoff lands, the slm-learning aggregator should be able
to populate the **frontier comparator row** of the
`scaling_proof_charter.md` Row-8 table with:

| Model | HE pass@1 | MBPP pass@1 |
|---|---|---|
| Gemini-2.0-Flash | ? | ? |
| Gemini-2.5-Pro | ? | ? |

and contrast against our 1.5B+retain canonical (HE 64.0% / MBPP 64.0%),
7B+hard canonical (HE 84.8% / MBPP 82.3%).

## Why this matters now

The headline scaling-proof claim is "cheap gap-targeted adapters on
existing open bases reach scores that retraining a same-or-larger
base from scratch would have to spend at least 1000× more to match."
**That claim cannot survive review without the frontier row.** A
Gemini-2.0-Flash or 2.5-Pro pass@1 on HE/MBPP is the right ceiling
to compare against — modern frontier on cheap tier vs. our $0.034
adapter on a 1.5B base.

## What slm-learning will do once results land

1. Drop the comparator JSONs into `reports/comparators/2026-05-08/`
2. Run `scripts/morphism/aggregate_1p5b_ladder.py` (or a successor
   that includes the frontier row)
3. Update `reports/research/scaling_proof_charter.md` Row 8 with
   real numbers
4. Log a decision (slm-learning-175 or later) crediting this
   handoff and recording the comparator gap

## Cross-references

- `reports/research/scaling_proof_charter.md` — Row 8 (frontier comparator)
- `slm-learning-095` — comparator floor: Big Pickle / Llama-3.3-70B / Nemotron
- `slm-learning-103` — compare-and-compete (4-row matrix; this is row 2)
- `slm-learning-164` — scaling-proof charter pre-registered with this row marked open
- `scripts/eval/frontier_comparator.py` — ready-to-extend script
- `scripts/eval/_load_env.py` — BOM-aware .env loader (utf-8-sig)
- Modal secret `gad-api-keys` — currently holds OPENROUTER_API_KEY
  + (depleted) ANTHROPIC_API_KEY; team can add GEMINI_API_KEY or
  team-credentials path

## Non-blocking but priority

This is **not blocking** the slm-learning ladder work — we have
~$10 of Modal credit remaining and can keep firing arms (Variant B
+ retain-mix, 3B + 7B-hard transfer, late-layer Variant A). But
the scaling-proof charter is incomplete without the frontier row,
and that row is what makes the paper claim defensible.

— Dr. Stein, 2026-05-08
