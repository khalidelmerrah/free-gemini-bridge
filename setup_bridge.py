"""Interactive setup wizard for the Gemini bridge (standalone / installable).

Pick an auth source — the bridge doesn't care where the Google login came from,
it just needs refresh tokens. Sources:

  1. Antigravity IDE (auto-detect)   — reads the IDE's local login state (state.vscdb)
  2. Cockpit Tools (export file)     — import accounts from a data-transfer JSON
  3. Gemini CLI / Antigravity CLI    — detect an existing login (tokens are
                                       CLI-internal; use 4/5 for the same account)
  4. Sign in with Google (phone)     — fresh OAuth for ANY Google account,
                                       no prior login needed (loopback flow)
  5. Paste a refresh token           — advanced / from another tool

After saving, the wizard verifies one generation and prints the exact Hermes
config commands.

Usage:
  python setup_bridge.py            interactive
  python setup_bridge.py --detect   print detected sources/accounts, no prompts
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOME = Path.home()
REPO = HOME / "gemini-hermes"
REGISTRY = REPO / "accounts.json"

from gemini_cli_bridge import (  # noqa: E402
    _discover_external_accounts,
    _load_registry,
    _refresh_token,
)

OAUTH_CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
SCOPES = ("https://www.googleapis.com/auth/cloud-platform "
          "https://www.googleapis.com/auth/userinfo.email "
          "https://www.googleapis.com/auth/userinfo.profile")


def banner(text: str):
    print("\n" + "=" * 62)
    print("  " + text)
    print("=" * 62)


def save_accounts(accounts: list[dict]):
    reg = _load_registry()
    existing = {a["email"]: a for a in reg["accounts"]}
    added = 0
    for acc in accounts:
        if acc["email"] not in existing:
            existing[acc["email"]] = acc
            added += 1
    reg["accounts"] = list(existing.values())
    REGISTRY.write_text(json.dumps(reg, indent=1), encoding="utf-8")
    return added


def detect() -> dict:
    external = _discover_external_accounts()
    reg = _load_registry()
    by_source: dict[str, list[str]] = {}
    for acc in external.values():
        by_source.setdefault(acc.get("source", "?"), []).append(acc["email"])
    return {
        "registry": [a["email"] for a in reg["accounts"]],
        "external": by_source,
        "ide_logged_in": bool(by_source.get("antigravity-ide")),
        "cockpit_export_present": (REPO / "cockpit_export.json").exists(),
        "cli_login_state": _cli_login_state(),
    }


def _cli_login_state() -> str:
    ga = HOME / ".gemini" / "google_accounts.json"
    try:
        d = json.loads(ga.read_text(encoding="utf-8"))
        active = d.get("active")
        return f"active={active or 'none'}, old={len(d.get('old', []))}"
    except Exception:
        return "not found"


def src_ide() -> list[dict]:
    ext = _discover_external_accounts()
    out = [a for a in ext.values() if a["source"] == "antigravity-ide"]
    if not out:
        print("  ⚠  No Antigravity IDE login found (state.vscdb empty/missing).")
    return out


def src_cockpit_export() -> list[dict]:
    path = input("  Path to Cockpit data-transfer export JSON (drag the file here): ").strip().strip('"')
    p = Path(path)
    if not p.exists():
        print(f"  ✗ File not found: {p}")
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ✗ Not valid JSON: {e}")
        return []
    out = []
    platforms = d.get("accounts", {}).get("platforms", {})
    for plat in ("antigravity", "antigravity_ide"):
        for acc in platforms.get(plat, {}).get("exported_data", []) or []:
            if acc.get("refresh_token") and acc.get("email"):
                out.append({"email": acc["email"], "refresh_token": acc["refresh_token"],
                            "source": "cockpit-export"})
    if not out:
        print("  ✗ No antigravity accounts with refresh tokens in that export.")
    return out


def src_phone_login() -> list[dict]:
    """Loopback OAuth with the Antigravity client — works for ANY Google account."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = {
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": "http://localhost:8765",
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    print("  Open this URL (on any device, signed into the Google account you want):")
    print("\n    " + url + "\n")
    print("  After approving, the browser will try to open http://localhost:8765 and fail")
    print("  (nothing listens there). Copy the FULL address from the address bar")
    print("  (it looks like http://localhost:8765/?code=4/0A...&scope=...) and paste it:")
    landed = input("  Pasted URL: ").strip()
    code = urllib.parse.parse_qs(urllib.parse.urlparse(landed).query).get("code", [None])[0]
    if not code:
        print("  ✗ No code found in that URL.")
        return []
    data = urllib.parse.urlencode({
        "client_id": OAUTH_CLIENT_ID, "client_secret": OAUTH_CLIENT_SECRET,
        "code": code, "code_verifier": verifier,
        "redirect_uri": "http://localhost:8765", "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tok = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"  ✗ Token exchange failed: {e.code} {e.read()[:200]}")
        return []
    rt = tok.get("refresh_token")
    if not rt:
        print("  ✗ No refresh_token in response (consent didn't include offline access).")
        return []
    email = _email_from_tok(tok)
    print(f"  ✅ Got login for {email or 'unknown email'}")
    return [{"email": email or "google-account", "refresh_token": rt, "source": "phone-login"}]


def _email_from_tok(tok: dict) -> str | None:
    idt = tok.get("id_token")
    if idt:
        try:
            p = idt.split(".")[1]
            p += "=" * (-len(p) % 4)
            return json.loads(base64.b64decode(p)).get("email")
        except Exception:
            pass
    try:
        req = urllib.request.Request("https://www.googleapis.com/oauth2/v2/userinfo",
                                     headers={"Authorization": "Bearer " + tok["access_token"]})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r).get("email")
    except Exception:
        return None


def src_manual() -> list[dict]:
    email = input("  Account email: ").strip()
    rt = input("  Refresh token: ").strip()
    if not rt:
        return []
    return [{"email": email, "refresh_token": rt, "source": "manual"}]


def verify(email: str) -> bool:
    from gemini_cli_bridge import _access_token
    try:
        at = _access_token(email)
    except Exception as e:
        print(f"  ✗ Token refresh failed: {e}")
        return False
    body = json.dumps({
        "model": "gemini-3.6-flash-high", "user_prompt_id": "setup-verify",
        "request": {"contents": [{"role": "user", "parts": [{"text": "Reply with exactly: OK"}]}]},
    }).encode()
    req = urllib.request.Request(
        "https://daily-cloudcode-pa.googleapis.com/v1internal:generateContent",
        data=body,
        headers={"Authorization": f"Bearer {at}", "Content-Type": "application/json",
                 "User-Agent": "antigravity/1.20.5 windows/amd64 google-api-nodejs-client/10.3.0",
                 "x-goog-api-client": "gl-node/22.21.1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.load(r)
        cands = res.get("response", {}).get("candidates", [])
        text = "".join(p.get("text", "") for p in
                       (cands[0].get("content", {}).get("parts", []) if cands else []))
        print(f"  ✅ Generation works — Gemini replied: {text[:60]!r}")
        return True
    except urllib.error.HTTPError as e:
        print(f"  ✗ Generation failed: {e.code} {e.read()[:200]}")
        return False


def print_hermes_instructions():
    print("""
─────────────────────────────────────────────────────────────
  Add to Hermes (run these):

    hermes config set providers.gemini-cli.name "Gemini"
    hermes config set providers.gemini-cli.api "http://127.0.0.1:8787/v1"
    hermes config set providers.gemini-cli.transport chat_completions
    hermes config set providers.gemini-cli.default_model "gemini-3.6-flash-high"
    hermes config set providers.gemini-cli.models '["gemini-3.6-flash-high","gemini-3.6-flash-medium","gemini-3.6-flash-low","gemini-3.1-pro-high","gemini-3-flash","gemini-2.5-pro","claude-sonnet-4-6","claude-opus-4-6-thinking","gpt-oss-120b-medium"]'

  Then restart Hermes and pick "Gemini" in the model dropdown.
─────────────────────────────────────────────────────────────""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detect", action="store_true", help="print detected sources, no prompts")
    args = ap.parse_args()

    if args.detect:
        print(json.dumps(detect(), indent=1))
        return

    banner("Gemini bridge — standalone setup")
    print("  Registry: " + str(REGISTRY))
    print(json.dumps(detect(), indent=1))
    banner("Choose an auth source")
    print("  1. Antigravity IDE (auto-detect local login)")
    print("  2. Cockpit Tools (import a data-transfer export file)")
    print("  3. Gemini CLI / Antigravity CLI (check existing login)")
    print("  4. Sign in with Google on your phone (any account, no prior login)")
    print("  5. Paste a refresh token manually")
    choice = input("\n  Pick 1-5: ").strip()

    accounts = []
    if choice == "1":
        accounts = src_ide()
    elif choice == "2":
        accounts = src_cockpit_export()
    elif choice == "3":
        print(f"  Gemini CLI login state: {_cli_login_state()}")
        print("  (CLI tokens are stored CLI-internally; for the same account use option 4 or 5)")
        accounts = []
    elif choice == "4":
        accounts = src_phone_login()
    elif choice == "5":
        accounts = src_manual()
    else:
        print("  Invalid choice.")
        return

    if not accounts:
        print("\n  Nothing imported. Run again with a different source.")
        return

    added = save_accounts(accounts)
    print(f"\n  Saved {len(accounts)} account(s) ({added} new) to {REGISTRY.name}")

    print("  Available accounts:")
    reg = _load_registry()
    for i, a in enumerate(reg["accounts"], 1):
        print(f"    {i}. {a['email']}  [{a.get('source', 'registry')}]")

    pick = input("\n  Which account should be active? (number, Enter = first): ").strip()
    if pick.isdigit() and 1 <= int(pick) <= len(reg["accounts"]):
        active = reg["accounts"][int(pick) - 1]["email"]
    else:
        active = reg["accounts"][0]["email"]
    (REPO / "bridge_state.json").write_text(json.dumps(
        {"follow_cockpit": False, "active_email": active}, indent=1), encoding="utf-8")
    print(f"  Active: {active}")

    if input("\n  Run a live verification (one Gemini call)? [y/N]: ").strip().lower() == "y":
        verify(active)

    print_hermes_instructions()


if __name__ == "__main__":
    main()
