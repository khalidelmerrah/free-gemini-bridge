# scripts/

- `extract_gemini_token.py` — pull the active Antigravity OAuth token from
  `state.vscdb` (used by the quota chip backend). Still current.
- `archive/` — research tools from the discovery phase, kept for reference:
  - `find_*.py` — bundle-digging helpers (how the GCA RPCs were discovered)
  - `gemini_phone_login.py` — phone-completable OAuth loopback login.
    **OBSOLETE since v2** — no login is needed at all; the bridge uses
    Cockpit's Antigravity refresh tokens directly.
