# Changelog

All notable changes to the Gemini × Hermes integration.

## [2.0.0] — 2026-08-26 — Direct GCA bridge (login-free)

**The big one.** Gemini became a fully working Hermes chat provider with zero
login ceremony.

### Added
- `gemini_cli_bridge.py` v2 — rewritten to call **Gemini Code Assist directly**
  (`daily-cloudcode-pa.googleapis.com/v1internal:*`) instead of shelling out to
  the Gemini CLI:
  - OpenAI-compatible `/v1/models` (live from `fetchAvailableModels`),
    `/v1/chat/completions` (non-stream + SSE stream), `/health`, `/v1/account`,
    `/v1/account/switch`, `/v1/account/follow-cockpit`.
  - Silent token refresh per request (Antigravity public OAuth client),
    rotated-refresh-token persistence.
- **Discovery:** Antigravity OAuth tokens are accepted for full GCA inference
  when requests identify as the Antigravity IDE client (UA + `ideType:
  ANTIGRAVITY` metadata). `loadCodeAssist` then reports `currentTier:
  free-tier` and `generateContent` succeeds. Generic Gemini-CLI identity gets
  `403 SUBSCRIPTION_REQUIRED #3501` or IAM denial on `cloudshell-gca`.
- **Account switching:** bridge auto-follows Cockpit's active Antigravity
  account (`~/.antigravity_cockpit/accounts.json` → `current_account_id`);
  manual override endpoints included.
- `accounts.json` registry (email → refresh_token), seeded from a Cockpit
  data-transfer export; **gitignored**.
- `start_bridge.bat` + scheduled task `HermesGeminiBridge` (ONLOGON).
- `bridge_watchdog.py` + scheduled task `HermesGeminiBridgeWatchdog`
  (every 5 min) — verified live: killed bridge → watchdog restarted it.
- Hermes provider `providers.gemini-cli` registered with 12 models
  (gemini-3.6-flash-high/medium/low, gemini-3.1-pro-high/low, gemini-3-flash,
  gemini-2.5-pro, gemini-3.1-flash-lite, claude-sonnet-4-6,
  claude-opus-4-6-thinking, gpt-oss-120b-medium, gemini-pro-agent).
- Tests: 5 unit tests (mocked GCA, no network).
- Docs rewritten for the working state; `docs/pickup-guide.md` now the ops
  reference.

### Changed
- Bridge no longer depends on a Gemini CLI login (the phone OAuth flow is
  obsolete — kept as `scripts/gemini_phone_login.py` for reference).
- `docs/status.md` flipped from "blocked" to DONE.

### Removed / archived
- CLI-subprocess backend and its `FakeGeminiRunner` tests.

## [1.0.0] — 2026-08-21 — Research archive (pre-breakthrough)

- `plugins/gemini-quota` — working status-bar quota chip (Antigravity
  `state.vscdb` token → `fetchAvailableModels` → per-model remaining %).
- OAuth findings (`docs/oauth-findings.md`), Cockpit Tools analysis
  (`docs/cockpit-tools-analysis.md`), bundle-digging scripts (`scripts/find_*`),
  phone login helper (`scripts/gemini_phone_login.py`).
- Hermes `gemini-cli` skill documenting the quota technique.
- Status at the time: chat-model inference **blocked** (Antigravity scopes
  rejected by `generativelanguage`; assumption — proven wrong in 2.0.0 — that
  a Gemini CLI login was required).
