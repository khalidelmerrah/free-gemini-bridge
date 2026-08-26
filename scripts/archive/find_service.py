import re, glob

pats = ["cloudcode", "cloud-code", "cloudaicompanion", "companion", "pa.googleapis", "genai", "generativelanguage"]
found = {}
for f in glob.glob("C:/Users/admindev/AppData/Local/hermes/node/node_modules/@google/gemini-cli/bundle/*.js"):
    src = open(f, encoding="utf-8", errors="ignore").read()
    for p in pats:
        for m in re.finditer(r".{0,80}" + re.escape(p) + r".{0,80}", src):
            s = m.group(0).strip()
            if "http" in s or "://" in s or "googleapis" in s:
                key = s[:160]
                found.setdefault(p, set()).add(key)
for p in pats:
    vals = found.get(p, set())
    print(f"== {p}: {len(vals)}")
    for v in sorted(vals)[:6]:
        print("   ", v.replace("\n", " ")[:150])
