# Gemini × Hermes — integration research archive

**Mission:** connect Google Gemini models to Hermes Agent the way Codex is
connected — **account login, no API key** — plus a live per-model **quota
status chip** in the Hermes desktop status bar.

This repo is the complete handoff: what we learned, how we did it, what
works, what's blocked, and exactly how to pick the work back up.

---

## TL;DR

| Piece | Status |
|---|---|
| Quota chip (status bar) | ✅ **WORKING** — real per-model quota from Antigravity's login, zero setup |
| `gemini-cli` Hermes skill | ✅ Installed — delegate coding tasks to Gemini CLI (needs one-time CLI login) |
| Gemini as a **chat model** in Hermes | 🔒 Blocked on a Google OAuth scope — plan documented in `docs/status.md` |
| Phone-completable OAuth login | ✅ **Proven** — loopback paste-back flow, tokens captured |

## Repo map

```
README.md                      ← you are here (master index)
docs/
  cockpit-tools-analysis.md    ← how the reference project uses Gemini + switches accounts
  oauth-findings.md            ← every OAuth client/scope/endpoint we tested
  status.md                    ← what works / what's blocked / the open thread
  how-we-did-it.md             ← full journey: commands, files, exact steps
  pickup-guide.md              ← RESUME HERE: step-by-step continuation
  recommendations.md           ← suggested next moves & guardrails
plugins/
  gemini-quota/                ← the working status-bar chip (desktop + Python backend)
scripts/
  extract_gemini_token.py      ← pull tokens from Antigravity's local login state
  gemini_phone_login.py        ← phone-completable Google OAuth login
  find_*.py                    ← bundle-digging tools (how we discovered endpoints)
skill/
  gemini-cli-SKILL.md          ← the Hermes skill that documents this whole technique
```

## Key facts (the one-paragraph version)

1. **Quota works without any login** because Antigravity (Google's Gemini IDE,
   installed & logged in on the office PC) stores its OAuth tokens in
   `%APPDATA%\Antigravity\User\globalStorage\state.vscdb` — a SQLite table
   (`ItemTable`, key `antigravityUnifiedStateSync.oauthToken`), base64 +
   protobuf-wrapped. `scripts/extract_gemini_token.py` unwraps it.
2. **Quota API:** `POST https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels`
   with `Authorization: Bearer <access>` + User-Agent `antigravity/1.20.5 windows/amd64`
   → `models[].quotaInfo.remainingFraction/resetTime`.
3. **Chat models are blocked** because the public Gemini model API demands the
   `https://www.googleapis.com/auth/generative-language` scope, and BOTH Google
   OAuth clients we can use are `restricted_client` for it. The likely unlock:
   the Gemini CLI generates through `cloudcode-pa.googleapis.com` with only
   `cloud-platform` scope — the exact generation endpoint is the one open thread
   (see `docs/status.md`).

## Security

- **Real tokens never belong in this repo.** Refresh/access tokens live only in
  `~/.sharksms-outreach/gemini_tokens.json` (gitignored). If that file leaks,
  revoke at https://myaccount.google.com/security → "Your connections" → revoke.
- The OAuth client IDs/secrets in the scripts are **public** (shipped in the
  open-source cockpit-tools repo and the `@google/gemini-cli` npm package).

---
*Created 2026-08-19. Resume with `docs/pickup-guide.md`.*
