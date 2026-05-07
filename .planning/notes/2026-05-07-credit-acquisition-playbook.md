# Credit acquisition playbook — fastest wins first

## Why this exists

Per slm-learning-098, our $50-shot budget needs to grow. Most credit
programs require either (a) just an application or (b) a company entity
the user is filing tomorrow. Ranked by time-to-funds.

## TIER 1 — Apply this week, no entity required, fast turnaround

| Program | Amount | Time to funds | Application surface | Notes |
|---|---|---|---|---|
| **NVIDIA Inception** | DGX Cloud free hours + tech support + co-marketing | 1-7 days approval | https://www.nvidia.com/en-us/startups/ — application form | NO equity, NO entity required for individual researcher tier; mention "open coding-agent research" |
| **Modal startup credits** | up to $5k typically | 1-3 days | email founders@modal.com | Pitch: indie ML researcher, $30 starting balance, scaling to 32B class fine-tune; will publish results |
| **Hugging Face research credits** | variable (Spaces, datasets, inference, GPU) | 1-2 weeks | https://huggingface.co/contact-research or DM @ClemDelangue / @Thomas_wolf | Frame as open research; commit to publishing model + paper on Hub |
| **Anthropic developer credits** | $5-50 starter (already $0) | days | https://console.anthropic.com/billing | For distillation teacher (haiku); we use Claude API minimally already |
| **OpenAI dev tier** | none typically; pay-as-go | n/a | n/a | Skip unless we have specific need |
| **Lambda Labs / RunPod / Vast.ai** | spot pricing — much cheaper than Modal for ad-hoc | instant | sign up, $5 deposit | Backup for when Modal credits run out; can be 2-5x cheaper for spot |

## TIER 2 — Once company is filed (next 1-4 weeks)

| Program | Amount | Time to funds | Notes |
|---|---|---|---|
| **AWS Activate Founders** | $1k for unfunded indie | days after entity | Just need EIN + business profile; auto-approved at $1k tier |
| **AWS Activate Portfolio** | $5k-100k | weeks; need investor sponsor | Higher tier requires VC/accelerator backing |
| **Microsoft for Startups Hub** | $5k-150k Azure + $2.5k OpenAI credits | 2-4 weeks | Need company entity + business email; tier depends on stage |
| **Google for Startups Cloud Program** | $2k-200k GCP | 4-8 weeks | Tier depends on accelerator/investor signal |
| **DigitalOcean / Linode startup** | $500-25k | days | Lower per-dollar GPU value but easy yes |

## TIER 3 — Larger / slower / more selective

| Program | Amount | Time | Notes |
|---|---|---|---|
| **Y Combinator (W26 or S26 batch)** | $500k investment + $300k credit packs | months; competitive | Real swing for the fences; would unlock everything |
| **Mozilla AI grants** | $10-100k research | weeks-months | Open-source mission alignment; we fit |
| **Open Philanthropy ML safety / alignment grants** | $50k-500k | months | If we frame self-improvement loop as alignment-research |
| **a16z Speedrun / a16z American Dynamism** | $750k investment | months | Pitch as infrastructure |
| **Schmidt Sciences / Open Phil RFPs** | varies | months | Domain-specific; check their RFP pages quarterly |
| **Hugging Face × Github "Build with AI" grants** | hardware credits | rolling | Watch for announcements |
| **Modal x Together x Replicate joint credits** | varies | rolling | Sometimes co-promoted; ask all three together |

## Applications with the same boilerplate

Most of the above can share a 200-word pitch. Draft now, paste everywhere:

```
Founder: <name>
Project: GAD — open coding-agent platform with self-improvement loop
Stage: bootstrap / pre-seed
What we're building:
  Open-source coding agent with composition-of-specialists architecture
  (50-100 fine-tuned LoRA adapters across 1.5B-32B parameter range)
  routed and fused into a Sonnet-class system at fraction of cost.
  Self-improvement loop: every CLI invocation produces telemetry that
  feeds next-generation training, compounding personalization that
  frontier APIs structurally cannot offer. Currently shipping at 1.5B
  with 30/30 GAD-CLI eval and 50% GSM8K. Need compute to fire 32B
  coder shot (Qwen2.5-Coder-32B + QLoRA) and 70B orchestrator (Qwen2.5
  -72B-Instruct + QLoRA).
Compute ask: $X for ~Y hours of A100 80GB / H100 / DGX Cloud equivalent
Deliverables:
  - Full model weights published to Hugging Face (Apache 2.0)
  - Benchmark report vs frontier
  - Open-source agent framework (already public, MIT)
Public repo: https://github.com/MagicbornStudios/gad_slms
```

## Tracking applications

Use a single tracking file at `.planning/notes/credit-applications.md`
with columns: program, applied-on, amount, status, contact, follow-up
date. Don't lose track.

## Data acquisition (free, no application needed)

Pull these now to fill the data gaps documented in
`.planning/codebase/audit-2026-05-07-data-quality-honest.md`:

| Dataset | Size | Why | Pull cost |
|---|---|---|---|
| `bigcode/the-stack-smol-xs` | 120MB Python | code corpus seed for shot #1 (gap G8) | minutes |
| `bigcode/the-stack-v2` Python | ~50GB filtered | full code corpus for shot #1 | hours |
| `nvidia/OpenCodeReasoning` | 736k pairs | coder reasoning traces | minutes |
| `Anthropic/hh-rlhf` | 161k pairs | preference data for DPO (we have 97; this is +1600x) | minutes |
| `OpenAssistant/oasst2` | 600k examples | multi-turn assistant chats | minutes |
| `lmsys/lmsys-chat-1m` | 1M conversations | real chat data with preferences | hours |
| `princeton-nlp/SWE-bench` | 2k+ verified | already in plan; pull verified subset for eval | minutes |
| `cais/mmlu` | 14k Q&A | multi-subject reasoning eval | minutes |

After pulls land in `data/external/`, our DPO data goes from 97 pairs
to ~160k. That alone unlocks meaningful preference training at any size.
