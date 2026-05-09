# Nous Research Real-Time Feed: gad nous

**Date:** 2026-05-09

## Bottom Line

`gad nous` is the daily-standup surface for staying current with Nous Research community signals — their model releases, active issues, PRs, and community discussions. It operates entirely against the public GitHub API (no auth required for the daily ritual) and surfaces the most relevant signals in under 10 seconds. Primary use case: morning checkin on overnight Nous activity before deciding what to investigate, replicate, or respond to in our own work.

## Reachable Signals

| Subcommand | API endpoint | What it returns |
|---|---|---|
| `gad nous repos` | `GET /orgs/NousResearch/repos` | All public repos with stars, forks, language, topics, last push |
| `gad nous issues` | `GET /search/issues?q=org:NousResearch` | Issues and PRs filtered by text, repo, state |
| `gad nous discussions` | `GET /repos/:org/:repo/discussions` (REST) or issues label fallback | Community discussions; falls back to `label:question` search without GraphQL token |
| `gad nous releases` | `GET /repos/:org/:repo/releases` per active repo | Model releases, tagged versions — "did Hermes-5 drop yet" |
| `gad nous activity` | search/issues (issues + PRs) + releases in parallel | N-day chronological feed, all event types merged and sorted |
| `gad nous search` | Multi-target: repos + issues + releases in parallel | One-shot query across all signal types |

## Daily Ritual

One-prompt morning routine:

```sh
gad nous activity --days 1 --json | head -80
```

This returns all issues opened/updated, PRs merged, and releases tagged in the last 24 hours across the NousResearch org. Total API cost: 3 calls (issues search, PR search, releases via top-5 repos). Well within the 60-req/hr unauthenticated budget.

If the output contains a new model release (tag containing "Hermes", "Nous", or a version bump), surface it to operator immediately. If there is a spike in open issues in `Atropos` or `Hermes-3`, that signals active development worth watching.

With `GITHUB_TOKEN` set, the same ritual costs nothing against the 5000/hr quota and enables deeper pulls:

```sh
gad nous activity --days 7          # full week retroactive sweep on session start
gad nous issues --query "atropos training" --state open
gad nous releases --repo Hermes-3
```

## Connection to gad ask

`gad ask "what's new in Nous Research"` should eventually route internally to `gad nous activity --days 1 --json` and format the result as a narrative summary. The wiring is not yet implemented (no integration in `ask.cjs`), but the surface contract is stable: `gad nous activity --json` returns a `{ org, days, since, events[], metadata }` structure that any summarizer can consume. The `gad ask` + `gad nous` integration belongs in a follow-on task under phase 158 (intake/ask) or a new phase targeting "research feed integration."

## Auth Ladder

| Level | Setup | Req/hr | Discussions |
|---|---|---|---|
| None | Default | 60 | Issues label fallback only |
| `GITHUB_TOKEN` (classic or fine-grained) | `export GITHUB_TOKEN=ghp_...` | 5000 | Issues label fallback |
| Token with `read:discussion` scope | Same var, broader scope | 5000 | Full REST discussions |
| GraphQL token | Would need separate `GITHUB_GRAPHQL_TOKEN` | — | Full org-wide discussions via GraphQL |

For the daily ritual, unauthenticated (60/hr) is sufficient: 3 calls for activity, caching prevents redundant calls within the 5-minute TTL. For deeper research sessions (iterating on issues, scanning all releases), set `GITHUB_TOKEN`.

## Open Questions

**Discord:** Nous Research has an active Discord with announcements and community help. No public API without a bot token with guild membership. Not worth pursuing unless we add a Discord integration layer (requires joining the server + standing bot). Low priority.

**Reddit r/LocalLLaMA:** RSS feed available at `https://www.reddit.com/r/LocalLLaMA/.rss`. Could be added as `gad nous reddit` pulling that feed and filtering for "nous" + "hermes" mentions. Light lift, medium signal value.

**Twitter/X:** No public API (v2 requires paid access). Not viable without paying for Basic tier access ($100/month). Skip.

**HuggingFace:** `https://huggingface.co/NousResearch` model list is fetchable via HF Hub API (`GET /api/models?author=NousResearch`). This would add the highest-value signal (model drops typically appear on HF before GitHub releases). Candidate for `gad nous hf` subcommand in a follow-on phase — or wired into `gad hf` when that namespace ships.

**nousresearch.com/releases:** The releases page renders dynamically. No RSS link confirmed in the page head. The GitHub releases endpoint is the better canonical signal for now.
