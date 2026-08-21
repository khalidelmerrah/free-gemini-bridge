# How we did all this — the full journey

A step-by-step account of how this research happened, so a future session (or a
human) can reconstruct every decision and repeat every step.

## 1. The request

User showed a working **"Codex Quota"** Hermes status-bar plugin
(`plugin.js` — a `useQuery` chip polling `ctx.rest('/quota')`) and asked for
"something similar with Google Gemini models" — connect Gemini models, login
based, **no API key**.

## 2. First discovery: no public quota API

- `GET generativelanguage.googleapis.com/v1beta/usage` → 404 (no such endpoint)
- The Gemini CLI (`@google/gemini-cli`, installed via
  `npm install -g @google/gemini-cli`) has **no quota command** (`gemini --help`)
- Conclusion: Google exposes no public Gemini quota API. A Codex-style chip was
  assumed impossible — until the user pointed us to a reference project.

## 3. The unlock: cockpit-tools (open source)

https://github.com/jlcodes99/cockpit-tools — a universal AI-IDE account manager
supporting Antigravity/Gemini, Codex, Copilot, Cursor. It proved two things:

**A. Tokens live on disk (no login needed).** Antigravity stores its OAuth
tokens in a SQLite DB. Decode chain (ported to `scripts/extract_gemini_token.py`):

```
%APPDATA%\Antigravity\User\globalStorage\state.vscdb
  → SELECT value FROM ItemTable WHERE key='antigravityUnifiedStateSync.oauthToken'
  → base64 decode
  → protobuf: iterate fields; field 1 (wire 2) = entry
  → entry field 1 = sentinel string ("oauthTokenInfoSentinelKey" or
     "authStateWithContextSentinelKey")
  → entry field 2 = Row protobuf → field 1 = base64(OAuthTokenInfo)
  → OAuthTokenInfo: field 1 = access_token, field 2 = "Bearer",
    field 3 = refresh_token, field 4 = expiry (unix), field 5 = id_token
```

**B. Quota comes from Google's internal Cloud Code API.** The Antigravity app
(and cockpit) call `v1internal:fetchAvailableModels` with a Bearer access token
and the app's User-Agent. Verified live on this machine: **25 models, real
remainingFraction + resetTime per model.**

## 4. Built the quota chip (works today)

- `plugins/gemini-quota/desktop/plugin.js` — status-bar chip, mirrors the Codex
  chip (`STATUSBAR_AREAS.right`, `useQuery` polling every 60s, `Tip` tooltip)
- `plugins/gemini-quota/dashboard/plugin_api.py` — Python backend (`APIRouter`)
  mounted at `/api/plugins/gemini-quota/*`; refreshes the access token with the
  Antigravity OAuth client, calls the quota API, normalizes the response
- `plugins/gemini-quota/dashboard/manifest.json` — `{"name":"gemini-quota","api":"plugin_api.py"}`
- Enabled via `hermes config set plugins.enabled '["gemini-quota"]'`
- **Verified end-to-end**: `logged_in:true`, plan=`steave.j.jenkins@gmail.com`,
  25 models at 100%, resets 23:35Z

## 5. The chat-model wall (the open problem)

For chat, the model API must be reachable. Tests with our access token:

| Endpoint | Result |
|---|---|
| `generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent` (Bearer) | ❌ `403 insufficient authentication scopes` |
| `v1beta/openai/chat/completions` (Bearer) | ❌ `401 missing credential` |

Cause: the model API requires scope `https://www.googleapis.com/auth/generative-language`,
and both usable OAuth clients return `403 restricted_client` / `unregistered
scope` when that scope is requested (verified by constructing auth URLs).
The Antigravity + GCA clients ship with `cloud-platform` only.

## 6. Login flows tested (for getting a token WITH the right scope)

| Flow | Result |
|---|---|
| Device flow (`oauth2.googleapis.com/device/code`) | ❌ `invalid client type` (both clients) |
| OOB flow (`urn:ietf:wg:oauth:2.0:oob`) | ❌ deprecated / rejected |
| Loopback flow (`redirect_uri=http://localhost:8765`) | ✅ **WORKS**, phone-completable |
| `generative-language` scope on GCA client auth URL | ❌ `restricted_client` (user's phone login hit this) |

**Phone login (proven, 2 min):** open the auth URL on the phone → sign in →
Google redirects to `localhost:8765` (fails — *expected*) → copy the full URL
from the address bar (it contains `?code=...`) → paste back → exchange
code+PKCE verifier for tokens. This is the standard remote-machine OAuth trick
(GitHub CLI / gcloud style). `scripts/gemini_phone_login.py` automates the
exchange; tokens saved to `~/.sharksms-outreach/gemini_tokens.json`.

## 7. The open thread (where the next session should dig)

The Gemini CLI (`gemini`) in GCA mode (`GOOGLE_GENAI_USE_GCA=true`) generates
through **`https://cloudcode-pa.googleapis.com`** (constant `CODE_ASSIST_ENDPOINT`
in the bundle) using only `cloud-platform` tokens — the same host family as the
quota API that already works. The exact generation method (a `v1internal:...`
RPC) is still undiscovered — see `docs/status.md` for the hunt plan. If found, a
tiny local OpenAI-compatible proxy can expose Gemini to Hermes as a plain
`base_url` provider with no scope changes needed.

## Environment (this machine, 2026-08-19)

- Hermes home: `C:\Users\admindev\AppData\Local\hermes`
- Working files: `C:\Users\admindev\.sharksms-outreach\` (tokens, scripts, creds)
- Antigravity DB: `C:\Users\admindev\AppData\Roaming\Antigravity\User\globalStorage\state.vscdb`
- Gemini CLI: `@google/gemini-cli@0.56.0` (npm global, Hermes node dir)
- Plugin dir: `C:\Users\admindev\AppData\Local\hermes\plugins\gemini-quota\`
- Skill: `C:\Users\admindev\AppData\Local\hermes\skills\autonomous-ai-agents\gemini-cli\SKILL.md`
