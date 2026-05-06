# Constitution Impact

## Status

`open-hypothesis`

## Owned by

Dr. Stein

## Definition

We accepted souls as operational constitutions (decisions
`slm-learning-044..048`). This concern tracks the open empirical
question: **does the constitution actually change anything we can
measure?**

Two sub-hypotheses:

### H1 — Training-time effect

Training Dr. Stein 1.5B with soul-aligned prompts (system + user
preamble drawn from the constitution) produces a measurably different
model than training the same base on the same data without the
constitution. Effect can be on:

- training speed (loss curve, time-to-convergence)
- output quality on bounded GAD tasks (tool-use, doc-verify, hypothesis
  formulation)
- output discipline (does the trained model emit the Dr. Stein output
  schema spontaneously?)
- failure modes (does it overstate less? does it ask for cheaper
  tests more often?)

### H2 — Project-evolution effect

Projects (or phases) that operate under explicit soul/constitution
prompting evolve differently from those that don't. Measured by:

- number of decisions logged per phase
- number of skeletons interred (failures preserved as evidence)
- promotion-gate pass rate
- rework rate (how often a decision is reversed)
- artifact survival rate over N phases

## Why this is open and not settled

A constitution can look good on paper and have zero downstream
behavior signal. We have to test. The cost of a wrong constitution
that nobody notices is: weeks of self-flattery dressed as discipline.

## Proposed experiment (pending D5)

| Arm | Setup | Cost |
|---|---|---|
| A (control) | Qwen2.5-1.5B-Instruct + existing GAD-tools pairs | already done |
| B (constitution-on) | same base + same data + soul-injected system prompt during SFT | ~1 GPU-day |
| C (constitution-on, eval-only) | A's model, B's prompt at inference time | ~hours |

C lets us isolate the prompt-time effect from the training-time
effect. If C delivers most of B's gain, the constitution should stay
in prompt and not be baked yet (consistent with decision
`slm-learning-047`). If B beats C, baking is justified eventually.

## Project-evolution measurement (pending D6)

We need a primary signal for "evolutionary step." Candidates:

- phase complete (coarse, slow)
- decision logged (finer, but volume varies)
- skeleton interred (rare, high-information)
- skill promoted (rare, very high-information)
- pressure point closed (currently fuzzy)

Per the GAD evolution loop, pressure points + promotion events are
the natural high-information signals. A simple metric: **promotions
per N decisions**, tracked over time, with constitution-on vs
constitution-off as conditions.

## Pending decisions

| ID | Question |
|---|---|
| D5 | Run the A/B/C experiment? |
| D6 | What counts as the primary "evolutionary step" signal? |

## References

- decisions `slm-learning-044..048` — soul system
- decision `slm-learning-032` — promotion gate (selection pressure)
- decision `slm-learning-047` — soul-first prompting; this concern
  is the test of that decision's premise
