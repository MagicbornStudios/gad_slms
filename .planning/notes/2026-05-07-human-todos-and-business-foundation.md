---
title: Human TODOs — funding outreach, business setup, and pitch foundation
date: 2026-05-07
agent: dr-stein
project: slm-learning
status: open
tags: [human-todo, funding, business, pitch, ops]
---

# Human TODOs — funding, business setup, and "why we need a business"

This note is the durable home for the work only the operator can do.
Code-side work is handled by Dr. Stein (this repo) and the monorepo
team. Everything below requires the operator's hands or signature.

Reference docs that already exist — read these first, don't duplicate
their content here:

- `.planning/notes/2026-05-07-credit-acquisition-playbook.md` — the
  ranked apply-list with boilerplate per program.
- `.planning/notes/2026-05-07-overnight-results-brief.md` — the
  numbers backing the pitch (30/30 vs 24/30 vs claude-cli at $0/call).
- `.planning/concerns/research-program-charter.md` — the operating
  constitution (lane discipline, comparator floors).

## 1 — Funding outreach (ranked by time-to-funds)

| # | Program | Effort | Entity required? | Owner action |
|---|---|---|---|---|
| 1 | NVIDIA Inception | ~10 min | No | Submit via https://www.nvidia.com/en-us/startups/ |
| 2 | Modal startup credits | ~15 min | No | Email `founders@modal.com` — boilerplate in playbook |
| 3 | HF research credits | ~20 min | No | https://huggingface.co/contact-research |
| 4 | AWS Activate / Azure for Startups / GCP for Startups | ~1 hr each | YES | Blocked on entity filing (#5 below) |
| 5 | Anthropic / OpenAI startup programs (if/when announced) | TBD | YES | Blocked on entity |

**Single highest-leverage action: file the entity.** Steps 1–3 fund
the runway right now (≤1 hr of operator time). Step 4 unlocks the big
multipliers but is gated on entity.

## 2 — Business setup checklist

| Item | Why it matters | Status |
|---|---|---|
| File entity (Delaware C-corp or Wyoming LLC) | Unlocks startup tiers + investor due-diligence + business banking | open |
| Business email on a real domain (`magicbornstudios.com` or new) | Required for credit programs + investor intros + customer trust | open |
| EIN | Required for entity bank account + payroll if/when | open |
| Business bank (Mercury / Brex) | Separates personal $ from business $; required for credit programs | open |
| Bookkeeping baseline (one-person stack: Mercury + Wave/QuickBooks) | Runway tracking + tax prep | open |
| Trademark check on "Magicborn" / "Dr. Stein" / "Kael" / "GAD" | Defensive; cheap to check, expensive to ignore later | open |

This list is operator-only. Do not delegate to Dr. Stein.

## 3 — Cost analysis (current burn vs runway)

Latest snapshot from the overnight brief:

| Bucket | Spent (overnight) | Notes |
|---|---|---|
| Modal compute | ~$4.50–6.00 | Within $30 budget |
| HF / OpenRouter / Claude API | $0 (free tier so far) | claude-cli is local-headed |
| Local hardware | sunk | 1660 Ti, no marginal cost |

**Implication:** at current cadence, Modal credits ($30 batch) buy
~5–6 ladder smokes + a $50 32B shot still leaves headroom. After
NVIDIA/Modal/HF credits land we have effectively unlimited training
budget for the next 6–8 weeks. The bottleneck is operator-hours and
public-benchmark wiring, not GPU $.

The $50 32B shot remains gated on the public-benchmark row landing
(decision `slm-learning-103`).

## 4 — "Why we need a business going forward" — pitch foundation

Three lines, drafted here so they don't drift:

> **Wedge** — Repo-native agent intelligence + artifact generation +
> continuous delta learning. We don't beat the frontier on general
> intelligence first; we beat them on owned-domain workflows the
> generic models will never specialize for.

> **Proof point (existing, today)** — `ours-via-modal-v2` scores 30/30
> on `gad_tools_v2` versus claude-cli's 24/30 at $0 per call. That is
> a real frontier-comparator row, not a vibe.

> **What funding unlocks** — Public-benchmark coverage (HumanEval,
> MBPP, SWE-bench Verified) so our owned-domain win is paired with a
> credible public score; a $50 32B-coder run that the scaling-ladder
> already predicts will lift code_smoke another ~10pp; the Kael
> desktop product as the customer-facing surface.

This is the seed of the deck. Operator decides whether to harden it
into slides now or wait for the public-benchmark row.

## Open questions for the operator

1. Pick the entity jurisdiction (Delaware C-corp vs Wyoming LLC vs DC
   single-member). C-corp is investor-default; LLC is cheaper and
   simpler if revenue-first.
2. Pick the business domain. Reuse `magicbornstudios.com` or register
   a new one for the agent product (`gad.dev`, `kael.app`, etc.)?
3. Pick the dispatcher-soul name (handoff to monorepo team flags this
   too). Candidate set: **Marshal**, **Quartermaster**, **Ferryman**.
   Dr. Stein recommends **Marshal**.

— Dr. Stein
