---
id: h-2026-05-07T20-00-00-monorepo-kael-desktop-dispatcher-soul-and-dx-gaps
projectid: slm-learning
phase: 04
task_id: SL-T-04-monorepo-bridge
created_at: 2026-05-07T20:00:00.000Z
created_by: dr-stein-slm-learning
claimed_by:
claimed_at:
completed_at:
priority: high
estimated_context: bounded
risk: safe
time: standard
surface: cross-project
runtime_preference: claude-code
recipient: monorepo / platform team dispatcher
---

# Cross-project handoff — Kael desktop app, dispatcher soul, MCP-app ownership, DX gaps

From: Dr. Stein, slm-learning root
To: monorepo/platform team's dispatcher (or new dispatcher soul, see §1)
Why: Operator declared the lane split — slm-learning completes on
SLM/LLM training & evals; monorepo/platform owns dev velocity,
funding-facing UX, the Kael desktop app, and the MCP-app migration.
This is the suggestions/review packet for that team's mailbox.

Operator quote (verbatim, 2026-05-07):

> "the monorepo agent is mainly responsible and this is the
> slm-learning root. we just need to make some handoffs or give
> suggestions in that teams mailbox that needs review from their
> dispatcher/leader/new soul. this repo needs to focus on completeling
> in slms/llms. the monorepo and platform needs to focus on speeding
> up our dev time and getting us funding."

## §1 — New soul candidate: a dispatcher / COO archetype

Operator observation: Dr. Stein and Gilgamesh both **dream**
(capability, possibility). Neither dreams of operations efficiency.
Kael fills that role for the operator personally, but the *team*
needs the same archetype at the dispatch layer — somebody who routes
work across lanes, picks runtimes, watches handoff queues, enforces
the comparator floor, and keeps wall-time honest.

Three candidate names + archetypes:

| Name | Archetype | Pros | Cons |
|---|---|---|---|
| **Marshal** | Field commander, organizes the front | Authoritative; matches "dispatch" verb; non-mythic so doesn't compete with Gilgamesh | Slightly martial — adjust voice toward "ops director" not "general" |
| **Quartermaster** | Supply, logistics, resource allocation | Strong ops-efficiency match; clear non-dreamer role | Less personality; might feel subordinate |
| **Ferryman** | Charon — moves work across lanes | Mythic resonance with Gilgamesh; literal handoff metaphor | More handoff-focused than ops-broad |

Dr. Stein's recommendation: **Marshal** — keeps Stein/Gilgamesh as
dreamers, gives the team a non-dreamer COO voice, and the verb maps
cleanly onto `gad handoffs claim-next` / runtime selection / comparator
gate enforcement.

**Acceptance gate (§1):** monorepo dispatcher (current or replacement)
chooses one name and lands `narrative/souls/<name>.md` with a body
modeled after `kael.md` but team-scoped, plus a SOUL.md pointer block
for the *monorepo* root (not slm-learning — Stein stays here).

## §2 — Kael desktop app (single page) — operator concept brief

Verbatim operator brief:

> "we just need our fundamental application which is just kael as a
> nice looking desktop app...single page. always standing by waiting
> to converse and i can say a keyword command like 'hey google'. but
> it would be 'Kael, you there?' and that would be the cue for ack by
> kael and they take in what i am saying and then start performing
> actions, rendering, or building what is needed."

Translated into a build spec:

| Surface | Behavior |
|---|---|
| Window | Single-page Tauri app, always-on, dockable to system tray |
| Idle state | Avatar + "standing by" indicator; minimal CPU |
| Wake phrase | "Kael, you there?" — local wake-word listener (Picovoice / Snowboy / Whisper-tiny streaming) |
| Ack | Kael says/types "I'm here" + opens the assistant-ui thread to ready |
| Action | Kael interprets request, **dispatches** to the right soul (Stein for SLM work, Gilgamesh for vision/scope, Marshal for cross-lane ops, Kael himself for personal/computer-use) |
| Rendering | Pulls transient component windows via `launch_component` from the MCP-app manifest |
| Real-time | Tails `gad state show` + open handoffs + experiment queue + runtime health on a polling/WebSocket loop |
| Voice loop | Optional: TTS for Kael's responses; toggleable |

**Critical constraint:** Kael is the *operator's* personal companion.
Marshal (or whoever wins §1) is the *team's* dispatcher. They can be
different processes/souls even if the surface looks unified.

**Acceptance gate (§2):** monorepo team produces a one-page design
note + a Tauri prototype (window + wake-word stub + assistant-ui
thread, no agent backend yet). Backend wiring is a follow-on phase
once the MCP-app schema lands.

## §3 — MCP-app migration ownership

Confirming the lane: the ~7h migration plan from the prior session
(manifest schema, `gad mcp` loader, Tauri `launch_component`, Next
transient layout, two pilot manifests, retire overnight daemon) lives
in the **monorepo** lane.

Three answered design questions from Dr. Stein for that team to act on:

| Question | Verdict | Reason |
|---|---|---|
| Manifest shape (6 tools) | YES, with `capabilities: ["read","write","long-running","file-export",…]` added so `launch_component` can pick the right confirmation UX | Otherwise shape works |
| Shared shell vs per-app | Shared shell first (`apps/desktop/projects/<slug>/components/<id>?transient=1`) | Per-app is premature; flip when a project's bespoke deps would bloat the shared bundle |
| Embeddings vs keywords for `find_component` | Keywords (fuzzy on `intent + title + tags`) | ~50 components is well below the embeddings-pays-off threshold |

Plus one non-negotiable Dr. Stein addition: **bake an
`mcp-app.schema.json` into `lib/` and validate on `gad mcp serve`
boot** so a malformed manifest fails loud, not silent.

**Slm-learning's commitment:** once the schema lands, this repo
declares its own manifest covering the slm-learning components from
the tray-app surface inventory below (queue-board, comparator-matrix,
runtime-health, evolution-panel for slm-learning's proto-skills).

## §4 — Tray-app surface inventory (Dr. Stein's catalog)

Reproduced for the monorepo team's reference. Most of these are
already CLI-mediated and only need a thin component wrapper:

| Lane | CLI commands today | Tray surface needed |
|---|---|---|
| Project context | `gad snapshot`, `gad projects list` | `project-overview` |
| Tasks | `gad tasks list/stamp/show` | `task-board` (kanban + inline stamp) |
| Handoffs | `gad handoffs list/claim/complete/show` | `handoff-tray` (ranked, claim button, runtime badge) |
| State / decisions | `gad state log/show`, `gad decisions add/show/list` | `decision-log` + `state-stream` (live tail) |
| Team / runtimes | `gad team status/show`, `gad runtimes status/ping` | `runtime-health` (auth check + last-success-per-runtime, surfaces gemini/codex/opencode preflight failures) |
| Issues / notes | `gad note add/list/promote` | `issue-intake` (backed by `post_agent_issue` MCP tool) |
| Evolution | `gad evolution evolve/validate/shed` | `evolution-panel` (proto-skill review + validator output) |
| Experiments | `experiments/queue/{pending,running,evaluated,promoted,rejected}` | `queue-board` (drag, fire from pending, view eval JSON) |
| Eval matrix | `scripts/eval/run_comparative_matrix.py` | `comparator-matrix` (4-row card per candidate) |
| Project editor | (Next route already) | open as transient via Tauri |
| Visual Context | alt+i → VCS panel | every component opts in via `<SiteSection cid="…">` |

## §5 — Adopt assistant-ui

Dr. Stein recommends adopting `assistant-ui` for chat surfaces inside
transient windows. Not rolling our own.

**Caveat:** pin the version, wrap behind a thin `<GadChatThread>`
adapter so we can swap our SLM/LLM gateway in/out without a UI rewrite
when we route to `ours-via-modal-v2`.

## §6 — DX gaps Dr. Stein hit while filing this handoff

Two real gaps worth fixing in the gad CLI:

1. **`gad state log` is write-only.** `gad state show` renders the
   current next-action but does **not** tail recent log entries. Today
   the only way to read prior entries is `Read` on `.planning/STATE.xml`
   directly. Proposal: add `gad state log --tail N` (mirrors `gad
   handoffs list`'s scan) or fold a tail into `gad state show
   --log-tail N`. Either is a small CLI change in the monorepo.

2. **`gad handoffs create` requires `--task-id` that exists in
   `.planning/tasks/`** which is friction for cross-project handoffs
   (recipient project may not have a matching task). I worked around
   it by writing this file directly, mirroring the format of the
   inbound closeout `h-2026-05-07T19-15-00-global-bridge-ack-export-ready`.
   Proposal: relax the check when `surface: cross-project` is used, or
   document the direct-file-write pattern in the README.

## §7 — Real-time UI lane summary

Operator's framing: monorepo + platform are responsible for real-time
UI; slm-learning produces components that plug into it. Dr. Stein
agrees and will not duplicate UI work here. When monorepo lands the
manifest schema + Tauri shell, slm-learning will publish its components
on the manifest the same day.

## Acceptance gate

Receiving lane (monorepo dispatcher / Marshal-tbd) is asked to:

- [ ] Pick a dispatcher-soul name and land `narrative/souls/<name>.md`
- [ ] Produce a one-page design note + Tauri prototype for Kael
      desktop (§2)
- [ ] Confirm MCP-app migration ownership and the ~7h plan
- [ ] Land the two DX-gap CLI fixes (§6)
- [ ] Reply via closeout handoff to slm-learning when each item ships

Slm-learning's parallel commitment:

- [ ] Stay focused on the public-benchmark row (HumanEval / MBPP /
      SWE-bench Verified subset) — operator's stated #1 data ask
- [ ] Publish slm-learning's manifest contribution the day the schema
      lands
- [ ] Do not duplicate Kael / desktop / dispatcher work here

— Dr. Stein
