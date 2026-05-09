# Operator Chat Bridges: Discord / WhatsApp / SMS → Kael

**Date:** 2026-05-09
**Scope:** custom_portfolio monorepo — `vendor/get-anything-done/bin/commands/bridge.cjs`
**Decision trigger:** operator 2026-05-09: "we do need whatsapp, phone, discord integrations. whatever is easiest. kael should help me set up everything by next session."

---

## 1. Bottom Line

Kael is the operator's central nervous system. Every inbound message from any channel (Discord DM or server, WhatsApp, SMS, future voice transcript) routes into Kael's chat thread. Kael processes it — plans tasks, answers questions, surfaces handoffs — and optionally echoes responses back to the source channel. The operator never needs to leave the Kael UI to act on a message from another surface. This is the same operator-todos rendering pattern already shipping: chat-first, inline, no always-on dashboards.

---

## 2. The Three Bridges, Ranked by Effort

| Bridge | Effort | Cost | Timeline |
|---|---|---|---|
| Discord | Minutes | Free | Next session |
| WhatsApp | Hours (Twilio setup) | ~$0.005/msg outbound | 1-2 days |
| SMS | Hours (same Twilio account) | ~$0.01/msg US | 1-2 days (same account as WhatsApp) |
| Voice/Phone | Days (TwiML + transcription) | ~$0.013/min + Whisper | Future phase |

**Discord (easiest):** Webhook URL = outbound in 5 minutes. Inbound requires a Discord Application + Bot Token + `gad bridge discord receive` listening on a public port (or ngrok for local dev). Free at any realistic operator scale. discord.js SDK available but not needed — native fetch handles webhook POST.

**WhatsApp (medium):** Twilio WhatsApp Business API. Requires a Twilio account ($5–10 trial credit covers weeks of testing), a WhatsApp Business-enabled number (Twilio provides `+14155238886` as a shared sandbox for testing without business verification), and eventually a business-verified account for production. Outbound messages to numbers that haven't opted in require pre-approved template messages — the main operational constraint. Inbound webhook is free and immediate.

**SMS (medium, same account):** If Twilio is already set up for WhatsApp, SMS costs one extra Twilio phone number ($1/month). ~$0.01 per US message. No opt-in restriction for outbound (operator owns the number). Works immediately after Twilio signup.

**Voice/Phone (skip now):** Twilio Voice + TwiML for call routing, Whisper or Twilio's built-in STT for transcription. Adds latency, cost, and complexity with unclear operator benefit when SMS/WhatsApp cover the use case. Deferred to a future phase.

---

## 3. Architecture

```
[Discord/WhatsApp/SMS]
       |
       | inbound POST (operator message, external event)
       v
[gad bridge <provider> receive]  -- port 3030 (discord) or Twilio webhook
       |
       | appends JSONL record
       v
[.planning/bridges/<provider>/<date>.jsonl]   (audit log, gitignored)
       |
       | + writes / calls Kael chat-message API (future: gad transcript-append)
       v
[Kael chat thread]   -- inline assistant-ui rendering, same pattern as operator-todos
       |
       | Kael processes: plans tasks, answers, surfaces handoffs
       v
[Kael response]
       |
       | optional echo (bridge.echo_kael_responses_to_inbox = true, OPT-IN)
       v
[outbound webhook / Twilio API]
       |
       v
[Discord channel / WhatsApp / SMS]
```

The inbound path is always active once `gad bridge <provider> receive` is running. The outbound echo path is opt-in: `bridge.echo_kael_responses_to_inbox` defaults `false` per the operator standing rule that features multiplying API spend must be opt-in.

---

## 4. Setup Flow Tomorrow (Discord first)

**(a)** Operator: open Discord → User Settings → Advanced → enable Developer Mode. Create (or pick) a server. Create `#kael-inbox` channel. Right-click channel → Integrations → Webhooks → New Webhook → copy URL.

**(b)** Operator runs:
```sh
gad bridge discord channels add kael-inbox --webhook-url <url>
```
Writes to `.planning/gad-config.toml` under `[bridge.discord.channels]`.

**(c)** Operator runs:
```sh
gad settings set bridge.discord.kael_inbox_channel kael-inbox --scope project --projectid global
```

**(d)** Operator runs (foreground to verify, then add `--detach` for daemon mode):
```sh
gad bridge discord receive --port 3030
```
For external access (Discord needs a public URL for bot events), use ngrok: `ngrok http 3030`. Paste the ngrok URL as the Interactions Endpoint URL in the Discord Developer Portal.

**(e)** Optional echo (opt-in):
```sh
gad settings set bridge.echo_kael_responses_to_inbox true --scope user
```

**(f)** Smoke test (dry-run, no real send):
```sh
gad bridge discord send "#kael-inbox" "Kael online" --dry-run --json
gad bridge status --json
```

---

## 5. Privacy + Opt-In Discipline

Bridges that **emit** (Discord channels that may have other members, SMS to phone numbers, WhatsApp to contacts) are opt-in at the configuration level. If `bridge.discord.default_webhook_url` is null and no channel mapping exists, `gad bridge discord send` refuses with a clear error rather than silently failing. `bridge.echo_kael_responses_to_inbox` defaults false. This mirrors the dual-generate incident learning: outbound paths that multiply cost or external visibility are never on by default.

Inbound (`gad bridge discord receive`, Twilio webhook) is always fine — it only writes to the local `.planning/bridges/` JSONL log and routes into Kael's session, both operator-private.

---

## 6. WhatsApp + SMS Specifics

**Twilio account setup:**
1. Sign up at twilio.com — trial credit covers weeks of testing (~$15).
2. Get a phone number ($1/month US). For WhatsApp sandbox: use `+14155238886` (shared, pre-verified for sandbox testing; message "join <sandbox-word>" from your personal WhatsApp to opt in).
3. Set env vars: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` (+14155238886 for sandbox), `TWILIO_SMS_FROM` (your Twilio number).
4. Configure inbound webhook: Twilio Console → Phone Numbers → Manage → your number → Messaging → Webhook URL = `https://<your-host>/twilio/sms` (future `gad bridge sms receive` endpoint, same shape as discord receive).

**WhatsApp Business verification** is needed to send outbound messages outside the sandbox to arbitrary numbers. Takes 1-2 business days and requires a Facebook Business Manager account. For operator-to-self messaging (operator's personal WhatsApp), sandbox is sufficient indefinitely.

---

## 7. Connection to Kael Chat

Discord inbound webhook events become inline assistant messages in Kael's chat thread, rendered using the same `useAssistantTool` pattern as operator-todos (decision GLOBAL-D-301, phase 160). The operator sees a message-shaped component in chat showing the inbound source, sender, and content. Responding in Kael's chat is the action — no need to switch to Discord.

The `gad bridge discord receive` server writes each event to the JSONL audit log and (when the Kael transcript-append API ships) will call `gad transcript-append --projectid global --role user --content "<message>"` to inject it into the live session. Until that API lands, the audit log serves as a queue that Kael can poll during startup.

---

## 8. Open Questions

- **Per-channel message filter:** should `receive` only forward messages from the operator's Discord username and ignore all others? Probably yes for the inbox channel; configurable per-channel via `gad-config.toml [bridge.discord.filters]`.
- **Daily outbound cap:** should `gad bridge discord send` enforce a daily message cap (similar to `feedback.askuserquestion.daily_cap`)? Low priority until echo is enabled, since the operator controls all outbound sends today.
- **Twilio webhook inbound server:** `gad bridge sms receive` and `gad bridge whatsapp receive` follow the same `http.createServer` pattern as `gad bridge discord receive`. Twilio signs webhooks with an `X-Twilio-Signature` header — the receive server should validate this before trusting inbound content. Not yet implemented; open for the next session.
- **Voice transcription pipeline:** Twilio Voice can call a TwiML URL, record, and post the MP3 to a webhook. Whisper on that audio → text → Kael chat message. This is the highest-friction path but covers the "call Kael" use case. Future phase.
