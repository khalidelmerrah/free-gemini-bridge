# Gemini → Hermes provider — STATUS: DONE (2026-08-26)

**Goal achieved:** Gemini (and the Antigravity model lineup) is selectable in Hermes as
a provider + models in the dropdown, using **the same Google auth Cockpit Tools already
manages** — no Gemini CLI login, no API key, no new browser flow.

## How it works

1. **Cockpit Tools** stores Antigravity Google OAuth refresh tokens per account
   (`~/.antigravity_cockpit/`, and obtainable plaintext via its data-transfer export).
2. **`gemini_cli_bridge.py`** (FastAPI, loopback `127.0.0.1:8787`, OpenAI-compatible):
   - refreshes the active account's token via `oauth2.googleapis.com/token`
     (public Antigravity OAuth client),
   - calls Gemini Code Assist directly:
     `POST https://daily-cloudcode-pa.googleapis.com/v1internal:generateContent`
     identifying as the **Antigravity IDE client** (`User-Agent:
     antigravity/1.20.5 windows/amd64 google-api-nodejs-client/10.3.0`,
     `x-goog-api-client: gl-node/22.21.1`; `loadCodeAssist` metadata
     `ideType: ANTIGRAVITY` etc. → grants `free-tier`),
   - serves `GET /v1/models` (live from `fetchAvailableModels`) and
     `POST /v1/chat/completions` (non-stream + SSE stream).
3. **Hermes config** has custom provider `providers.gemini-cli` →
   `http://127.0.0.1:8787/v1` with ~12 models (gemini-3.6-flash-high,
   gemini-3.1-pro-high, claude-sonnet-4-6, claude-opus-4-6-thinking,
   gpt-oss-120b-medium, …).

## Account switching (Cockpit-style)

- Bridge **auto-follows Cockpit's active Antigravity account** by reading
  `~/.antigravity_cockpit/accounts.json` → `current_account_id` → email.
  Switch in Cockpit → Hermes Gemini follows automatically.
- Manual override: `POST /v1/account/switch {"email": "..."}`;
  re-enable follow: `POST /v1/account/follow-cockpit {"follow": true}`.
- Status: `GET /v1/account`, `GET /health`.

## Ops

- Start: `start_bridge.bat` (scheduled task `HermesGeminiBridge`, ONLOGON).
- Manual: `cd C:\Users\admindev\gemini-hermes && <venv python> -m uvicorn gemini_cli_bridge:app --host 127.0.0.1 --port 8787`
  (venv python: `C:\Users\admindev\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe`).
- Tests: `python -m unittest discover -s tests` (5 tests, no network).
- Secrets: `accounts.json` (email → refresh_token) is gitignored. Do NOT commit it.
  Keep a backup (Cockpit data-transfer export) somewhere safe.

## Key findings (research log)

- `cloudcode-pa.googleapis.com/v1internal:*` RPCs (colon syntax!): `loadCodeAssist`,
  `onboardUser`, `fetchAvailableModels`, `retrieveUserQuotaSummary`, `generateContent`,
  `countTokens`, `listExperiments`.
- Generic Gemini CLI UA / `IDE_UNSPECIFIED` metadata → account is `standard-tier`
  (paid) and `generateContent` fails: `SUBSCRIPTION_REQUIRED #3501` (no project) or
  `IAM_PERMISSION_DENIED` on `projects/cloudshell-gca`.
- Antigravity-branded metadata → `currentTier: free-tier` (Gemini Code Assist for
  individuals) → `generateContent` works with project omitted or `cloudshell-gca`.
- All 4 Cockpit Antigravity accounts verified generating.
- Quota payload is `{}` or `{"project": id}` (NOT `{metadata, mode}` — that 400s).
- Gemini CLI's own auth store is `google_accounts.json` + per-account tokens; a
  `credentials.json` with the Antigravity client is NOT honored by the CLI — but we
  don't need the CLI at all anymore.
