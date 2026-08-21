# How cockpit-tools uses Gemini & switches accounts

Source: https://github.com/jlcodes99/cockpit-tools (MIT, Rust + TS/Tauri).
A "universal AI-IDE account manager" for Antigravity (Gemini), Codex, Copilot,
Cursor, etc. — with quota monitoring and one-click account switching.

## The two tricks that matter

### 1. Reading Gemini quota WITHOUT any login

1. Antigravity stores its OAuth login in a SQLite DB:
   `%APPDATA%/Antigravity/User/globalStorage/state.vscdb`
2. Query: `SELECT value FROM ItemTable WHERE key='antigravityUnifiedStateSync.oauthToken'`
3. The value is base64 → protobuf topic → entry with sentinel
   `oauthTokenInfoSentinelKey` → Row.value → base64(OAuthTokenInfo protobuf) →
   **field 3 = refresh_token** (also access_token, expiry, id_token)
   (port: `crates/cockpit-core/src/utils/protobuf.rs`)
4. Refresh the access token via `oauth2.googleapis.com/token` using the
   **Antigravity OAuth client** (see oauth-findings.md)
5. Call the quota API:
   `POST https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels`
   - `Authorization: Bearer <access_token>`
   - `User-Agent: antigravity/1.20.5 windows/amd64` (spoofed!)
   - body `{}` (or `{"project": "<id>"}`)
   - response: `{ models: { "<model>": { displayName, quotaInfo: { remainingFraction, resetTime } } } }`
   - plus `v1internal:retrieveUserQuotaSummary` for weekly/5h buckets,
     `v1internal:onboardUser`, `v1internal:loadCodeAssist` for tier/credits

### 2. Switching accounts

Cockpit keeps its own account store (access+refresh+project tokens) and
**writes the chosen account's token back into Antigravity's local
`antigravityUnifiedStateSync.oauthToken` slot** — the IDE then uses whatever
account was injected. (That's the "switch account" mechanism.)

## Lessons applied here

- The quota API works with the Antigravity token — this powers the
  `gemini-quota` Hermes status chip with **zero user login**.
- The same token is **rejected by the model inference API**
  (`generativelanguage.googleapis.com`, 403 insufficient scopes) — the chat
  path needs different scopes/endpoints (see status.md).
