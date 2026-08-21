"""Gemini Quota backend — reads real Gemini quota via Antigravity's Cloud Code API.

Auth: Google OAuth tokens extracted from the local Antigravity IDE login state
(state.vscdb → antigravityUnifiedStateSync.oauthToken, protobuf-decoded —
the same technique as the open-source cockpit-tools project). No API key,
no separate login: whatever account is signed into Antigravity is the one
whose quota shows in the status bar.

Quota endpoint (same one Antigravity uses):
    POST https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels
"""
import json, os, time, gzip, io, base64, sqlite3
import urllib.request, urllib.parse
from fastapi import APIRouter

router = APIRouter()

TOKEN_URL = "https://oauth2.googleapis.com/token"
QUOTA_URL_DAILY = "https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels"
QUOTA_URL_PROD = "https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels"
CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
CLIENT_SECRET = "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"  # public (open-source cockpit-tools)
USER_AGENT = "antigravity/1.20.5 windows/amd64"

TOKENS_PATH = os.path.expanduser("~/.sharksms-outreach/gemini_tokens.json")
STATE_DB = os.path.expanduser("~/AppData/Roaming/Antigravity/User/globalStorage/state.vscdb")


def _load_tokens():
    try:
        with open(TOKENS_PATH) as f:
            return json.load(f)
    except Exception:
        return None


def _save_tokens(tokens):
    os.makedirs(os.path.dirname(TOKENS_PATH), exist_ok=True)
    with open(TOKENS_PATH, "w") as f:
        json.dump(tokens, f, indent=2)


def _extract_tokens_from_antigravity():
    """Re-extract tokens from Antigravity's local login state (state.vscdb)."""
    try:
        conn = sqlite3.connect(STATE_DB)
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key='antigravityUnifiedStateSync.oauthToken'"
        ).fetchone()
        conn.close()
        if not row:
            return None
        data = base64.b64decode(row[0])

        def read_varint(d, offset):
            result, shift, pos = 0, 0, offset
            while True:
                b = d[pos]
                result |= (b & 0x7F) << shift
                pos += 1
                if b & 0x80 == 0:
                    break
                shift += 7
            return result, pos

        def skip_field(d, offset, wt):
            if wt == 0:
                return read_varint(d, offset)[1]
            if wt == 1:
                return offset + 8
            if wt == 2:
                l, o = read_varint(d, offset)
                return o + l
            if wt == 5:
                return offset + 4
            raise ValueError(wt)

        def field_bytes(d, target):
            off = 0
            while off < len(d):
                tag, no = read_varint(d, off)
                wt, fn = tag & 7, tag >> 3
                if fn == target and wt == 2:
                    l, co = read_varint(d, no)
                    return d[co:co + l]
                off = skip_field(d, no, wt)
            return None

        def str_field(d, target):
            v = field_bytes(d, target)
            return v.decode("utf-8", "replace") if v else None

        offset = 0
        while offset < len(data):
            tag, no = read_varint(data, offset)
            wt, fn = tag & 7, tag >> 3
            if fn == 1 and wt == 2:
                l, co = read_varint(data, no)
                entry = data[co:co + l]
                if str_field(entry, 1) == "oauthTokenInfoSentinelKey":
                    row_b = field_bytes(entry, 2)
                    b64 = str_field(row_b, 1)
                    if b64:
                        oauth = base64.b64decode(b64)
                        tokens = {
                            "access_token": str_field(oauth, 1),
                            "refresh_token": str_field(oauth, 3),
                            "token_type": str_field(oauth, 2) or "Bearer",
                            "id_token": str_field(oauth, 5),
                            "expires_in": 3600,
                            "expiry_timestamp": 0,
                            "email": None,
                        }
                        if tokens["refresh_token"]:
                            _save_tokens(tokens)
                            return tokens
            offset = skip_field(data, no, wt)
    except Exception:
        return None
    return None


def _refresh_access_token(tokens):
    """Exchange the refresh token for a fresh access token."""
    body = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": tokens["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        return None, f"token refresh failed: {exc}"
    tokens["access_token"] = data["access_token"]
    tokens["expires_in"] = data.get("expires_in", 3600)
    tokens["expiry_timestamp"] = int(time.time()) + tokens["expires_in"]
    _save_tokens(tokens)
    return tokens["access_token"], None


def _fetch_quota(access_token):
    """Call fetchAvailableModels with the Antigravity user-agent."""
    payload = json.dumps({}).encode()
    req = urllib.request.Request(QUOTA_URL_DAILY, data=payload, method="POST", headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8")), None
    except Exception as exc:
        return None, str(exc)


def _quota_response(tokens):
    """Build the chip payload from stored tokens + live quota."""
    access_token = tokens.get("access_token")
    if not access_token or int(time.time()) > tokens.get("expiry_timestamp", 0) - 60:
        access_token, err = _refresh_access_token(tokens)
        if err:
            # refresh failed — the login may have changed; re-extract from Antigravity
            fresh = _extract_tokens_from_antigravity()
            if fresh:
                access_token, err = _refresh_access_token(fresh)
            if err:
                return {"logged_in": False, "windows": [], "details": [f"auth unavailable: {err}"]}

    data, err = _fetch_quota(access_token)
    if err:
        # fall back to the prod base URL (GCP ToS accounts)
        data2, err2 = _fetch_quota_prod(access_token)
        if err2:
            return {"logged_in": True, "windows": [], "details": [f"quota fetch failed: {err2}"]}
        data = data2

    models = data.get("models", {}) if isinstance(data, dict) else {}
    windows = []
    details = []
    for name, info in models.items():
        q = info.get("quotaInfo") or {}
        frac = q.get("remainingFraction")
        reset = q.get("resetTime")
        pct = round(frac * 100) if isinstance(frac, (int, float)) else None
        label = info.get("displayName") or name
        windows.append({
            "label": label,
            "remaining_percent": pct,
            "reset_at": reset,
        })
        line = f"{label}: {'—' if pct is None else str(pct) + '% remaining'}"
        if reset:
            line += f" · resets {reset[:16].replace('T', ' ')}"
        details.append(line)
    windows.sort(key=lambda w: (w["remaining_percent"] is None, -(w["remaining_percent"] or 0)))
    return {
        "logged_in": True,
        "plan": tokens.get("email", "Gemini account"),
        "windows": windows[:8],
        "details": details[:8],
    }


def _fetch_quota_prod(access_token):
    payload = json.dumps({}).encode()
    req = urllib.request.Request(QUOTA_URL_PROD, data=payload, method="POST", headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode()), None
    except Exception as exc:
        return None, str(exc)


def _email_from_id_token(tokens):
    """Extract the account email from the OAuth id_token (JWT payload)."""
    try:
        idt = tokens.get("id_token") or ""
        if not idt:
            return None
        payload = idt.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        return data.get("email")
    except Exception:
        return None


@router.get("/quota")
async def quota():
    tokens = _load_tokens()
    if not tokens:
        tokens = _extract_tokens_from_antigravity()
    if not tokens:
        return {
            "logged_in": False,
            "plan": None,
            "windows": [],
            "details": ["Not logged into Antigravity on this machine"],
        }
    result = _quota_response(tokens)
    email = _email_from_id_token(tokens)
    if email and result.get("plan") is None:
        result["plan"] = email
    return result
