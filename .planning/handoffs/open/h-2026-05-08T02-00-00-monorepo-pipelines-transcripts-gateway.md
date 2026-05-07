---
id: h-2026-05-08T02-00-00-monorepo-pipelines-transcripts-gateway
projectid: slm-learning
phase: 04
task_id: SL-T-04-monorepo-pipelines
created_at: 2026-05-08T02:00:00.000Z
created_by: dr-stein-slm-learning
claimed_by:
claimed_at:
completed_at:
priority: high
estimated_context: bounded
risk: safe
time: deep
surface: cross-project
runtime_preference: claude-code
recipient: monorepo / platform team dispatcher (Marshal-tbd)
---

# Cross-project handoff — transcript curation, real-time daemon, inference gateway with fallback

From: Dr. Stein, slm-learning root
To: monorepo/platform team's dispatcher
Why: Operator declared four pipeline asks during 2026-05-08 diagnostic
session. All four belong to monorepo lane (data/inference
infrastructure), not slm-learning (training/evals). Routing them as a
single packet so the dispatcher can split them across phases.

Operator quote (verbatim, 2026-05-08, mid-diagnosis):

> "this is a convo for the monorepo agent that is relveant for you
> are we logging our transcripts too? do we have that being curated
> for our datasets. also do we have something always running like
> our daemon curating datasets in realtime and verifying in real
> time? […] we should definitely have reports for that and a remote
> storage going on to store the data. we also need to make sure that
> we have our inferencing pipeline for our models up and we support
> the chat completions and all the normal llm chat api, v2/v3
> versions of models. we need whatever we can set up in our
> slm-learning models and we need to start consuming those models
> and having fallbacks in our every day pipelines. this will be
> significant training data as it would show extactly what should
> be, and how wrong we are, while still getting the work done."

## §1 — Transcript curation pipeline

**Ask:** capture this conversation (and every Claude Code / Stein /
Kael / Gilgamesh session) as a curated dataset. Today the
`gad telemetry export` adapter produces 215k+ envelopes — but we
don't yet have the **conversation transcript** layer (full message
turns, tool-call interleaving, agent attribution).

**What slm-learning needs from it:**
- Prompt → response pairs with role attribution (operator, dr-stein,
  kael, claude-code orchestrator, etc.)
- Tool-call sequences as their own training signal
- Redaction pass (we have `gad telemetry export --redacted` already)
- Per-soul slicing so we can train a "Stein" specialist on Stein's
  outputs only

**Existing surfaces to extend:**
- `gad telemetry export` adapters (handoffs, gad-log, trace-events)
- `data/agent_corpus_*.jsonl` — already accumulating per-agent corpora
  (gad-codebase-mapper, gad-doc-verifier, gad-assumptions-analyzer
  observed in slm-learning's data dir)
- `data/agent_corpus_global_2026-05-07.jsonl` — daily roll-up

**What's missing:** the chat-message turn layer. Currently we capture
tool calls + reasoning + handoffs but not the user-message → assistant-
message pairing as a contiguous transcript. That's the highest-value
training signal because it's the operator's actual instructions in
context.

**Proposed:** new adapter `chat-transcripts` in
`gad telemetry export`. Each Claude Code session logs its message
log to `.gad/transcripts/<session-id>.jsonl` automatically (hook on
session-end), and the export adapter walks those.

## §2 — Real-time data curation daemon

**Ask:** "do we have something always running like our daemon
curating datasets in realtime and verifying in real time?"

**Status:** No. We have `gad telemetry export` as a manual pull. The
referenced "phase 147 daemon" appeared in the inbound handoff
`h-2026-05-07T19-15-00-global-bridge-ack-export-ready` as something
that "automates [export] on a 30m interval — gated on operator
approval to spawn." That gate has not been opened.

**Proposed scope for the daemon:**
1. Run `gad telemetry export` every 30 min (configurable)
2. After each export, run a verification pass: `gad data verify
   <export-path>` checks redaction, schema compliance, dedupe rate,
   manifest hash. Reject the export if any check fails; alert the
   operator via handoff.
3. Maintain a **timeline** at `.planning/data-timeline.json`: for each
   export, record `{ts, n_envelopes, n_chat_turns, n_handoffs,
   sha256, source_commits, sink_path}`.
4. Push fresh exports to remote storage (Modal slm-data volume)
   automatically with per-day directory layout.
5. Surface a report: `gad data report --since 7d` shows the
   accumulation curve.

**Why monorepo lane, not slm-learning:**
slm-learning consumes the curated data. The daemon producing it is
infrastructure that all projects benefit from, including
`magicborn-studios`, `gad-monorepo`, etc.

**Decision to add post-build:** `slm-learning-N` — daemon-curated
training data is the canonical SLM training input; manual datasets
become the exception.

## §3 — Inference gateway with chat-completions API

**Ask:** "make sure that we have our inferencing pipeline for our
models up and we support the chat completions and all the normal llm
chat api, v2/v3 versions of models."

**Status:** We have ONE Modal vLLM endpoint:
`https://b2gdevs--slm-learning-vllm-vllmengine-chat-completions.modal.run`
serving the v1 tooluse adapter, OpenAI-compatible. That's enough for
proof-of-concept but not for production fallback.

**What's missing:**

| Capability | Status | Owner suggestion |
|---|---|---|
| OpenAI-compatible chat-completions endpoint | ✅ live (v1) | — |
| Model versioning in URL (`/v1/`, `/v2/`, `/v3/`) | ❌ | monorepo: define convention |
| Multi-adapter routing (one endpoint serves many adapters) | ❌ | monorepo: vLLM LoRA-stack pattern |
| Adapter selection by `model` field in request | ❌ | monorepo: route on request body |
| Fallback chain (ours → claude-cli → opus → fail) | ❌ | monorepo: gateway service |
| Logging every request + response for training data | ❌ | monorepo: gateway hook |
| Cost / latency per route in a dashboard | ❌ | monorepo: grafana-equivalent |

**Proposed architecture for the gateway:**

```
operator/agent
    │
    ▼
gad-inference-gateway (new monorepo service)
    │
    ├── route("model": "ours-tooluse-v1") → modal-vllm-1
    ├── route("model": "ours-coder-7b-v3") → modal-vllm-3 (when trained)
    ├── route("model": "ours-*") fallback → claude-cli → opus
    │
    └── log to gad-telemetry → train next iteration
```

**Slm-learning's commitment:** publish every adapter we promote to a
named gateway route with the version suffix (`v1`, `v2`, `v3`). The
gateway team owns the routing rules + fallback policy.

## §4 — Daily pipeline consumption + correction-pair capture

**Ask** (this is the powerful one):

> "we need to start consuming those models and having fallbacks in
> our every day pipelines. this will be significant training data as
> it would show extactly what should be, and how wrong we are, while
> still getting the work done."

**Translation to a pipeline:**

```
operator request
    ↓
[gateway] try ours-* model first
    ↓
[ours-* model]: returns a candidate response
    ↓
[validator]: does the response pass the project's success bar?
    ├── YES → use it; log <prompt, ours_response, accepted=true>
    └── NO  → fallback to frontier (claude/opus)
              → log <prompt, ours_response, frontier_response,
                       diff, accepted=true_for_frontier>
              → THIS is the gold training pair: ours = chosen
                rejected, frontier = chosen accepted, ready for DPO
```

**Why this is the key idea:** every operator interaction becomes a
preference pair when ours fails. We don't need synthetic preference
data — we generate real, contextual preference data as a byproduct
of doing actual work. This is the data flywheel
(`slm-learning-094` composition strategy) made concrete.

**Build order for the loop:**
1. Gateway exists (§3)
2. Validator exists per-task (this is `gad eval <task>` — partially
   exists for coding, gad_tools, doc_verifier; needs broader coverage)
3. Rejection logging captures both candidates + the diff
4. DPO training pipeline consumes rejection logs daily
5. New adapter promoted as `ours-coder-vN+1`; gateway routes it; loop
   tightens

**Slm-learning's part:** stand up the DPO training pipeline. We
already have SFT. DPO needs `chosen`/`rejected` pairs. The gateway
log is the source.

**Monorepo's part:** stages 1–3 (gateway, validator, log capture).

## §5 — Reports and timeline

**Ask:** "we should definitely have reports for that and a remote
storage going on to store the data."

**Proposed:**
- `gad data timeline` — chart of envelope count, distinct sessions,
  redaction-rejection rate, per-day, per-source.
- `gad data inventory` — what's on slm-data volume, sized + dated.
- Auto-published to a static page (planning-app section?) so the
  operator can see the curve without running a CLI.

These are presentation surfaces over the daemon outputs (§2).

## Acceptance gate

Receiving lane (monorepo dispatcher / Marshal-tbd):

- [ ] §1 chat-transcripts adapter — phase scope + owner
- [ ] §2 daemon — phase scope + owner; first 30m export captured + verified
- [ ] §3 gateway — RFC for multi-adapter routing + fallback; first
      v1 → v2 promotion path documented
- [ ] §4 correction-pair capture — wire one pipeline (suggest:
      `gad note add` since it's low-stakes) end-to-end as a proof
- [ ] §5 reports — at least one published timeline view
- [ ] Closeout handoffs to slm-learning when each lands so we know
      what's available to consume

## Slm-learning's parallel commitments

- Continue declaring CLI extensions in
  `.planning/cli/extensions.json` (per prior handoff
  `h-2026-05-08T01-00-00`)
- Stand up the DPO training pipeline once §4's rejection logs flow
- Publish the next coder adapter as `ours-coder-7b-v2` (post-OCR-LoRA
  diagnosis; expected after the 5-variant controlled experiments
  per directive 2026-05-08)
- Provide live usage data — what models the operator routes through
  the gateway, what fails, what falls back

— Dr. Stein
