# CLI performance variance — same backing model, different CLI shells

User-noted hypothesis (2026-05-06): even when claude-code, codex-cli,
gemini-cli, and opencode all point at the SAME backing model (e.g. our
local vLLM endpoint serving `scrubster/dr-stein-colab-cli`), the CLI shells
themselves will produce measurably different outputs.

## Why this is plausible

| Source of variance | Expected impact |
|---|---|
| **System prompt / preamble injection** | Each CLI injects its own scaffolding ("you are a helpful assistant…", tool-use protocol, repo-aware context). Same model + different preamble → different output. |
| **Tool-use protocol** | claude-code uses XML-tagged tool blocks; codex-cli uses OpenAI function-call JSON; gemini-cli uses Gemini's structured output. Even on the same backing model, the model has to "speak" a different protocol. |
| **Context window mgmt** | Different truncation / pruning strategies for long sessions. |
| **Token budget defaults** | `max_tokens` defaults vary; some CLIs cap output at 4k while others go 32k. |
| **Streaming behavior** | First-token vs full-block latency differs; UX-influencing but not output-content unless stop-conditions differ. |
| **Tool whitelist / permissions UX** | Permission-prompted tool calls may not fire on same prompt across CLIs. |

## Eval dimension to add

Per existing decisions slm-learning-031 (router-first economic core) and
slm-learning-039 (rule-based router phase 1), the matrix probe
(`scripts/runtime/matrix.py`) already records `runtime_id`. We should add:

- `serving_mode`: `"own" | "provider" | "mixed"`
  - `own`: CLI configured to talk to our vLLM endpoint
  - `provider`: CLI talks to its native provider (Anthropic / OpenAI / Google)
  - `mixed`: routing layer decides per-call
- `served_model`: which adapter / base is actually behind the endpoint
- `cli_version`: CLI shell version (already in `check.py` output)
- `system_prompt_hash`: sha256 of the CLI's injected preamble for reproducibility

This lets us cleanly separate three causes when an output is wrong:

1. The model is wrong (re-train or pick different adapter).
2. The CLI scaffolding is wrong (re-prompt, change CLI).
3. The routing decision was wrong (update router rules).

## Why the auth probe got reframed

Earlier `check.py` flagged any CLI with no provider env-var as `auth_ok=false`.
That's incorrect when running in `serving_mode="own"` — no provider auth is
needed because the CLI talks to our endpoint. The probe now reports
`provider_auth_ok` informationally and includes `serving_modes` so
downstream consumers know when missing provider creds matter.

## Next experiment

Once `serve_adapter.py` is up, run the same task fixture through:

1. claude-code → our endpoint
2. codex-cli → our endpoint
3. gemini-cli → our endpoint
4. raw curl → our endpoint (control)

Same model, same prompt, four CLI shells. Capture output diffs, latency,
token usage. Variance signal feeds the routing rules.

## Decision pointer

If the variance is large (≥10% output divergence on the GAD-tools eval),
that's a router signal — pick the CLI that minimizes variance for a given
task shape, not just the cheapest. Update `scripts/router/runtime_select.py`
rules to include `(task_shape, cli_shell) → score`.
