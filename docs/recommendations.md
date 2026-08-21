# Recommendations

## For making Gemini a chat model in Hermes (the main goal)

1. **Dig the generation endpoint out of the gemini-cli bundle first** — it's the
   highest-leverage 30 minutes of work left. The CLI demonstrably generates with
   plain `cloud-platform` tokens through `cloudcode-pa.googleapis.com`; we just
   need the RPC name. The scripts in `scripts/` (find_service.py,
   find_endpoints2.py, find_gen.py) already point at the right files; a
   network capture during a CLI run (`GOOGLE_GENAI_USE_GCA=true gemini -p "hi"`)
   is the fallback.
2. **Proxy, don't patch.** A ~100-line local OpenAI-compatible proxy
   (`localhost:8787/v1/chat/completions` → the internal RPC) plugs into Hermes as
   a plain custom provider — **zero edits to Hermes internals**, survives updates.
3. **Do not chase the `generative-language` scope.** Both OAuth clients are
   `restricted_client` for it; Google won't grant it through a public login.
   Accept `cloud-platform` + internal endpoints as the working auth model.
4. **Park the API-key path entirely** — user requirement is login-only, and the
   internal-API route already satisfies it with better privacy.

## For the quota chip

5. **Keep the chip as-is; harden later.** It works with zero user-facing setup.
   If Google changes the quota API, the failure mode is a "Gemini !" chip —
   the tooltip already surfaces the error.
6. **Token fallback order already implemented** in `plugin_api.py`:
   stored tokens → refresh → re-extract from `state.vscdb`. Keep that order;
   don't cache access tokens longer than ~5 min (1h expiry).
7. **Consider a second source of truth** (optional): the chip could also read the
   Gemini CLI's own creds once the CLI login exists — one more refresh-token
   source if Antigravity is ever uninstalled.

## For the Gemini CLI skill

8. **Finish the CLI login** (`login_gemini.bat`, phone-completable) — it unlocks
   delegated coding today, independent of the chat-model work. The skill is
   already installed and documented.
9. **Fix the broken claude-mem hook** in `~/.gemini/settings.json` (a stale
   bun/powershell command prints a harmless error on every CLI run) — cosmetic,
   but makes CLI output cleaner for the agent.

## Guardrails (do not skip)

10. **Tokens are the crown jewels.** `gemini_tokens.json` (refresh token) must
    stay off GitHub, off chat, off memory. Revocation path documented in
    `pickup-guide.md` §5.
11. **The phone login flow is proven — reuse it**, don't rebuild. Any new OAuth
    needs: same GCA client, `localhost:8765` listener, PKCE, paste-back.
12. **If Google tightens the internal APIs** (rate limits, new auth), the
    fallback is the Gemini CLI itself as the inference path — the CLI is a
    supported Google product; a wrapper around it is the most durable option.

## Honest expectations

- The quota chip is **done and stable** — this was the win.
- Chat-model integration is **one solid session away** if the endpoint hunt
  succeeds; if Google blocks the internal API, the CLI-wrapper fallback still
  delivers it, just slower.
- Everything here was verified against the live environment on 2026-08-19;
  Google moves fast, so re-verify endpoints before assuming they still work.
