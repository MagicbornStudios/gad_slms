# Realistic benefit timeline — what to expect from the GAD-as-orchestrator plan

Counterweight to "we'll beat Opus" hype. Captures honest expectations
per phase 04's substrate-first ordering (decision `slm-learning-042`).

## 1–2 weeks (substrate landing)

**You can have**:
- `gad runtime check --json` + `gad runtime matrix --task-shape <X> --json`
- Local vLLM OpenAI-compatible endpoint serving any HF Hub adapter
- Rule-based runtime router with decision logging
- First SLM subagent endpoint reachable (probably v2 CLI translator at `/v1/chat/completions`)
- doc-verifier or command-router integrated into actual workflows

**Working experience changes to**: ask GAD for a task → GAD classifies + checks runtime
health → picks Claude/Codex/Gemini/OpenCode/local SLM → injects context → runs → logs
outcome → updates pressure data.

**Don't expect**: SLM replaces frontier; autonomous feature implementation; magic
routing decisions. The win is friction reduction, not capability replacement.

## 1 month

**You can have**:
- Routine GAD command translation handled locally (already 30/30 — needs the serving
  bridge to be useful)
- Doc verification partially local
- Assumption extraction partially local
- Codebase summaries assisted by 3B model
- Runtime routing decision logs accumulating (rule-based, ~500 decisions)
- First reliable training corpus per first-wave agent (doc-verifier, assumptions-analyzer,
  codebase-mapper)

**Cognitive overhead drops on**: "remember what we decided", "which command do I use",
"summarize the repo", "check the plan", "log this." Those become cheap automatic.

## 2–3 months

**You can have**:
- 7B tool-use coder trained on real GAD traces (Qwen2.5-Coder-7B + QLoRA)
- Multi-task LoRA tested
- Adapter interference measured empirically (stacked vs multi-task)
- Runtime routing trained on real outcome data (rule-based router → ML classifier)
- A/B/C eval against bare Opus (the defensible-claim test)
- GAD-native agent runtime prototype (Pattern B)

**At this point**: the actual thesis becomes testable. "Can a GAD-orchestrated system
beat bare Opus on bounded workflows?" gets a real answer, with traces to back it up.

## What this is NOT

- A path to a single-model frontier competitor. We do not have the budget, data, or
  scale to out-pretrain Anthropic/OpenAI/Google.
- A short-term productivity miracle. The substrate has to land before the SLMs are
  useful. Trained adapters that nothing calls are useless.
- A guarantee that stacked LoRAs will compose cleanly. The composition eval (step 6)
  exists specifically because we don't know yet.

## What it IS

A way to **stop manually carrying project memory, tool conventions, runtime decisions,
repeated verification, and logging.** GAD absorbs that work, routes it, measures it,
and converts it into better specialists over time.

The compounding benefit isn't model intelligence — it's **workflow memory that survives
session boundaries**.
