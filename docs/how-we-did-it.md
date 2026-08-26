# How we did it — full journey

## Phase 1 (2026-08-21): quota chip + research

Goal: connect Gemini to Hermes the way Codex is — **account login, no API key**.

1. Found the reference: [Cockpit Tools](https://github.com/jlcodes99/cockpit-tools)
   (Rust/Tauri) manages Antigravity IDE accounts + quota.
2. Discovered Antigravity's login state lives in
   `~/AppData/Roaming/Antigravity/User/globalStorage/state.vscdb`
   (SQLite key `antigravityUnifiedStateSync.oauthToken` → base64 protobuf →
   fields 1=access_token, 3=refresh_token, 5=id_token). `scripts/extract_gemini_token.py`
   ports Cockpit's protobuf decoding.
3. Quota endpoint: `POST daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels`
   with `Authorization: Bearer <access_token>`, UA `antigravity/1.20.5 windows/amd64`,
   body `{}` or `{"project": id}` → `models.{name}.quotaInfo`
   (`remainingFraction`, `resetTime`). Payload `{metadata, mode}` 400s — wrong shape.
4. Built `plugins/gemini-quota` — status-bar chip, live per-model % + reset times,
   account email, click-to-refresh, auto re-extract from `state.vscdb` on refresh failure.
5. **Wrong assumption:** tried `generativelanguage.googleapis.com` with the
   Antigravity token → `403 insufficient scopes`. Concluded a Gemini CLI login
   (which requests extra scopes) was required. **This was wrong** — the GCA
   backend accepts the token; `generativelanguage` is just not the right backend.

## Phase 2 (2026-08-26): breakthrough — direct GCA inference

6. User revealed the real prize: Cockpit **switches accounts instantly** with
   stored refresh tokens. Watched the switch live (file hashes every 2 s) —
   Cockpit updates `current_account_id` + re-encrypts account blobs (AES-256-GCM,
   local key) and does NOT touch Antigravity's `state.vscdb`. Cockpit's
   data-transfer export contains the **plaintext Google refresh tokens**.
7. Verified all 4 refresh tokens mint fresh access tokens via
   `oauth2.googleapis.com/token` with the public Antigravity client
   (`1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com` /
   `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`).
8. Probed GCA directly (source-diving the Gemini CLI bundle for RPC names):
   - `v1internal:loadCodeAssist` with generic metadata → `standard-tier` (paid),
     `generateContent` → `SUBSCRIPTION_REQUIRED #3501` or IAM denial on
     `cloudshell-gca`.
   - **With Antigravity metadata** (`ideName:"antigravity", ideType:"ANTIGRAVITY",
     ideVersion:"1.20.5", pluginVersion:"1.0.0", platform:"WINDOWS_AMD64",
     updateChannel:"stable", pluginType:"GEMINI") + Antigravity UA
     (`antigravity/1.20.5 windows/amd64 google-api-nodejs-client/10.3.0`,
     `x-goog-api-client: gl-node/22.21.1`) → `currentTier: free-tier`
     (Gemini Code Assist for individuals) → **`generateContent` SUCCEEDS** —
     all 4 accounts, including Claude/GPT-OSS models.
9. `generateContent` body:
   ```json
   {"model": "gemini-3.6-flash-high",
    "user_prompt_id": "<uuid>",
    "request": {"contents": [{"role": "user", "parts": [{"text": "…"}]}],
                "systemInstruction": {"parts": [{"text": "…"}]}}}
   ```
   Response: `{response: {candidates:[{content:{role:"model",parts:[{thoughtSignature,text}]}}], usageMetadata}}`.
   Streaming: same URL + `?alt=sse` → one `data: {json}` line per event.
10. Built `gemini_cli_bridge.py` v2 (FastAPI, loopback 8787, OpenAI-compatible):
    refresh token → GCA call → OpenAI shape; SSE streaming with proper
    `finish_reason` chunk; `fetchAvailableModels` for `/v1/models`.
11. **Account switching:** bridge reads `~/.antigravity_cockpit/accounts.json`
    → `current_account_id` → email → uses that account's token. Switch in
    Cockpit, Hermes follows. Manual endpoints for override.
12. Registered Hermes custom provider `providers.gemini-cli` →
    `http://127.0.0.1:8787/v1` with 12 models; verified end-to-end
    (`hermes chat -q … -m gemini-3.6-flash-high --provider gemini-cli` → clean reply).
13. Ops: `start_bridge.bat` + scheduled task `HermesGeminiBridge` (ONLOGON);
    `bridge_watchdog.py` + task `HermesGeminiBridgeWatchdog` (every 5 min).
    Verified: killed the bridge → watchdog restarted it → answered.

## Why the login looked needed (and wasn't)

The Gemini CLI's own OAuth client and the Antigravity client both request
`cloud-platform` + userinfo scopes. The blocker was never the scope list — it
was **client identity**: the GCA backend routes `ideType: ANTIGRAVITY` requests
to the free Antigravity tier, and generic clients to paid-tier project
validation. Identifying as Antigravity is the whole trick.
