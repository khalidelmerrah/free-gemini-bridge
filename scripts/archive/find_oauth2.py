import re, glob

for f in glob.glob("C:/Users/admindev/AppData/Local/hermes/node/node_modules/@google/gemini-cli/bundle/*.js"):
    src = open(f, encoding="utf-8", errors="ignore").read()
    for name in ["OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET", "OAUTH_SCOPE"]:
        for m in re.finditer(r"const\s+" + name + r"\s*=\s*([^;]{0,300});", src):
            print(f"{f.split('/')[-1]}: {name} = {m.group(1)[:280]}")
        for m in re.finditer(r"var\s+" + name + r"\s*=\s*([^;]{0,300});", src):
            print(f"{f.split('/')[-1]}: {name} = {m.group(1)[:280]}")
