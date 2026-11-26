"""Gera os arquivos agregados (sem dados pessoais) do painel a partir da exportação da Shotgun
e da planilha de leads. Uso: python3 build.py <tickets.json> <leads_dir> <out_dir> [corte AAAA-MM-DD]"""
import json, sys, re, collections as C, datetime as dt, os

TICKETS, LEADS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
STATIC = sys.argv[4] if len(sys.argv) > 4 else None     # static.json (planilha da Luciana + formulário de embaixadores)
SALT = sys.argv[5] if len(sys.argv) > 5 else ""
CUTOFF = sys.argv[6] if len(sys.argv) > 6 else None
S = json.load(open(STATIC)) if STATIC else {}
PROMO, PEDIDOS = S.get("promoters", {}), S.get("pedidos", {})
# Aba "painel" publicada da planilha de embaixadores (data, nome, sócio, link): cadastros e promoters novos
FORM_CSV = os.environ.get("FORM_CSV")
def socio_norm(s):
    t = (s or "").lower()
    if "sac" in t: return "Julia Bueno (SAC)"
    if "gigio" in t: return "Gigios"
    if "franc" in t: return "Francisco"
    if ("le" in t and ("ão" in t or "ao" in t)) or "🦁" in (s or ""): return "Leão"
    if "jo" in t or "xambah" in t: return "João Fernandes"
    if "rache" in t or t.strip() == "gabriel": return "Gabriel Rache"
    if "kur" in t: return "Vitor Kurc"
    if "craig" in t: return "Craig"
    return "Outros"
if FORM_CSV and os.path.exists(FORM_CSV):
    import csv
    linhas = list(csv.reader(open(FORM_CSV, encoding="utf-8")))[1:]
    cads = []
    for l in linhas:
        l = (l + ["", "", "", ""])[:4]
        if not (l[1] or "").strip(): continue
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", l[0] or "")
        socio = socio_norm(l[2])
        cads.append(dict(data=f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None, socio=socio))
        u = re.search(r"utm_source=(promoter-\d+)", l[3] or "")
        if u: PROMO.setdefault(u.group(1), [l[1].strip(), socio, "Embaixador"])
    if cads: S["cadastros"] = cads
os.makedirs(OUT, exist_ok=True)
T = json.load(open(TICKETS))
SALES_START = dt.date(2026, 5, 9)          # dia 1 de vendas
ADS = {"promoter-31417": "ADS (Roberto) – valor SAC", "promoter-31594": "ADS (Roberto) – valor embaixador"}
SAC_EMB_LINK = "promoter-31064"           # link SAC com valor embaixador (condições especiais)
# Valor real dos ingressos vendidos por pix fora da Shotgun (aba ADAPTAÇÕES INGRESSOS PIX da Luciana)
PIX_VALUE = {
    "JULIA EMBAIXADORA - Passaporte 7 Dias // 3 Festas Open Bar - Embaixador 2º lote": 3887.25,
    "Pacote Réveillon e Samba do Marcelo D2 - 2º Lote SAC": 2928.75,
    "Avulso Reveillon 1º Lote - Gigios": 2300.0,
    "Pacote Réveillon e Samba do Marcelo D2 - 2º Lote Francisco": 3200.0,
    "Pacote Réveillon e Samba do Marcelo D2 - 2º Lote Leão": 3025.0,
    "Passaporte 7 Dias // 3 Festas Open Bar - 1º lote_SAC Condição Especial": 3729.0,
}
PRINCIPAIS = ["Passaporte", "Avulso Réveillon", "Combo 31/12 + 02/01"]

def produto(t):
    s, ti = (t["deal_sub_category"] or "").upper(), (t["deal_title"] or "")
    tu = ti.upper()
    if "BARCO" in s or "BARCO" in tu:
        m = re.search(r"(\d{2}/\d{2})", s + " " + tu)
        return f"Barco {m.group(1)}" if m else "Barco"
    if "PACOTE" in s or "PACOTE" in tu: return "Combo 31/12 + 02/01"
    if "PASSAPORTE" in s or "PASSAPORTE" in tu: return "Passaporte"
    if s.startswith("RÉVEILLON") or "AVULSO REVEILLON" in tu or "AVULSO RÉVEILLON" in tu: return "Avulso Réveillon"
    return "Dias avulsos"

def grupo(p):
    return "Principal" if p in PRINCIPAIS else ("Barco" if p.startswith("Barco") else "Dia avulso")

def quem(t, p):
    """(canal, embaixador, sócio) pela lógica da Luciana: pedido -> link de promoter -> nome do ingresso."""
    u, ti = t.get("utm_source") or "", t["deal_title"] or ""
    if u in ADS: return "Anúncio", ADS[u], "Anúncio"
    if grupo(p) != "Principal": return "Barcos e dias avulsos", "", ""
    if u == SAC_EMB_LINK: return "SAC condição especial", "Tikal (SAC)", "Tikal (SAC)"
    info = PEDIDOS.get(str(t["order_id"])) or PROMO.get(u)
    if info:
        nome, socio, tipo = info
        tl = (tipo or "").lower()
        if "sac" in tl and "tikal" in tl: c = "SAC"
        elif "sac" in (socio or "").lower(): c = "Embaixador SAC"
        elif "embaix" in tl: c = "Embaixador"
        elif "sócio" in tl or "socio" in tl: c = "Sócio"
        elif "recorr" in tl: c = "Recorrência"
        elif "artista" in tl: c = "Artista"
        else: c = "Outros"
        return c, nome, socio
    if re.search(r"\bSAC\b", ti): return "SAC", "Tikal (SAC)", "Tikal (SAC)"
    if u.startswith("promoter-"): return "Promoter novo (sem nome)", u, "Sem sócio"
    return "Sem promoter", "", ""

def canal(t, p): return quem(t, p)[0]

def valor(t):
    if (t["deal_price"] or 0) == 0 and t["deal_title"] in PIX_VALUE: return PIX_VALUE[t["deal_title"]], "Pix direto"
    return (t["deal_price"] or 0) / 100, "Shotgun"

def pais(phone):
    ph = re.sub(r"[^\d+]", "", phone or "")
    if not ph: return "Sem telefone"
    if ph.startswith("+55"): return "Brasil"
    return "Estrangeiro"

def norm_phone(s):
    d = re.sub(r"\D", "", s or "")
    return d[-8:] if len(d) >= 8 else None

rows = []
for t in T:
    if t["ticket_status"] != "valid": continue
    day = t["ordered_at"][:10]
    if CUTOFF and day > CUTOFF: continue
    p = produto(t); v, via = valor(t)
    c3 = quem(t, p)
    rows.append(dict(t=t, day=day, produto=p, grupo=grupo(p), canal=c3[0], emb=c3[1], socio=c3[2], valor=v, via=via,
                     origem=pais(t["contact_phone"]), cond="Condição Especial" in (t["deal_title"] or "") or t.get("utm_source") in (SAC_EMB_LINK, "promoter-31594")))

def dump(name, data, meta=None):
    json.dump({"rows": data, "meta": meta or []} if meta else data, open(f"{OUT}/{name}.json", "w"), ensure_ascii=False, indent=0)

now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).strftime("%Y-%m-%d %H:%M")
# 1. vendas por produto e forma de pagamento
agg = C.defaultdict(lambda: [0, 0.0])
for r in rows: a = agg[(r["produto"], r["grupo"], r["via"])]; a[0] += 1; a[1] += r["valor"]
dump("vendas_produto", [dict(produto=k[0], grupo=k[1], via=k[2], qtd=v[0], receita=round(v[1], 2)) for k, v in sorted(agg.items())])
# 2. vendas por dia (data calendário e dia de venda)
agg = C.defaultdict(lambda: [0, 0.0])
for r in rows: a = agg[(r["day"], r["produto"], r["grupo"])]; a[0] += 1; a[1] += r["valor"]
dump("vendas_dia", [dict(ano=2027, data=k[0], dia_venda=(dt.date.fromisoformat(k[0]) - SALES_START).days + 1,
                         produto=k[1], grupo=k[2], qtd=v[0], receita=round(v[1], 2)) for k, v in sorted(agg.items())])
# 3. canal x produto
agg = C.defaultdict(lambda: [0, 0.0])
for r in rows: a = agg[(r["canal"], r["produto"])]; a[0] += 1; a[1] += r["valor"]
dump("canal_produto", [dict(canal=k[0], produto=k[1], qtd=v[0], receita=round(v[1], 2)) for k, v in sorted(agg.items())])
# 4. gênero (comprador) nos ingressos principais
g = C.Counter({"male": "Homens", "female": "Mulheres"}.get(r["t"]["contact_gender"], "Não binário / não informou") for r in rows if r["grupo"] == "Principal")
dump("genero", [dict(genero=k, qtd=v) for k, v in g.most_common()])
# 5. origem (Brasil x estrangeiro) por produto e condição especial
agg = C.defaultdict(lambda: [0, 0.0])
for r in rows: a = agg[(r["origem"], r["produto"], r["grupo"], "Sim" if r["cond"] else "Não")]; a[0] += 1; a[1] += r["valor"]
dump("origem", [dict(origem=k[0], produto=k[1], grupo=k[2], condicao_especial=k[3], qtd=v[0], receita=round(v[1], 2)) for k, v in sorted(agg.items())])
# 6. barcos: compradores de passaporte/combo que também compraram barco (cruzando e-mail e nome)
def keys(t):
    ks = set()
    if t.get("contact_email"): ks.add("e:" + t["contact_email"].strip().lower())
    nm = f'{t.get("contact_first_name") or ""} {t.get("contact_last_name") or ""}'.strip().lower()
    if len(nm) > 4: ks.add("n:" + nm)
    return ks
pk = C.defaultdict(set)
for r in rows:
    if r["produto"] in ("Passaporte", "Combo 31/12 + 02/01"): 
        for k in keys(r["t"]): pk[k].add(r["produto"])
people_main = set(); out = []
by_boat = C.defaultdict(lambda: {"ingressos": 0, "Passaporte": set(), "Combo 31/12 + 02/01": set(), "sem_match": 0})
for r in rows:
    if r["grupo"] != "Barco": continue
    b = by_boat[r["produto"]]; b["ingressos"] += 1
    ks = keys(r["t"]); prods = set().union(*[pk[k] for k in ks if k in pk]) if ks else set()
    ident = min(ks) if ks else str(r["t"]["ticket_id"])
    if not prods: b["sem_match"] += 1
    for p in prods: b[p].add(ident)
for boat, b in sorted(by_boat.items()):
    out.append(dict(barco=boat, ingressos_barco=b["ingressos"], com_passaporte=len(b["Passaporte"]),
                    com_combo=len(b["Combo 31/12 + 02/01"]), sem_cruzamento=b["sem_match"]))
dump("barcos", out)
# clientes únicos de passaporte/combo com algum barco
cli = C.defaultdict(lambda: {"main": set(), "barco": False})
for r in rows:
    ks = keys(r["t"]); 
    if not ks: continue
    k = min(ks)
    if r["produto"] in ("Passaporte", "Combo 31/12 + 02/01", "Avulso Réveillon"): cli[k]["main"].add(r["produto"])
    if r["grupo"] == "Barco": cli[k]["barco"] = True
tot = C.Counter(); com = C.Counter()
for c in cli.values():
    for p in c["main"]:
        tot[p] += 1; com[p] += c["barco"]
dump("clientes_barco", [dict(produto=p, clientes=tot[p], com_barco=com[p]) for p in PRINCIPAIS])
# 7. anúncios (links ADS Roberto)
agg = C.defaultdict(lambda: [0, 0.0])
for r in rows:
    u = r["t"].get("utm_source")
    if u in ADS: a = agg[(ADS[u], r["produto"], "Sim" if r["grupo"] == "Principal" else "Não")]; a[0] += 1; a[1] += r["valor"]
dump("anuncios_links", [dict(link=k[0], produto=k[1], comissionavel=k[2], qtd=v[0], receita=round(v[1], 2)) for k, v in sorted(agg.items())])
# 8. países (estrangeiros)
cc = C.Counter()
for r in rows:
    if r["origem"] == "Estrangeiro" and r["grupo"] == "Principal":
        cc[r["t"].get("contact_country") or "Não informado"] += 1
dump("paises", [dict(pais=k, qtd=v) for k, v in cc.most_common()])
# 9. leads (planilha de leads, só contagens)
L = json.load(open(f"{LEADS}/leads.json"))
ce = L["condicoes"]
buyers = C.defaultdict(list)
for r in rows:
    k = norm_phone(r["t"].get("contact_phone"))
    if k: buyers[k].append(r)
def foreign_lead(ph, txt):
    ph = (ph or "").strip(); d = re.sub(r"\D", "", ph)
    if "gringo" in txt or "estrangeiro" in txt: return True
    if "instagram" in ph: return False
    return not re.match(r"^\d{2}\s?9?\d{4}-?\s?\d{4}$", ph)
def tipo_oferta(s):
    s = (s or "").lower()
    if "upgrade" in s: return "Upgrade"
    if "lote anterior" in s or "2950" in s: return "Lote anterior"
    if "1300" in s: return "Dia 02 por R$ 1.300"
    if "recorr" in s: return "Recorrência"
    if "vende" in s or "ganha" in s: return "Grupo (compra X, ganha 1)"
    if "embaix" in s: return "Valor embaixador"
    return "Outras"
def tipo_ingresso(s):
    s = (s or "").lower()
    if "passa" in s and ("combo" in s or "d2" in s or "avulso" in s): return "Mais de um tipo"
    if "passa" in s: return "Passaporte"
    if s.startswith("combo"): return "Combo 31/12 + 02/01"
    if s.startswith("d2"): return "Dia 02 (D2)"
    if s.startswith(("avulso", "virada")): return "Avulso Réveillon"
    return "A definir / sem resposta"
agg = C.defaultdict(lambda: [0, 0, 0, 0])
for r in ce:
    txt = (r[7] or "").lower(); k = norm_phone(r[2])
    conv = bool(k and k in buyers) or (r[4] or "").strip().lower().startswith(("sim", "parcial"))
    fr = foreign_lead(r[2], txt)
    a = agg[(tipo_oferta(txt), tipo_ingresso(r[6]))]; a[0] += 1; a[1] += conv; a[2] += fr; a[3] += fr and conv
dump("condicoes_especiais", [dict(tipo=k[0], ingresso=k[1], ofertas=v[0], converteram=v[1], estrangeiros=v[2], estrangeiros_converteram=v[3]) for k, v in sorted(agg.items())])
dump("leads", [dict(metrica="Contatos no WhatsApp em 2026", valor=L["contatos_total"]),
               dict(metrica="Leads vindos de anúncio", valor=L["anuncios_total"]),
               dict(metrica="Condições especiais oferecidas", valor=len(ce))])
# 10. vendas por lote (nome do ingresso na Shotgun), só ingressos principais
agg = {}
for r in rows:
    if r["grupo"] != "Principal": continue
    k = r["t"]["deal_title"]
    a = agg.setdefault(k, dict(ingresso=k, produto=r["produto"], inicio=r["day"], qtd=0, receita=0.0, pix=0))
    a["inicio"] = min(a["inicio"], r["day"]); a["qtd"] += 1; a["receita"] += r["valor"]; a["pix"] += r["via"] == "Pix direto"
dump("vendas_lote", [dict(v, receita=round(v["receita"], 2), valor_un=round(v["receita"] / v["qtd"], 2)) for v in sorted(agg.values(), key=lambda x: (x["produto"], x["inicio"], x["ingresso"]))])
# 11. cidades, estados (CEP) e faixa etária dos compradores de ingressos principais
CEP_UF = [(1000,19999,"SP"),(20000,28999,"RJ"),(29000,29999,"ES"),(30000,39999,"MG"),(40000,48999,"BA"),(49000,49999,"SE"),(50000,56999,"PE"),
          (57000,57999,"AL"),(58000,58999,"PB"),(59000,59999,"RN"),(60000,63999,"CE"),(64000,64999,"PI"),(65000,65999,"MA"),(66000,68899,"PA"),
          (68900,68999,"AP"),(69000,69299,"AM"),(69300,69399,"RR"),(69400,69899,"AM"),(69900,69999,"AC"),(70000,72799,"DF"),(72800,72999,"GO"),
          (73000,73699,"DF"),(73700,76799,"GO"),(76800,76999,"RO"),(77000,77999,"TO"),(78000,78899,"MT"),(79000,79999,"MS"),(80000,87999,"PR"),
          (88000,89999,"SC"),(90000,99999,"RS")]
def uf(t):
    if (t.get("contact_country") or "") not in ("Brazil", "Brasil"): return None
    d = re.sub(r"\D", "", t.get("contact_postal_code") or "")
    if len(d) < 5: return "Não informado"
    n = int(d[:5])
    return next((u for a, b, u in CEP_UF if a <= n <= b), "Não informado")
main_rows = [r for r in rows if r["grupo"] == "Principal"]
cid = C.Counter((r["t"].get("contact_locality") or "Não informada").strip() for r in main_rows)
dump("cidades", [dict(cidade=k, qtd=v) for k, v in cid.most_common(15)])
ufs = C.Counter(u for u in (uf(r["t"]) for r in main_rows) if u)
dump("estados", [dict(estado=k, qtd=v) for k, v in ufs.most_common()])
def faixa(b):
    if not b: return "Não informada"
    try: idade = (dt.date(2026, 12, 26) - dt.date.fromisoformat(b[:10])).days // 365
    except ValueError: return "Não informada"
    for lim, lab in ((24, "18–24"), (29, "25–29"), (34, "30–34"), (39, "35–39"), (44, "40–44"), (49, "45–49")):
        if idade <= lim: return lab
    return "50+"
ORD = ["18–24", "25–29", "30–34", "35–39", "40–44", "45–49", "50+", "Não informada"]
fx = C.Counter(faixa(r["t"].get("contact_birthday")) for r in main_rows)
dump("idade", [dict(faixa=k, ordem=i, qtd=fx.get(k, 0)) for i, k in enumerate(ORD)])
# 12. dia da semana e hora da compra (horário da Bahia), ingressos principais
hs = C.Counter()
for r in main_rows:
    try: d = dt.datetime.fromisoformat(r["t"]["ordered_at"][:19]) - dt.timedelta(hours=3)
    except ValueError: continue
    hs[(d.weekday(), d.hour)] += 1
dump("hora_semana", [dict(dia_semana=k[0], hora=k[1], qtd=v) for k, v in sorted(hs.items())])
# 13. público esperado por dia do festival
DIAS_EVT = [("2026-12-26", "26/12", "Lava, Bahia!"), ("2026-12-27", "27/12", "Paredonn de Forró"), ("2026-12-28", "28/12", "Gramadão Open"),
            ("2026-12-29", "29/12", "Quebra Côco"), ("2026-12-30", "30/12", "Divino Maravilhoso"), ("2026-12-31", "31/12", "Réveillon"),
            ("2027-01-01", "01/01", "—"), ("2027-01-02", "02/01", "Samba do D2")]
def dia_do_ingresso(r):
    s = ((r["t"]["deal_sub_category"] or "") + " " + (r["t"]["deal_title"] or "")).upper()
    if r["produto"] == "Avulso Réveillon": return ["31/12"]
    if r["produto"] == "Combo 31/12 + 02/01": return ["31/12", "02/01"]
    if r["grupo"] == "Dia avulso": return [d for _, d, _ in DIAS_EVT if d in s][:1]
    return []
pas = sum(1 for r in rows if r["produto"] == "Passaporte")
dia_q = C.Counter(); barco_q = C.Counter()
for r in rows:
    for d in dia_do_ingresso(r): dia_q[d] += 1
    if r["grupo"] == "Barco": barco_q[r["produto"][-5:]] += 1
dump("publico_dia", [dict(data=iso, dia=d, festa=f, ordem=i, passaporte=pas, ingressos_do_dia=dia_q[d], barco=barco_q[d]) for i, (iso, d, f) in enumerate(DIAS_EVT)])
# 14. check-in (ingressos lidos na entrada), por dia e hora, horário da Bahia
ck = C.Counter()
for r in rows:
    sc = r["t"].get("ticket_scanned_at")
    if not sc: continue
    try: d = dt.datetime.fromisoformat(sc[:19]) - dt.timedelta(hours=3)
    except ValueError: continue
    ck[(d.date().isoformat(), d.hour, r["grupo"])] += 1
dump("checkin", [dict(data=k[0], hora=k[1], grupo=k[2], qtd=v) for k, v in sorted(ck.items())] or [dict(data=None, hora=None, grupo=None, qtd=0)])
# 15. reembolsos e revendas (todos os status)
cx = C.defaultdict(lambda: [0, 0.0])
for t in T:
    st = t["ticket_status"]
    if st == "valid": continue
    p = produto(t); mes = (t.get("ticket_canceled_at") or t.get("ticket_updated_at") or "")[:7]
    a = cx[({"refunded": "Reembolsado", "resold": "Revendido"}.get(st, st), p, mes)]; a[0] += 1; a[1] += (t["deal_price"] or 0) / 100
dump("cancelamentos", [dict(status=k[0], produto=k[1], mes=k[2], qtd=v[0], valor=round(v[1], 2)) for k, v in sorted(cx.items())])
# 16. taxas da Shotgun sobre os ingressos válidos
vt = [t for t in T if t["ticket_status"] == "valid"]
base = sum((t["deal_price"] or 0) for t in vt) / 100
dump("taxas", [dict(taxa_comprador=round(sum((t["deal_user_service_fee"] or 0) for t in vt) / 100, 2),
                    custo_produtor=round(sum((t["deal_service_fee"] or 0) + (t["deal_producer_cost"] or 0) for t in vt) / 100, 2),
                    valor_ingressos=round(base, 2))])
# 17. vendas por embaixador e por sócio (ingressos principais)
agg = C.defaultdict(lambda: [0, 0.0])
for r in main_rows:
    if r["canal"] in ("Barcos e dias avulsos",): continue
    a = agg[(r["emb"] or r["canal"], r["socio"] or r["canal"], r["canal"])]; a[0] += 1; a[1] += r["valor"]
dump("vendas_embaixador", [dict(embaixador=k[0], socio=k[1], canal=k[2], qtd=v[0], receita=round(v[1], 2)) for k, v in sorted(agg.items(), key=lambda x: -x[1][0])])
agg = C.defaultdict(lambda: [0, 0.0])
for r in main_rows: a = agg[r["socio"] or r["canal"]]; a[0] += 1; a[1] += r["valor"]
dump("vendas_socio", [dict(socio=k, qtd=v[0], receita=round(v[1], 2)) for k, v in sorted(agg.items(), key=lambda x: -x[1][0])])
# 18. embaixadores cadastrados por sócio e vendas recentes
hoje = dt.date.fromisoformat(now[:10])
cad = S.get("cadastros", [])
SOCIOS = ["Craig", "Francisco", "Gabriel Rache", "Gigios", "João Fernandes", "Julia Bueno (SAC)", "Leão", "Vitor Kurc"]
def socio_key(s):
    s = (s or "").lower()
    for k in SOCIOS:
        if k.split()[0].lower() in s: return k
    return None
v7 = C.Counter(); v30 = C.Counter()
for r in main_rows:
    if r["canal"] not in ("Embaixador", "Embaixador SAC"): continue
    k = socio_key(r["socio"]); d = (hoje - dt.date.fromisoformat(r["day"])).days
    if k and d < 7: v7[k] += 1
    if k and d < 30: v30[k] += 1
emb_socio = []
for k in SOCIOS:
    cs = [c for c in cad if c["socio"] == k]
    datas = [c["data"] for c in cs if c["data"]]
    emb_socio.append(dict(socio=k, cadastrados=len(cs), novos_30d=sum(1 for x in datas if (hoje - dt.date.fromisoformat(x)).days < 30),
                          ultimo_cadastro=max(datas) if datas else None, vendas_7d=v7[k], vendas_30d=v30[k]))
dump("embaixadores_socio", emb_socio)
# 19. recorrência: clientes de edições anteriores que compraram de novo (e-mail comparado por HMAC)
import hmac, hashlib
hh = lambda e: hmac.new(SALT.encode(), (e or "").strip().lower().encode(), hashlib.sha256).hexdigest()[:20]
prev = set(S.get("clientes_anteriores", []))
atuais = {hh(r["t"].get("contact_email")) for r in main_rows if r["t"].get("contact_email")}
ret = len(prev & atuais) if SALT else 0
dump("recorrencia", [dict(base=len(prev), retidos=ret, taxa=round(ret / len(prev), 4) if prev else 0,
                          metas=[dict(taxa=t, clientes=round(t * len(prev))) for t in (0.085, 0.095, 0.108, 0.121)])])
# 20. lotes: meta x vendido (metas do relatório da Luciana)
METAS = {("Passaporte", "Pré-venda secreta"): 120, ("Passaporte", "Pré-venda (pré-cadastro)"): 130, ("Passaporte", "1º lote"): 106,
         ("Passaporte", "2º lote"): 210, ("Passaporte", "3º lote"): 228, ("Passaporte", "4º lote"): 110, ("Passaporte", "Morador"): 11,
         ("Passaporte", "Pix especial"): 3, ("Avulso Réveillon", "1º lote"): 13, ("Avulso Réveillon", "2º lote"): 55, ("Avulso Réveillon", "3º lote"): 83,
         ("Combo 31/12 + 02/01", "1º lote"): 23, ("Combo 31/12 + 02/01", "2º lote"): 95, ("Combo 31/12 + 02/01", "3º lote"): 55}
def lote(ti):
    s = (ti or "").lower()
    if "secreta" in s: return "Pré-venda secreta"
    if "pré venda" in s or "pre venda" in s: return "Pré-venda (pré-cadastro)"
    if "morador" in s: return "Morador"
    m = re.search(r"(\d)\s*[º°o]\s*lote", s)
    return f"{m.group(1)}º lote" if m else "Outros"
vl = C.Counter((r["produto"], lote(r["t"]["deal_title"])) for r in main_rows)
ordem = list(METAS)
lotes = [dict(produto=k[0], lote=k[1], ordem=i, meta=m, vendido=vl.get(k, 0), falta=max(0, m - vl.get(k, 0))) for i, (k, m) in enumerate(METAS.items())]
lotes += [dict(produto=k[0], lote=k[1], ordem=99, meta=0, vendido=v, falta=0) for k, v in vl.items() if k not in METAS]
dump("lotes", lotes)
# 21. históricos (2024-2026) e embaixadores ao longo dos anos com 2027
for k in ("hist_dia", "hist_cal", "hist_canal", "hist_estrangeiros"):
    dump(k, S.get(k, []))
ativos = {r["emb"] for r in main_rows if r["canal"] == "Embaixador"}
dump("hist_embaixadores", S.get("hist_embaixadores", []) + [dict(ano=2027, cadastrados=sum(1 for c in cad if c["socio"] != "Julia Bueno (SAC)"),
     ativos=len(ativos), vendas_emb=sum(1 for r in main_rows if r["canal"] == "Embaixador"))])
json.dump({"atualizado_em": now, "tickets_validos": len(rows)}, open(f"{OUT}/_info.json", "w"))
print("ok", len(rows), "tickets válidos;", now)
