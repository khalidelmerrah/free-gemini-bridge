"""Gemini phone-completable OAuth login (GCA client, loopback + paste-back).

1. Prints an auth URL — open it on your PHONE, log in with your Google account
2. Google redirects to http://localhost:8765/?code=... (phone shows an error —
   that's normal); copy the FULL URL from the address bar and paste it here,
   or run the browser on this PC and the local listener captures it
3. Exchanges the code (PKCE) for refresh+access tokens -> gemini_tokens.json
"""
import base64, hashlib, json, os, socket, threading, urllib.request, urllib.parse, urllib.error, sys, time

CID = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j"
SECRET = "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"
REDIRECT = "http://localhost:8765"
SCOPE = "openid email profile https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/generative-language"
TOKENS_FILE = os.path.expanduser("~/.sharksms-outreach/gemini_tokens.json")

verifier = base64.urlsafe_b64encode(os.urandom(48)).rstrip(b"=").decode()
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
params = {
    "client_id": CID, "redirect_uri": REDIRECT, "response_type": "code",
    "scope": SCOPE, "access_type": "offline", "prompt": "consent",
    "code_challenge": challenge, "code_challenge_method": "S256",
    "state": "gemini-phone",
}
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)

captured = {}


def _server():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 8765))
    srv.listen(1)
    srv.settimeout(1800)
    try:
        conn, _ = srv.accept()
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
        head = data.decode(errors="replace")
        path = head.split(" ", 2)[1] if len(head.split(" ", 2)) > 1 else "/"
        captured["url"] = "http://localhost:8765" + path
        body = b"<html><body><h2>Login received. You can close this tab.</h2></body></html>"
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: " +
                     str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
        conn.close()
    except Exception as e:
        captured["err"] = str(e)
    finally:
        srv.close()


threading.Thread(target=_server, daemon=True).start()
print("OPEN THIS LINK ON YOUR PHONE (logged into steave.j.jenkins@gmail.com):")
print()
print(AUTH_URL)
print()
print("After approving, your phone browser will try to open 'localhost' and show")
print("'This site can't be reached' - that's EXPECTED. Copy the whole URL from the")
print("address bar (it contains ?code=...) and paste it below, or type 'wait' if")
print("you completed it in a browser on this PC.")
print("Waiting up to 30 minutes...")
sys.stdout.flush()

code = None
for _ in range(1800 // 5):
    time.sleep(5)
    if captured.get("url"):
        u = captured["url"]
        q = urllib.parse.urlparse(u).query
        if "code=" in q:
            code = urllib.parse.parse_qs(q)["code"][0]
            print("Captured code from local listener!")
            break
    if os.path.exists("pasted_code.txt"):
        u = open("pasted_code.txt").read().strip()
        q = urllib.parse.urlparse(u).query
        if "code=" in q:
            code = urllib.parse.parse_qs(q)["code"][0]
            print("Captured code from pasted URL!")
            break

if not code:
    print("TIMEOUT: no code received.")
    sys.exit(1)

body = urllib.parse.urlencode({
    "client_id": CID, "client_secret": SECRET, "code": code,
    "redirect_uri": REDIRECT, "grant_type": "authorization_code",
    "code_verifier": verifier,
}).encode()
req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body,
                             headers={"Content-Type": "application/x-www-form-urlencoded"})
tok = json.loads(urllib.request.urlopen(req, timeout=30).read())
out = {
    "access_token": tok["access_token"],
    "refresh_token": tok.get("refresh_token", ""),
    "expires_in": tok.get("expires_in", 3599),
    "expiry_ts": int(time.time()) + tok.get("expires_in", 3599),
    "id_token": tok.get("id_token", ""),
}
with open(TOKENS_FILE, "w") as f:
    json.dump(out, f)
os.chmod(TOKENS_FILE, 0o600)
print("SAVED to", TOKENS_FILE)
print("email in id_token:", json.loads(base64.urlsafe_b64decode(
    out["id_token"].split(".")[1] + "==")).get("email", "?") if out["id_token"] else "?")
