import re, glob

files = glob.glob("C:/Users/admindev/AppData/Local/hermes/node/node_modules/@google/gemini-cli/bundle/*.js")
scopes = set()
for f in files:
    try:
        src = open(f, encoding="utf-8", errors="ignore").read()
    except Exception:
        continue
    for m in re.findall(r"https://www\.googleapis\.com/auth/[a-zA-Z0-9._\-]+", src):
        scopes.add(m)
    for m in re.findall(r"scope[\"']?\s*[:=]\s*[\"']([^\"']{20,300})[\"']", src):
        scopes.add("STRING: " + m[:200])
for s in sorted(scopes):
    print(s)
