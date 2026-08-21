# Gemini × Hermes — integration research archive

**Goal:** connect Google Gemini models to Hermes Agent (login-based, NO API key),
mirroring how Codex is integrated — plus a live per-model **quota status chip**
in the Hermes desktop status bar.

**Status (2026-08-19):**
- ✅ **Gemini Quota chip — WORKING** (real quota, no login needed — reuses the
  local Antigravity IDE login)
- ✅ **Gemini CLI (`@google/gemini-cli` v0.56.0) — installed**, login helper ready
- ✅ **Phone-completable OAuth login — PROVEN** (loopback + paste-back flow
  completed successfully; tokens saved locally)
- ❌ **Gemini as a chat model — BLOCKED** (scope restriction, see docs/status.md)

---

## What's in here

```
docs/
  cockpit-tools-analysis.md   # How cockpit-tools uses Gemini & switches accounts
  oauth-findings.md           # Clients, scopes, endpoints discovered (the gold)
  status.md                   # Working / blocked / next steps
plugins/gemini-quota/         # The status-bar chip plugin (desktop + backend)
scripts/
  extract_gemini_token.py     # Pull OAuth tokens from Antigravity's state.vscdb
  gemini_phone_login.py       # Phone-completable OAuth login (loopback + paste-back)
  find_*.py                   # Bundle/endpoint diggers (how findings were made)
skill/gemini-cli-SKILL.md     # The Hermes skill (delegation + quota technique)
```

## Security

- **Real credentials are NOT committed.** Refresh/access tokens live only in
  `~/.sharksms-outreach/gemini_tokens.json` (chmod 600) and `creds.env` —
  both are gitignored here.
- OAuth client IDs + secrets in the scripts are **public** (published in the
  open-source cockpit-tools repo and the gemini-cli npm bundle) — they are
  Google's own client credentials, not user credentials.
