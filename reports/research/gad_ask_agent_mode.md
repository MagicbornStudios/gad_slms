# gad ask — Agent Mode + Permission Tiers

**Date:** 2026-05-09
**Extends:** `gad_ask_moe_entry_point.md` (sibling — do not modify)
**Schema refs:** `gad_ask_invocation.schema.json`, `gad_ask_permission_tiers.schema.json`
**Decision refs:** GLOBAL-D-324, GLOBAL-D-325, GLOBAL-D-330, GLOBAL-D-332

---

## 1. Bottom Line

`gad ask` is a two-axis surface: **mode** (ask | agent) × **permissions** (readonly | safe | dangerous). Default is ask+readonly — pure semantic lookup with no side effects. Agent+dangerous is the highest-trust configuration: the same surface that answers questions can take real-world actions on the operator's behalf, subject to an explicit authorization gate.

---

## 2. The Telephone-Book Argument

The operator's metaphor is exact: bending the corner of a page in a telephone book is a spatial indexing hack made obsolete by a search engine. The habit of "forage 20 folders for a specific file header" is the bent-corner approach applied to a codebase that now has a trained semantic index.

Two facts compound this:

**Fact 1 — The files don't need to exist.** A trained Kael model has compressed the rationale behind files that may no longer be present. It knows what that directory historically contained, what decisions drove its creation, and what decisions drove its removal. Querying the model reconstructs the knowledge without requiring the artifact. `gad ask "what was in the OMX directory before it was deleted"` is a valid and answerable query even though `.omx/` is gone.

**Fact 2 — Compounded works.** The model's latent knowledge can be recombined into answers that no single file contains. "What is the relationship between GLOBAL-D-293 and the visual-context system's cid token design?" spans a decision record, a skill body, and several component files. The model compresses that synthesis in one inference call. The file-forage path requires reading all three, holding them in context, and synthesizing manually — paying 10-50x the tokens for the same answer.

The implication for storage and attention is direct: content that exists only to be looked up does not need to be stored as a file. The model is the index. Files are for things that need to be executed, deployed, or handed off to another process — not for things that need to be understood.

---

## 3. The "Lower-End Model as Tool" Framing

Operator direction (verbatim): "asking gad and getting used to asking it for a lot of things, can help us free up latent space using that lower end model more like a tool for information."

The operational consequence:

- **Kael (1.5B-3B, cheap, gad-trained) is the first lookup.** Every agent — claude-code, codex-cli, gemini-cli, opencode — shells out to `gad ask` before reaching for Glob, Read, or Grep.
- **Kael returns an answer or says "low confidence."** If low-confidence, the agent escalates to the next tier (Sonnet for code reasoning, Opus for architecture decisions).
- **Opus stops being the default.** It becomes the expensive exception — reserved for genuine architectural judgment that requires reasoning across the full context of decisions, not lookup.

The cost profile shifts from "every query goes to Sonnet/Opus at $0.01-$0.10 per call" to "95% of queries go to Kael at $0.0001 per call, 5% escalate." At 100 queries per session, that is a 100x cost reduction for the lookup tier.

This framing also creates a training flywheel: every `gad ask` call that returns a high-confidence answer generates a tool-use DPO row where the Kael lookup is the `chosen` path and the Glob+Read cascade is the `rejected` path. Kael trains on these signals and increasingly prefers to call itself — the habit becomes encoded as a preference weight, not a standing rule that agents forget.

---

## 4. Agent Mode Mechanics

When `--mode=agent` is set, the invocation is no longer a lookup — it is a delegation. The soul resolves via `soul_routes.toml` as usual, but instead of returning an answer it returns a **plan**: a sequence of tool actions that answer the query by doing, not just by knowing.

The execution loop:

1. Soul receives query + context window (same assembly as ask mode).
2. Soul emits a plan: ordered list of `{ tool, inputs }` tuples.
3. **Each planned action is checked against the permissions tier** before execution. This check is not the soul's job — it is the `gad ask` runtime's job. The soul plans; the runtime enforces.
4. If check passes: action executes, result logged to `result.actions_taken[]`.
5. If check fails: `permission_check_result` record emitted with `decision=deny` or `decision=require_explicit_authorize`. Invocation status set to `aborted_permission_violation`. The soul's plan is halted — no partial execution of a multi-step plan past a permission boundary.
6. On completion: the full `actions_taken[]` array is mined for tool-use DPO rows.

The permission check happens at the **runtime layer**, not the model layer. The soul should not need to know the tier — it plans the best action for the goal. The runtime decides whether that action is allowed. This separation means the soul's training data stays clean: the model learns "what is the best action for this goal" without also learning "what can I get away with at this permission level" — the latter is an attack surface, not a capability.

---

## 5. Permissions Design

Three tiers, each a strict superset of the one below:

| Tier | Scope | Default for |
|---|---|---|
| `readonly` | Read, list, lookup, search, describe, diff only | All invocations unless overridden |
| `safe` | + edit-local, write-local, git-add/commit-local, test-run, build-local | Solo dev work |
| `dangerous` | + shell-exec, git-push, deploy, spend-money, delete-data, modify-credentials | Operator-authorized real-world actions |

Hard floor — cannot be lifted by any tier, env var, or flag: `destroy-customer-data`, `credential-exfiltration`, `drop-production-database-without-backup`.

**Tier defaults are configurable** in `gad-config.toml`:
```toml
[gad_ask]
default_mode = "ask"
default_permissions = "readonly"
```

Per-invocation flags override. Operator can also set `GAD_PERMISSIONS_AGENT_DANGEROUS_ALLOWLIST` to pre-authorize specific action patterns and skip the per-invocation confirmation prompt for those patterns.

**The authorization gate for dangerous.** Any action that falls under the `dangerous` tier but is not in the allowlist triggers a structured confirmation prompt before execution:
```
AUTHORIZE: modal deploy modal_app/serve_vllm.py [yes/no]
```
Proceeding without a `yes` reply = `decision=require_explicit_authorize` → abort. This mirrors the UX of `git push --force-with-lease`: the action is available, but it is fenced by an explicit human acknowledgment.

---

## 6. Concrete Invocation Examples

| Invocation | Mode | Permissions | What happens | Est. cost |
|---|---|---|---|---|
| `gad ask "what is GLOBAL-D-330"` | ask | readonly | Kael looks up the decision, returns text + citation | ~$0.0001 |
| `gad ask "what's stuck in claimed/"` | ask | readonly | Kael reads the handoff dataset in context, returns count + list | ~$0.0002 |
| `gad ask --mode=agent --permissions=safe "reclaim stale claims"` | agent | safe | Kael plans `gad handoffs reclaim --dry-run`, executes it, returns results + asks operator to confirm the real reclaim | ~$0.0003 |
| `gad ask --mode=agent --permissions=dangerous "deploy modal vllm"` | agent | dangerous | Kael prepends authorization gate prompt, on `yes` fires `modal deploy modal_app/serve_vllm.py`, logs action | ~$0.001 + modal compute |
| `gad ask --mode=agent --permissions=safe "delete .gad-log/old"` | agent | safe | Permission check fails: `delete-irreversible` exceeds safe tier. Emits `permission_check_result(deny)`. Invocation aborts. | ~$0.00005 |

---

## 7. Tool-Use DPO Connection

Every agent-mode invocation generates one DPO row per planned action. The schema is `tool_use_preference.schema.json` — same format as the existing seed rows.

The `chosen` path is the action the agent took via `gad ask --mode=agent`. The `rejected` path is reconstructed from the query type: what would a model without this training have done? For most agent-mode queries the rejected path is a manual shell sequence — `ls claimed/` + Read each file + parse mtime + grep claimed_by + decide.

Permission-denial events are especially valuable training signal: the `rejected` path is "agent planned a delete-irreversible action without escalating, and executed it." The `chosen` path is "agent recognized the action exceeded the tier, emitted a deny result, and surfaced the escalation to the operator." This trains future souls to reason about permission tiers before planning actions — not just to execute plans and let the runtime catch violations.

The `verdict_source` on these DPO rows is `retrospective_log_analysis` when mined from logs and `verifier` when the permission check runtime validates the decision programmatically.

---

## 8. Open Questions

**Q7 — Confirm-phrase vs yes/no.** Should `permissions=dangerous` require a typed confirm phrase (like `git push --force-with-lease`) or a simple `yes/no` prompt? Typed phrase reduces accidental authorization but increases friction. Operator decision required.

**Q8 — Per-customer permissions bound.** Where does the maximum permissions cap for a customer-scoped invocation live? Candidate: `soul_route.permissions_max` field in `soul_routes.toml`. A customer whose soul has `permissions_max=safe` cannot invoke `--permissions=dangerous` even if the operator is present. This is relevant once gad ask is exposed through operator-facing products.

**Q9 — Destructive as a fourth tier.** Should there be a `destructive` tier above `dangerous` for actions that are not recoverable under any circumstances — `DROP TABLE` in production, `git push --force origin main`, `rm -rf /`? The current design puts these in the hard floor (always forbidden). A fourth tier that requires a 24-hour operator pre-authorization window (like a bank wire confirmation) might be cleaner than the hard floor for edge cases where the operator genuinely needs the action.

**Q10 — Per-action vs per-invocation tier inheritance.** The current design inherits the permissions tier from the invocation for all actions in that invocation's plan. An alternative: each action in a plan carries its own permissions assertion, and the agent can escalate mid-plan. This is more flexible but harder to audit — the DPO signal becomes ambiguous when a single invocation spans tiers. Recommendation: keep per-invocation inheritance; a new invocation is cheap enough that switching tiers mid-plan is not a real burden.

---

*Sibling to `gad_ask_moe_entry_point.md`. Do not merge these documents. The MoE entry point covers routing architecture; this document covers the action surface and permission model. Both are design artifacts — no gad ask runtime code exists yet.*
