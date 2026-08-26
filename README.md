# Gemini × Hermes — Gemini as a first-class Hermes provider

**Status: ✅ WORKING (2026-08-26)** — Gemini models (plus the full Antigravity
lineup: Claude Sonnet 4.6, Claude Opus 4.6, GPT-OSS 120B, …) are selectable in
Hermes' model dropdown, authenticated with **the same Google accounts Cockpit
Tools already manages** — no Gemini CLI login, no API key, no new browser flow.

---

## What this is

A small **localhost OpenAI-compatible bridge** that connects Hermes Agent to
Google's **Gemini Code Assist (GCA) backend** using the OAuth refresh tokens
stored by [Cockpit Tools](https://github.com/jlcodes99/cockpit-tools) for
Antigravity IDE accounts.

```
┌────────────┐   OpenAI API   ┌────────────────────┐   Bearer + Antigravity UA   ┌──────────────────────────────┐
│   Hermes   │ ─────────────▶ │ gemini_cli_bridge  │ ──────────────────────────▶ │ daily-cloudcode-pa.googleapis│
│ (provider  │ ◀───────────── │ 127.0.0.1:8787     │ ◀────────────────────────── │ .com/v1internal:generate…    │
│  gemini-cli│    SSE stream  │ (FastAPI, Python)  │   refresh token every call  └──────────────────────────────┘
└────────────┘                └────────────────────┘
                                     │
                                     ▼ reads
                        ~/.antigravity_cockpit/accounts.json
                        (Cockpit's active account → auto-follow)
```

**Key discovery:** Google's GCA backend accepts Antigravity OAuth tokens for
full model inference — *only when the request identifies as the Antigravity
IDE client* (User-Agent `antigravity/1.20.5 …` + `loadCodeAssist` metadata
`ideType: ANTIGRAVITY`). Generic Gemini-CLI identity gets `403
SUBSCRIPTION_REQUIRED #3501`. Details in `docs/how-we-did-it.md`.

## Features

- **OpenAI-compatible API** (`/v1/models`, `/v1/chat/completions` incl. SSE
  streaming) — works with any OpenAI client, not just Hermes.
- **Zero-setup auth** — reuses Cockpit's existing Antigravity Google logins
  (4 accounts on this machine, one per Google account).
- **Account switching like Cockpit** — the bridge *auto-follows* Cockpit's
  active account (`current_account_id`), or switch explicitly via
  `POST /v1/account/switch {"email": …}`.
- **Live model list** — `/v1/models` returns the account's real available
  models + quota from `fetchAvailableModels`.
- **Self-healing ops** — starts at logon (scheduled task) and a watchdog
  restarts it within 5 minutes if it ever dies.
- **Secure** — binds `127.0.0.1` only; refresh tokens never leave this
  machine; the registry file is gitignored.

## Quick start (this machine — already deployed)

1. Bridge runs automatically (task `HermesGeminiBridge` at logon + watchdog
   `HermesGeminiBridgeWatchdog` every 5 min).
2. Hermes config already has the provider:
   ```yaml
   providers:
     gemini-cli:
       name: Gemini (CLI login)
       api: http://127.0.0.1:8787/v1
       transport: chat_completions
       default_model: gemini-3.6-flash-high
       models: [gemini-3.6-flash-high, gemini-3.1-pro-high, gemini-3-flash,
                gemini-2.5-pro, claude-sonnet-4-6, claude-opus-4-6-thinking,
                gpt-oss-120b-medium, gemini-pro-agent, …]
       discover_models: true
   ```
3. Restart Hermes → pick **Gemini (CLI login)** in the model dropdown.

Manual start (if ever needed):
```bat
cd C:\Users\admindev\gemini-hermes
C:\Users\admindev\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe -m uvicorn gemini_cli_bridge:app --host 127.0.0.1 --port 8787
```

## API

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness + active account + follow mode |
| `GET /v1/models` | live model list (from GCA quota API) |
| `POST /v1/chat/completions` | chat (OpenAI shape; `stream: true` → SSE) |
| `GET /v1/account` | active account, follow mode, available accounts |
| `POST /v1/account/switch` | `{"email": "…"}` — explicit override |
| `POST /v1/account/follow-cockpit` | `{"follow": true\|false}` — re-enable Cockpit sync |

## Ops & troubleshooting

- **Logs:** `bridge.log` (uvicorn), `bridge-watchdog.log`.
- **Bridge down?** Watchdog fixes within 5 min; or run `start_bridge.bat`.
- **Port busy (8787)?** Watchdog detects and won't kill foreign processes —
  change `PORT` in `gemini_cli_bridge.py` + `bridge_watchdog.py` + Hermes
  config `api:` together.
- **New Google account?** Add its refresh token to `accounts.json` (from a
  Cockpit data-transfer export) and it appears in `/v1/account` immediately.
- **Secrets:** `accounts.json` (email → refresh_token) is gitignored. Back it
  up via Cockpit's export. Never commit it.

## Repo map

```
README.md                    ← you are here
CHANGELOG.md                 ← version history
gemini_cli_bridge.py         ← the bridge (FastAPI, OpenAI-compatible)
bridge_watchdog.py           ← self-heal watchdog
start_bridge.bat             ← logon auto-start
tests/                       ← unit tests (no network)
scripts/                     ← research tools (token extraction, endpoint digging, legacy login helper)
plugins/gemini-quota/        ← status-bar quota chip (desktop + Python backend) — still works
skill/gemini-cli-SKILL.md    ← the Hermes skill documenting this technique
docs/
  pickup-guide.md            ← ops + key findings (current)
  how-we-did-it.md           ← full research journey
  oauth-findings.md          ← OAuth clients/scopes/endpoints tested
  cockpit-tools-analysis.md  ← how the reference project works
  status.md                  ← current status
  recommendations.md         ← next steps
```

## Roadmap / known limits

- Free Antigravity tier quota applies (weekly + 5-hour buckets — see the
  quota chip).
- Tool/function calling is not yet translated in the bridge — plain chat
  works; agentic tool use is the next step.
- Streaming delivers whole GCA events per SSE chunk (GCA does not stream
  tokens incrementally through this RPC).
