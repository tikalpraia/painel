"""Baixa todos os ingressos do evento Portal de Algodões 2027 na API da Shotgun.
Token: variável SHOTGUN_TOKEN; sem ela, envia um valor fictício e o proxy do ambiente injeta o token salvo."""
import json, os, sys, time, urllib.request
OUT = sys.argv[1] if len(sys.argv) > 1 else "data/shotgun_tickets.json"
tok = os.environ.get("SHOTGUN_TOKEN", "placeholder")
url = "https://api.shotgun.live/tickets?organizer_id=222720&event_id=549857&include_cohosted_events=1"
rows, n = [], 0
while url:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    rows += d.get("data", [])
    url = (d.get("pagination") or {}).get("next")
    if url and "token=" in url:  # nunca propagar token na URL
        url = "&".join(p for p in url.split("&") if not p.startswith("token="))
    n += 1
    if n % 90 == 0: time.sleep(60)
# deduplica pelo ticket_id mantendo a versão mais recente
by = {}
for t in rows: by[t["ticket_id"]] = t
json.dump(list(by.values()), open(OUT, "w"), ensure_ascii=False)
print(f"{len(by)} tickets, {n} pages -> {OUT}")
