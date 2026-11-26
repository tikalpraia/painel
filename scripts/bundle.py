"""Junta os arquivos agregados num único JSON para o painel."""
import json, glob, os, sys
out = sys.argv[1]
b = {os.path.basename(f)[:-5]: json.load(open(f)) for f in sorted(glob.glob(f"{out}/*.json")) if not os.path.basename(f).startswith(("_", "bundle"))}
b["_info"] = json.load(open(f"{out}/_info.json"))
json.dump(b, open(f"{out}/bundle.json", "w"), ensure_ascii=False, separators=(",", ":"))
print(list(b), os.path.getsize(f"{out}/bundle.json"))
