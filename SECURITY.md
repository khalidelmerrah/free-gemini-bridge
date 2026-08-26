# Security

## What's in this repo
- **No real credentials.** `accounts.json` (the registry holding Google refresh
  tokens) is **gitignored and never committed** — it only exists on the machine
  where the bridge runs. Tests use fake tokens.
- **The `GOCSPX-…` strings are Google's *public* OAuth client secrets** for the
  Antigravity IDE / Gemini CLI clients — they ship in Google's own open-source
  artifacts (cockpit-tools, gemini-cli npm bundle) and are not secrets.
- No API keys, no GitHub tokens, no passwords. Git history was audited for
  token patterns — clean.

## Threat model
- The bridge binds **127.0.0.1 only** — it never listens on the network.
- Refresh tokens never leave the machine (exchanged only against
  `oauth2.googleapis.com` and `daily-cloudcode-pa.googleapis.com`).
- Anyone with local access to the machine *and* the registry file can use the
  accounts — protect `accounts.json` like a password (the same trust model as
  Cockpit Tools itself).

## Reporting
Open an issue for anything security-related.
