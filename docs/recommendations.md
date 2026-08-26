# Recommendations / next steps

Current state is **working**. These are the valuable next moves, in order.

## 1. Tool / function calling in the bridge (highest value)
Hermes agents rely on tool calls. The GCA `generateContent` request supports
Vertex-style tools (`tools: [{functionDeclarations: [{name, description,
parameters}]}]`); the bridge's `_openai_to_gca` doesn't map them yet.
- Map OpenAI `tools` → Vertex `functionDeclarations`; parse
  `candidates[].content.parts[].functionCall` back into OpenAI
  `tool_calls`; feed `functionResponse` parts back in.
- Verify with `hermes chat -q "what time is it" -m gemini-3.6-flash-high --provider gemini-cli`
  (forces a tool call).

## 2. Account UX
- A tiny Hermes plugin or slash command to list/switch bridge accounts
  (`/gemini account`, `/gemini switch <email>`) instead of raw curl.
- Optional: bridge endpoint to refresh the quota chip data so chip + provider
  share the same account view.

## 3. Hardening
- Watchdog already covers crashes; consider `--reload` off (it is), log
  rotation for `bridge.log`.
- Registry backup reminder: keep a Cockpit data-transfer export somewhere
  safe (off-VPS) — it's the recovery path for `accounts.json`.

## 4. Research breadcrumbs (for later)
- GCA `countTokens`, `listExperiments`, `retrieveUserQuotaSummary` all work
  with the same auth — useful for token accounting.
- The paid `standard-tier` path (user's own GCP project) would unlock beyond
  free-tier quotas if the user ever subscribes — the same bridge works; only
  the project resolution changes.
- Cockpit's encrypted account store (`AES-256-GCM` + `account-token.key`) is
  decryptable in principle — unnecessary now that the export provides tokens,
  but documented in `docs/cockpit-tools-analysis.md`.

## Guardrails
- Never commit `accounts.json` (refresh tokens). Already gitignored.
- Keep the bridge loopback-only (`127.0.0.1`); it proxies Google credentials.
- Don't change the port without updating bridge + watchdog + Hermes config
  together.
