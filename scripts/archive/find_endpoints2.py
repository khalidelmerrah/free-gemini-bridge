import re, glob

urls = {}
for f in glob.glob("C:/Users/admindev/AppData/Local/hermes/node/node_modules/@google/gemini-cli/bundle/*.js"):
    src = open(f, encoding="utf-8", errors="ignore").read()
    # any https URL mentioning googleapis or pa.googleapis
    for m in re.finditer(r"https://[a-zA-Z0-9._\-]+(?:\.googleapis\.com|\.google\.com|\.googleusercontent\.com)[a-zA-Z0-9/_.\-:]*", src):
        u = m.group(0)
        urls[u] = urls.get(u, 0) + 1
for u in sorted(urls, key=lambda x: -urls[x])[:40]:
    print(urls[u], "|", u)
