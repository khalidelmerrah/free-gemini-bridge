# Status

## ✅ Working

1. **Gemini Quota chip** (Hermes desktop plugin `plugins/gemini-quota`)
   - Reads quota from Antigravity's local login state — no login, no API key
   - Shows per-model `remainingFraction` + reset times + account email
   - Auto-refreshes token; auto-re-extracts from `state.vscdb` if refresh fails
   - Enabling: `hermes config set plugins.enabled '["gemini-quota"]'`
   - Verified: 25 models, real data (Gemini 3.7/2.5/3.1, Claude Sonnet 4.6, GPT-OSS…)

2. **Phone-completable OAuth login** (`scripts/gemini_phone_login.py`)
   - Proven end-to-end on 2026-08-19 (user completed from phone, code captured,
     tokens saved to `~/.sharksms-outreach/gemini_tokens.json`)
   - Loopback redirect + PKCE; code travels in the pasted URL text

3. **Gemini CLI installed** — `@google/gemini-cli@0.56.0`; `gemini-cli` Hermes
   skill installed (delegation + this technique documented)

## ❌ Blocked: Gemini as a CHAT model in Hermes

**Why:** the public model API (`generativelanguage.googleapis.com`) requires the
`generative-language` OAuth scope. Neither the Antigravity client nor the GCA
client can be issued that scope (`restricted_client`). Tokens with
`cloud-platform` get `403 insufficient authentication scopes` on model calls
(verified with both clients' real tokens).

**The likely unlock (unexplored):** the Gemini CLI's **GCA mode** generates
through `https://cloudcode-pa.googleapis.com` (`CODE_ASSIST_ENDPOINT`), which
accepts cloud-platform tokens (same host family as the quota API that works).
The generation method path on that host was not yet dug out of the bundle
(open thread: grep the bundle for `v1internal` paths next to `CODE_ASSIST_ENDPOINT`).

**Alternative quick win:** `GOOGLE_GENAI_USE_GCA=true GOOGLE_CLOUD_ACCESS_TOKEN=<token> gemini -p "..."` —
the CLI accepts an env-supplied token, so Hermes could delegate to the CLI with
our Antigravity token (proven quota access) instead of proxying the API directly.

## Next steps (when resumed)

1. Find the cloudcode-pa generation path in the gemini-cli bundle
   (`v1internal:*` methods near `CODE_ASSIST_ENDPOINT`)
2. Test a generation call with the Antigravity access token
3. If it works: build the local OpenAI-compat proxy → register as Hermes
   `custom` provider → Gemini appears in the model picker
