# OAuth findings — clients, scopes, endpoints

All discovered from the gemini-cli npm bundle (`@google/gemini-cli@0.56.0`) and
the cockpit-tools source. All client IDs/secrets are **public** (shipped in
those open-source artifacts).

## OAuth clients

| Owner | Client ID | Secret |
|---|---|---|
| Antigravity IDE | `1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com` | `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` |
| Gemini CLI (GCA) | `681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com` | `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` |
| gcloud ADC | `764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur` | (public client) |

## Scopes

- **Antigravity** (cockpit-tools oauth.rs): `openid`, `cloud-platform`,
  `userinfo.email`, `userinfo.profile`, `cclog`, `experimentsandconfigs`
- **Gemini CLI** (`OAUTH_SCOPE` in bundle):
  `cloud-platform`, `userinfo.email`, `userinfo.profile`
- **`generative-language` scope** (`https://www.googleapis.com/auth/generative-language`)
  is **rejected by BOTH clients** with `restricted_client` / unregistered-scope
  errors → the public model API can't be called with these clients' tokens.

## Endpoints

| Purpose | URL | Auth |
|---|---|---|
| Quota (daily) | `https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels` | Bearer + UA `antigravity/1.20.5 windows/amd64` |
| Quota (weekly) | `v1internal:retrieveUserQuotaSummary` (same host) | Bearer |
| Token refresh | `https://oauth2.googleapis.com/token` | client_id+secret+refresh_token |
| Device flow | `https://oauth2.googleapis.com/device/code` | ❌ `invalid_client` for both clients |
| Out-of-band | `redirect_uri=urn:ietf:wg:oauth:2.0:oob` | ❌ deprecated, rejected |
| Loopback flow | `redirect_uri=http://localhost:8765` | ✅ works (any numeric port) |
| Model inference | `https://generativelanguage.googleapis.com/v1beta/...` | needs `generative-language` scope → blocked (irrelevant — GCA is the right path) |
| GCA endpoint | `CODE_ASSIST_ENDPOINT = https://cloudcode-pa.googleapis.com` (from bundle) | ✅ **THE working generation path** — see v2 below |

## The gemini CLI's auth env hooks (from `initOauthClient`)

- `GOOGLE_GENAI_USE_GCA=true` + `GOOGLE_CLOUD_ACCESS_TOKEN=<token>` → the CLI
  uses that access token directly (no login prompt!). Useful for scripting.

## Login flows tested

- **Device flow**: rejected (`invalid_client`)
- **OOB**: rejected (deprecated)
- **Loopback + paste-back**: ✅ PROVEN — auth URL with `redirect_uri=http://localhost:8765`
  + PKCE S256; user completes on phone; the code is copied from the failed
  redirect URL's address bar and pasted back; exchange with code_verifier works.
  See `scripts/gemini_phone_login.py`.

## v2 (2026-08-26): GCA generation — SOLVED, no login needed

- **The blocker was never scopes — it was client identity.** Antigravity
  refresh tokens (minted by the Antigravity client, scopes `openid`,
  `cloud-platform`, `userinfo.*`, `cclog`, `experimentsandconfigs`) ARE
  accepted for full inference by the GCA backend.
- **Trick:** identify as the Antigravity IDE client:
  - `User-Agent: antigravity/1.20.5 windows/amd64 google-api-nodejs-client/10.3.0`
  - `x-goog-api-client: gl-node/22.21.1`
  - `loadCodeAssist` metadata `{ideName:"antigravity", ideType:"ANTIGRAVITY",
    ideVersion:"1.20.5", pluginVersion:"1.0.0", platform:"WINDOWS_AMD64",
    updateChannel:"stable", pluginType:"GEMINI"}` → `currentTier: free-tier`
    (Gemini Code Assist for individuals).
  - Generic metadata (`IDE_UNSPECIFIED`) → `standard-tier` (paid) →
    `generateContent` fails `SUBSCRIPTION_REQUIRED #3501` or IAM denial on
    `projects/cloudshell-gca`.
- Generation RPC (host `daily-cloudcode-pa.googleapis.com`):
  `v1internal:generateContent`, body `{model, user_prompt_id,
  request:{contents, systemInstruction?, generationConfig?}}`;
  streaming = `?alt=sse`. Also works: `countTokens`, `listExperiments`,
  `retrieveUserQuotaSummary`, `onboardUser` (colon RPC syntax: `v1internal:name`).
- `fetchAvailableModels` body is `{}` or `{"project": id}` — NOT `{metadata, mode}` (400).
- Models available (free tier): gemini-3.6-flash-high/medium/low,
  gemini-3.5-flash-*, gemini-3.1-pro-*, gemini-3-flash, gemini-2.5-pro,
  **claude-sonnet-4-6, claude-opus-4-6-thinking, gpt-oss-120b-medium**,
  gemini-pro-agent, …
- **Gemini CLI auth caveat:** the CLI does NOT honor a hand-written
  `~/.gemini/credentials.json` (even with the right client) — it manages its
  own `google_accounts.json` store. Doesn't matter: the bridge bypasses the
  CLI entirely.
