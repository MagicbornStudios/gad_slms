# Teacher species policy

**Date:** 2026-05-08
**Owner:** Dr. Stein (slm-learning)
**Decision refs:** slm-learning-197 (Opus is THE teacher; open Qwen
is comparator/labeler/inspector, not teacher rival), slm-learning-198
(registry as first-class artifact), slm-learning-199 (Kael's moat is
integration depth × speed × cost, not benchmark parity).

This is the operating articulation of the teacher policy table at
`data/registry/teachers.json` (schema: `schemas/teacher_policy.schema.json`).
A ChatGPT-paired discussion proposed treating high-end open Qwen as a
"teacher" peer to Claude Opus. The proposal conflated four distinct
roles. This doc names them and binds the program to the cleanest split.

## 1. The conflation

The proposal said: "Use Claude Opus when we need best judgment. Use
high-end Qwen when we need open-weight, repeatable, same-family,
long-context, distillable teaching."

That single word "teaching" was the conflation. It welded together:

- **Teacher** — the model that produces the gold label, the standard
  the student is trying to match.
- **Bulk labeler** — the model that produces *a lot* of labels cheaply,
  with quality good enough but not best-in-class.
- **Backbone** — the model the student is *built from*. The student's
  parent body, not its parent mind.
- **Truth (verifier)** — the strictest signal of all: tests, executors,
  contract checkers. They have no opinion, only outcome.
- **Inspector** — a model whose internals (logits, hidden states,
  attention) we can probe, because we have its weights.
- **Comparator** — a model we score against to make a paper-row claim
  reproducible by anyone.

These are not synonyms. They are six different roles, sometimes filled
by the same model, sometimes not. Calling all of them "teacher"
collapses the planning surface.

## 2. The honest assignment

| Role | Best fit (today) | Why |
|---|---|---|
| Teacher | **Claude Opus 4.5** | Strongest agentic reasoning + coding judge available; sets Kael's quality ceiling on hard tasks. |
| Premium teacher (fallback) | Claude Sonnet 4.6 | Cheaper than Opus; close on most code/repair. Use when Opus is rate-limited or when row volume scales. |
| Bulk labeler | Claude Haiku 4.5 (paraphrase, easy rows) ; Qwen2.5-Coder-32B-Instruct (offline/Modal) ; Qwen3-Next-80B-A3B (long context) | Cheap-per-row; quality good enough for consolidation/augmentation; same-family with Qwen students for distillation cleanliness. |
| Backbone (the body, not the mind) | Qwen2.5-Coder-{1.5,3,7,14}B-Instruct | Already chosen. Open Apache-2.0. Kael lives in the 7B body. |
| Truth (verifier) | HumanEval+ test suite, executor sandboxes, JSON schema validators, contract runners | Beats every model. The strictest teacher of all. |
| Inspector | Qwen2.5-Coder-7B-Instruct (same family) ; Qwen3-Next-80B-A3B-Instruct (long context) | Open weights only. Required for logit/hidden-state work. |
| Comparator | Qwen2.5-Coder-7B/32B, DeepSeek-R1-Distill, gpt-oss-20b/120b, Llama-3.3-70B-Instruct (free OpenRouter), Phi-4 | Open weights → reproducible. Charter Row 8 paper rows. |

## 3. Why open Qwen is NOT a teacher rival to Opus

Claude Opus 4.5 is positioned by Anthropic at coding, agents, and
computer-use, with API pricing at $5/$25 per Mtok input/output. It's
the strongest available signal on hard reasoning. We use it as a
teacher because we want max quality flowing into Kael's training data.

Qwen3-Next-80B-A3B-Instruct is Apache-2.0, ~80B total / ~3.9B active
hybrid Transformer-Mamba MoE with 262K native context. It's strong,
but it does not match Opus on the hardest agentic reasoning rows. It
fills three different roles where Opus does NOT compete:

1. **Bulk-labeling at scale** — we can host it on Modal H100 and label
   1M rows for the marginal cost of compute, vs. Anthropic API tokens.
2. **Logit/hidden-state inspection** — Opus's weights are closed. We
   physically cannot probe its internals. For research questions that
   require this, Qwen-Next is a teacher; Opus is not.
3. **Reproducible paper rows** — Charter Row 8 needs a comparator any
   peer can rerun. A closed API row is not that.

These are real, valuable roles. They are not the same role as "produces
the gold label that Kael is trying to match."

## 4. What about same-family transfer?

The proposal also argued: "Qwen high-end teacher distills into Qwen
students more cleanly because same tokenizer, same conventions."

This is a **hypothesis worth testing**, not a settled belief. Same-family
distillation has been shown to reduce KL divergence in preliminary work
on smaller scales, but for Kael's actual moat (agentic loops, tool
correctness, GAD-domain mastery) the gold label quality dominates the
tokenizer match. We will test it directly:

> **EXP-pending — same-family distillation arm.** Two arms: (a) Kael-7B
> SFT'd on Opus-generated function-completion rows. (b) Kael-7B SFT'd on
> Qwen2.5-Coder-32B-generated rows of the same prompts. Hold all else
> equal. Score on HE/MBPP/HE+/MBPP+, BFCL tool-action, and the Kael-house
> trajectory eval. If (b) wins by ≥2pp at 30% the cost, escalate Qwen-32B
> to "active_teacher" for that task shape. Otherwise the policy stands.

Until that experiment fires and lands, the policy is: **Opus is the
teacher; open Qwen is bulk_labeler + comparator + inspector.**

## 5. What "max Kael" means

A 7-14B model **will not** match Opus on hard agentic reasoning. That's
a math fact about parameter count + training compute. Trying to close
that gap on benchmark scores is the wrong target.

Kael's moat is integration depth × speed × cost:

| Axis | Concrete measure |
|---|---|
| **Routing** | "Local-vs-escalate" decision quality. Kael handles 80% locally and escalates 20% to Opus with a clean handoff. Score: % of correctly-routed turns. |
| **Tool-action reliability** | Clean JSON emissions, no hallucinated CLI surfaces. Score: BFCL + GAD-tools owned-domain row. |
| **GAD-domain mastery** | Knows planning docs, decisions, handoff lifecycle, gad CLI cold. Score: GAD-tools owned-domain eval (Charter Row 7). |
| **Speed × cost** | Order of magnitude faster + cheaper than Opus. Score: cost-per-successful-task (Lane D D2). |
| **Agentic loops** | Multi-turn self-correction with verifier feedback. Score: trajectory eval (Kael-house dataset, in flight). |
| **Continual learning** | Every Opus escalation becomes the next Kael's training data. Score: month-over-month escalation rate trend. |

Stein-house 7B canonical at HE/MBPP 84.8/82.3 is already strong; further
gains on those benchmarks are diminishing returns. The big wins come
from the rows above — agentic-loop training under hybrid runtime
(slm-learning-168), not raw HumanEval lift.

## 6. Provenance contract for teacher rows

Per slm-learning-204 (proposed), every teacher-generated training row
must track:

```json
{
  "teacher_model": "claude-opus-4-5",
  "task_shape": "code_function_completion",
  "cost_usd": 0.012,
  "latency_seconds": 3.4,
  "output_contract": "function_definition",
  "accepted_by": "verifier|human|frontier_panel",
  "license_status": "anthropic_tos_review_passed_2026-05-08",
  "row_id": "...",
  "decision_refs": ["slm-learning-197"]
}
```

`accepted_by` is the most important field. A row labeled by Opus that
fails a verifier is NOT a teacher row — it's a row the verifier
overruled. Train on it as a *negative* sample if you want, but don't
treat it as gold.

## 7. Open research questions

Logged for future experiments:

1. **Same-family distillation** — does Qwen-32B teacher beat Opus
   teacher on Kael-7B student on a per-dollar basis? (See §4.)
2. **Teacher disagreement** — when Opus and Qwen-32B disagree on a row,
   is the row higher-value? Use disagreement as an active-learning
   selector.
3. **Verifier saturation** — at what point does adding more
   verifier-passed Opus rows stop improving Kael? (Diminishing returns
   detector for the data side.)
4. **Bulk-labeler quality floor** — how low can the teacher quality go
   before consolidation rows hurt instead of help? (We've seen this at
   1.5B with Variant A asymmetric per slm-learning-185 — analogous on
   the data side?)

— Dr. Stein, teacher species policy, 2026-05-08
