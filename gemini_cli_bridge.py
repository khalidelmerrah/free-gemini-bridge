"""Localhost OpenAI-compatible bridge backed by the Gemini Code Assist (GCA) API
using the SAME Google OAuth credentials Cockpit Tools manages.

Discovery (2026-08-26): Antigravity OAuth refresh tokens (which Cockpit stores
and switches) ARE accepted for full GCA inference when the request identifies as
the Antigravity IDE client (User-Agent + client metadata). No Gemini CLI login
or API key needed. Account switching = swap the refresh token (or auto-follow
Cockpit's active account).

Endpoints (OpenAI-compatible):
  GET  /health
  GET  /v1/models
  POST /v1/chat/completions      (stream=true supported via SSE)
  GET  /v1/account               (current account)
  POST /v1/account/switch        ({email: ...})  — explicit override
  POST /v1/account/follow-cockpit ({follow: true|false})
"""
from __future__ import annotations

import gzip
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

HOME = Path(os.path.expanduser("~"))
REPO = HOME / "gemini-hermes"
REGISTRY = REPO / "accounts.json"
STATE = REPO / "bridge_state.json"
COCKPIT_ACCOUNTS = HOME / ".antigravity_cockpit" / "accounts.json"

GCA = "https://daily-cloudcode-pa.googleapis.com"
TOKEN_URL = "https://oauth2.googleapis.com/token"
UA = "antigravity/1.20.5 windows/amd64 google-api-nodejs-client/10.3.0"
X_GOOG = "gl-node/22.21.1"

_TOKEN_CACHE: dict[str, tuple[str, float]] = {}  # email -> (access_token, expires_at)

CHAT_MODELS = [
    "gemini-3.6-flash-high", "gemini-3.6-flash-medium", "gemini-3.6-flash-low",
    "gemini-3.5-flash-low", "gemini-3.1-pro-high", "gemini-3.1-pro-low",
    "gemini-3-flash", "gemini-2.5-pro",
]
EXTRA_MODELS = [
    "claude-sonnet-4-6", "claude-opus-4-6-thinking", "gpt-oss-120b-medium",
    "gemini-pro-agent", "gemini-3.1-flash-lite", "gemini-3.5-flash-extra-low",
]


def _gzip_or_text(raw: bytes, headers) -> bytes:
    if headers.get("Content-Encoding") == "gzip":
        return gzip.decompress(raw)
    return raw


def _http(url: str, payload: dict | None, access_token: str, stream: bool = False, timeout: int = 90):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": UA,
        "x-goog-api-client": X_GOOG,
        "Accept-Encoding": "gzip",
    }
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read()
        return resp.status, _gzip_or_text(raw, resp.headers)
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, _gzip_or_text(raw, e.headers)


def _refresh_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    data = urllib.parse.urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"token refresh failed: {e.code} {e.read()[:200]}")


def _load_registry() -> dict:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return reg


def _accounts() -> dict[str, dict]:
    reg = _load_registry()
    return {a["email"]: a for a in reg["accounts"]}


def _cockpit_active_email() -> str | None:
    """Follow Cockpit Tools' currently-active Antigravity account."""
    try:
        d = json.loads(COCKPIT_ACCOUNTS.read_text(encoding="utf-8"))
        cur = d.get("current_account_id")
        for a in d.get("accounts", []):
            if a.get("id") == cur:
                return a.get("email")
    except Exception:
        pass
    return None


def _state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"follow_cockpit": True, "active_email": None}


def _save_state(st: dict):
    STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")


def _active_email() -> str:
    st = _state()
    if st.get("follow_cockpit"):
        email = _cockpit_active_email()
        if email:
            return email
    if st.get("active_email"):
        return st["active_email"]
    # fallback: first account in registry
    return list(_accounts())[0]


def _access_token(email: str) -> str:
    cached = _TOKEN_CACHE.get(email)
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    reg = _load_registry()
    oc = reg["oauth_client"]
    acct = _accounts().get(email)
    if not acct:
        raise HTTPException(status_code=404, detail=f"account {email} not in registry")
    tok = _refresh_token(oc["id"], oc["secret"], acct["refresh_token"])
    at = tok.get("access_token")
    if not at:
        raise HTTPException(status_code=502, detail=f"no access token for {email}")
    expires = time.time() + int(tok.get("expires_in", 3600)) - 120
    _TOKEN_CACHE[email] = (at, expires)
    # persist rotated refresh token if Google rotated it
    if tok.get("refresh_token") and tok["refresh_token"] != acct["refresh_token"]:
        reg = _load_registry()
        for a in reg["accounts"]:
            if a["email"] == email:
                a["refresh_token"] = tok["refresh_token"]
        REGISTRY.write_text(json.dumps(reg, indent=1), encoding="utf-8")
    return at


def _gca_call(rpc: str, payload: dict, email: str) -> tuple[int, dict | bytes]:
    at = _access_token(email)
    status, raw = _http(f"{GCA}/v1internal:{rpc}", payload, at)
    try:
        return status, json.loads(raw) if isinstance(raw, (bytes, bytearray)) else json.loads(raw)
    except Exception:
        return status, raw


def _models_for(email: str) -> list[dict]:
    status, res = _gca_call("fetchAvailableModels", {}, email)
    if status != 200 or not isinstance(res, dict):
        return [{"id": m, "object": "model", "owned_by": "google-gca"} for m in CHAT_MODELS]
    out = []
    for name, info in (res.get("models") or {}).items():
        if not info.get("quotaInfo"):
            continue
        out.append({
            "id": name,
            "object": "model",
            "owned_by": "google-gca",
            "display_name": info.get("displayName"),
            "max_tokens": info.get("maxTokens"),
            "supports_thinking": bool(info.get("supportsThinking")),
        })
    if not out:
        out = [{"id": m, "object": "model", "owned_by": "google-gca"} for m in CHAT_MODELS]
    return out


def _openai_to_gca(messages: list[dict]) -> dict:
    """Convert OpenAI chat messages to the GCA generateContent request body."""
    contents = []
    system_parts = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if role == "system":
            system_parts.append({"text": content if isinstance(content, str) else json.dumps(content)})
            continue
        parts = []
        if isinstance(content, str):
            parts.append({"text": content})
        elif isinstance(content, list):
            for c in content:
                if c.get("type") == "text":
                    parts.append({"text": c.get("text", "")})
                elif c.get("type") == "image_url":
                    parts.append({"inlineData": {"mimeType": "image/png",
                                                 "data": c["image_url"].get("url", "").split(",", 1)[-1]}})
        if not parts:
            continue
        gca_role = "model" if role == "assistant" else "user"
        contents.append({"role": gca_role, "parts": parts})
    if not contents:
        contents = [{"role": "user", "parts": [{"text": ""}]}]
    request_body = {"contents": contents}
    if system_parts:
        request_body["systemInstruction"] = {"parts": system_parts}
    return request_body


def _extract_text(parts: list[dict] | None) -> str:
    out = []
    for p in parts or []:
        if isinstance(p, dict) and p.get("text"):
            out.append(p["text"])
    return "".join(out)


def _translate_response(res: dict) -> dict:
    resp = res.get("response") or {}
    usage = resp.get("usageMetadata") or {}
    cands = resp.get("candidates") or []
    choices = []
    for c in cands:
        content = c.get("content") or {}
        text = _extract_text(content.get("parts"))
        role = content.get("role") or "assistant"
        choices.append({
            "index": len(choices),
            "message": {"role": role, "content": text},
            "finish_reason": c.get("finishReason") or "stop",
        })
    if not choices:
        choices = [{"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}]
    return {
        "id": f"chatcmpl-{res.get('traceId', uuid.uuid4().hex)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "gca",
        "choices": choices,
        "usage": {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "total_tokens": usage.get("totalTokenCount", 0),
        },
    }


class SwitchIn(BaseModel):
    email: str


class FollowIn(BaseModel):
    follow: bool = True


class ChatIn(BaseModel):
    model: str
    messages: list[dict]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="Gemini GCA bridge (Cockpit auth)", version="2.0.0")

    @app.get("/health")
    def health():
        st = _state()
        return {
            "status": "ok",
            "active_account": _active_email(),
            "follow_cockpit": st.get("follow_cockpit", True),
        }

    @app.get("/v1/models")
    def models():
        email = _active_email()
        return {"object": "list", "data": _models_for(email)}

    @app.get("/v1/account")
    def account():
        return {
            "active": _active_email(),
            "follow_cockpit": _state().get("follow_cockpit", True),
            "available": list(_accounts()),
        }

    @app.post("/v1/account/switch")
    def switch(body: SwitchIn = Body(...)):
        if body.email not in _accounts():
            raise HTTPException(status_code=404, detail="unknown account")
        st = _state()
        st["follow_cockpit"] = False
        st["active_email"] = body.email
        _save_state(st)
        _TOKEN_CACHE.pop(body.email, None)
        return {"active": body.email, "follow_cockpit": False}

    @app.post("/v1/account/follow-cockpit")
    def follow_cockpit(body: FollowIn = Body(...)):
        st = _state()
        st["follow_cockpit"] = body.follow
        if body.follow:
            st["active_email"] = None
        _save_state(st)
        return {"follow_cockpit": body.follow, "active": _active_email()}

    class ChatIn(BaseModel):
        model: str
        messages: list[dict]
        stream: bool = False
        temperature: float | None = None
        max_tokens: int | None = None

    @app.post("/v1/chat/completions")
    def chat(body: ChatIn = Body(...)):
        email = _active_email()
        payload = {
            "model": body.model,
            "user_prompt_id": uuid.uuid4().hex,
            "request": _openai_to_gca(body.messages),
        }
        if body.temperature is not None:
            payload["request"]["generationConfig"] = {"temperature": body.temperature}
        if body.max_tokens is not None:
            payload["request"].setdefault("generationConfig", {})["maxOutputTokens"] = body.max_tokens

        if body.stream:
            return _stream_chat(payload, email)

        status, res = _gca_call("generateContent", payload, email)
        if status != 200:
            detail = res if isinstance(res, str) else json.dumps(res, default=str)[:500]
            raise HTTPException(status_code=502, detail=f"GCA {status}: {detail}")
        if not isinstance(res, dict):
            raise HTTPException(status_code=502, detail=f"GCA {status}: unexpected response")
        return _translate_response(res)

    def _stream_chat(payload: dict, email: str):
        at = _access_token(email)
        body = json.dumps(payload).encode()
        req = urllib.request.Request(f"{GCA}/v1internal:generateContent?alt=sse", data=body, headers={
            "Authorization": f"Bearer {at}", "Content-Type": "application/json",
            "User-Agent": UA, "x-goog-api-client": X_GOOG, "Accept": "text/event-stream",
        })

        def gen():
            try:
                resp = urllib.request.urlopen(req, timeout=180)
            except urllib.error.HTTPError as e:
                yield f"data: {json.dumps({'error': {'message': str(e.code) + ': ' + e.read().decode('utf-8','replace')[:300]}})}\n\n"
                return
            buf = b""
            emitted = False
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line or not line.startswith(b"data:"):
                        continue
                    try:
                        ev = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    resp2 = ev.get("response") or ev
                    cands = resp2.get("candidates") or []
                    text = ""
                    for c in cands:
                        text += _extract_text((c.get("content") or {}).get("parts"))
                    if not text:
                        continue
                    obj = {
                        "id": f"chatcmpl-{ev.get('traceId', uuid.uuid4().hex)}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": payload["model"],
                        "choices": [{"index": 0,
                                     "delta": ({"role": "assistant", "content": text}
                                               if not emitted else {"content": text}),
                                     "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(obj)}\n\n"
                    emitted = True
            # OpenAI convention: final chunk carries finish_reason before [DONE]
            if emitted:
                fin = {
                    "id": f"chatcmpl-{uuid.uuid4().hex}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": payload["model"],
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(fin)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


app = create_app()
