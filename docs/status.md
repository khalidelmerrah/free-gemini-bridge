# Status — 2026-08-26

## ✅ DONE: Gemini as a Hermes chat provider

| Piece | Status |
|---|---|
| Gemini as a **chat model** in Hermes | ✅ **WORKING** — provider `gemini-cli` → local bridge → GCA, verified end-to-end |
| Auth | ✅ Zero setup — reuses Cockpit Tools' Antigravity Google refresh tokens; no CLI login, no API key |
| Account switching | ✅ Auto-follows Cockpit's active account; manual override endpoints |
| Model lineup | ✅ 25 models on the account incl. Gemini 3.6/3.1/3, Claude Sonnet 4.6, Claude Opus 4.6, GPT-OSS 120B |
| Streaming | ✅ SSE (`stream: true`), proper finish_reason |
| Quota chip (status bar) | ✅ Still working (unchanged from v1) |
| Ops resilience | ✅ Logon auto-start + 5-min watchdog (both verified) |
| Tests | ✅ 5/5 (mocked GCA, no network) |

## Known limits (next steps)

1. **Tool/function calling** not yet translated in the bridge — plain chat is
   solid; agentic tool use requires mapping OpenAI tools → GCA Vertex-style
   `tools` in `generateContent`.
2. GCA streaming returns whole events per SSE chunk (no token-level
   incremental streaming through this RPC).
3. Free Antigravity tier quota (weekly + 5h buckets) applies — real, visible
   in the quota chip.

## History

- **2026-08-21** — research archive: quota chip working; chat model believed
  blocked on OAuth scope.
- **2026-08-26** — breakthrough: Antigravity tokens accepted by GCA with
  Antigravity client identity → bridge v2 built, deployed, verified.
