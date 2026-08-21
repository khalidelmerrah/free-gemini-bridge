"""Extract the Gemini/Antigravity refresh token from state.vscdb (port of
cockpit-tools' protobuf decoding) and save it for the quota chip."""
import sqlite3, base64, json

DB = "C:/Users/admindev/AppData/Roaming/Antigravity/User/globalStorage/state.vscdb"
OUT = "C:/Users/admindev/.sharksms-outreach/gemini_tokens.json"


def read_varint(data, offset):
    result, shift, pos = 0, 0, offset
    while True:
        b = data[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if b & 0x80 == 0:
            break
        shift += 7
    return result, pos


def skip_field(data, offset, wire_type):
    if wire_type == 0:
        return read_varint(data, offset)[1]
    if wire_type == 1:
        return offset + 8
    if wire_type == 2:
        length, off = read_varint(data, offset)
        return off + length
    if wire_type == 5:
        return offset + 4
    raise ValueError(wire_type)


def extract_bytes_field(data, target_field):
    offset = 0
    while offset < len(data):
        tag, new_off = read_varint(data, offset)
        wire_type, field_num = tag & 7, tag >> 3
        if field_num == target_field and wire_type == 2:
            length, content_offset = read_varint(data, new_off)
            return data[content_offset:content_offset + length]
        offset = skip_field(data, new_off, wire_type)
    return None


def extract_string_field(data, target_field):
    v = extract_bytes_field(data, target_field)
    return v.decode("utf-8", "replace") if v else None


def extract_oauth_info(entry):
    """Extract {access, refresh, expiry, id_token} from an oauthTokenInfo entry."""
    if extract_string_field(entry, 1) != "oauthTokenInfoSentinelKey":
        return None
    row = extract_bytes_field(entry, 2)
    if not row:
        return None
    b64 = extract_string_field(row, 1)
    if not b64:
        return None
    oauth = base64.b64decode(b64)
    return {
        "access_token": extract_string_field(oauth, 1),
        "refresh_token": extract_string_field(oauth, 3),
        "token_type": extract_string_field(oauth, 2) or "Bearer",
        "id_token": extract_string_field(oauth, 5),
    }


conn = sqlite3.connect(DB)
row = conn.execute(
    "SELECT value FROM ItemTable WHERE key='antigravityUnifiedStateSync.oauthToken'"
).fetchone()
conn.close()

if not row:
    print("KEY NOT FOUND — Antigravity login state absent")
    raise SystemExit(1)

data = base64.b64decode(row[0])
print("topic data bytes:", len(data))
info = None
offset = 0
while offset < len(data):
    tag, new_off = read_varint(data, offset)
    wire_type, field_num = tag & 7, tag >> 3
    if field_num == 1 and wire_type == 2:
        length, content_offset = read_varint(data, new_off)
        entry = data[content_offset:content_offset + length]
        r = extract_oauth_info(entry)
        if r:
            info = r
            break
    offset = skip_field(data, new_off, wire_type)

if info and info["refresh_token"]:
    print("REFRESH TOKEN EXTRACTED:", info["refresh_token"][:14] + "..." + info["refresh_token"][-6:])
    tokens = {
        "access_token": info.get("access_token"),
        "refresh_token": info["refresh_token"],
        "token_type": info.get("token_type", "Bearer"),
        "expires_in": 3600,
        "expiry_timestamp": 0,
        "email": None,
        "id_token": info.get("id_token"),
    }
    with open(OUT, "w") as f:
        json.dump(tokens, f, indent=2)
    print("saved to gemini_tokens.json (full tokens never printed)")
else:
    print("no oauthTokenInfo entry found")
