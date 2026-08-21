# Pickup guide — RESUME HERE

Everything needed to continue this work after a break. Follow in order.

## 0. Inventory check (2 min)

Run these to confirm the environment is intact:

```bash
# Gemini CLI installed?
npm view @google/gemini-cli version          # expect 0.56.0+
gemini --version

# Tokens present (quota chip data source)?
ls ~/.sharksms-outreach/gemini_tokens.json

# Plugin in place + enabled?
ls "C:/Users/admindev/AppData/Local/hermes/plugins/gemini-quota"
hermes config get plugins.enabled            # expect ["gemini-quota"]

# Antigravity still logged in?
ls -la "C:/Users/admindev/AppData/Roaming/Antigravity/User/globalStorage/state.vscdb"
```

## 1. If the quota chip stopped working

```bash
cd ~/.sharksms-outreach
python extract_gemini_token.py      # re-extract tokens from Antigravity (it refreshes its DB as you use it)
python - <<'EOF'
# quick sanity: does the quota API still answer?
import json, urllib.request
t = json.load(open("gemini_tokens.json"))
req = urllib.request.Request("https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels",
    data=b"{}", headers={"Authorization": "Bearer " + t["access_token"],
    "User-Agent": "antigravity/1.20.5 windows/amd64", "Content-Type": "application/json"})
print(urllib.request.urlopen(req).status)
EOF
```

Then reload the Hermes desktop app (Settings → Plugins → toggle off/on).

## 2. If tokens were revoked / login needed again

```bash
cd ~/.sharksms-outreach
python gemini_phone_login.py        # prints a fresh auth URL + starts the localhost:8765 listener
```
- Open the printed URL on the **phone** → sign in with `steave.j.jenkins@gmail.com`
  → **Advanced → proceed** past the "unverified app" warning → **Allow**
- The phone shows "This site can't be reached" — **expected**. Copy the full URL
  from the address bar (`?code=...`) → paste into `pasted_code.txt` (or chat with
  the agent, which writes it there) → script exchanges and saves tokens.
- Scope note: the proven-good scope set is
  `openid email profile https://www.googleapis.com/auth/cloud-platform`
  (quota works). Do **NOT** add `generative-language` — it's
  `restricted_client` for this client and hard-fails the login.

## 3. The open thread: find the chat-generation endpoint

Goal: make Gemini usable as a chat model. The likely path (from
`docs/status.md` + `docs/oauth-findings.md`):

1. In the gemini-cli bundle, find where `CODE_ASSIST_ENDPOINT`
   (`https://cloudcode-pa.googleapis.com`) is used for generation:
   ```bash
   B="C:/Users/admindev/AppData/Local/hermes/node/node_modules/@google/gemini-cli/bundle"
   grep -rn "cloudcode-pa\|CODE_ASSIST_ENDPOINT\|v1internal" "$B" --include="*.js" -o | sort -u
   ```
2. Look for RPC names like `generateContent`, `fetchCodeAssist`,
   `streamGenerateContent` near the endpoint usage (they're split across chunks —
   the scripts in `scripts/` were built for this).
3. Alternatively: watch network traffic while running
   `GOOGLE_GENAI_USE_GCA=true gemini -p "hi"` (after a CLI login) to capture the
   generation URL + payload.
4. Once found, write a small local OpenAI-compatible proxy
   (`/v1/chat/completions` → the internal RPC) and register it in Hermes as a
   custom `base_url` provider → Gemini appears in the model picker.

**Why this works without the generative-language scope:** the quota API
(`daily-cloudcode-pa.googleapis.com`) already accepts our cloud-platform token,
and the CLI uses that same backend family for generation. The public
`generativelanguage` API is a dead end for OAuth (scope-restricted).

## 4. Gemini CLI for delegated coding (works today, needs one login)

The `gemini-cli` Hermes skill lets the agent delegate coding tasks to Gemini
(same pattern as Codex). It needs a one-time CLI login — on the PC, in a REAL
terminal (the Hermes PTY can't drive it):
```
C:\Users\admindev\.sharksms-outreach\login_gemini.bat
```
It prints a URL/code flow that can be finished from the phone. After login, the
skill's one-shot/background/worktree workflows work as documented in the skill.

## 5. Guardrails

- **Never commit `gemini_tokens.json` / `creds.env` / anything containing
  `1//` (refresh tokens) or `ya29.` (access tokens).** `.gitignore` already covers
  the standard names.
- If tokens leak: https://myaccount.google.com/security → revoke the app's access
  (tokens for "Antigravity" / "Gemini CLI").
- The OAuth client secrets in `scripts/` are public (open-source), but treat them
  as semi-sensitive anyway — they're tied to Google's own client quota.
- The phone login consumes ~1 authorization code per login; a code is single-use
  and expires in minutes — no cleanup needed.
