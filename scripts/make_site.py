"""Gera index.html (site público) a partir da página do painel do Claude (page.html).
O painel usa a API `dash` do Claude; aqui um pequeno substituto carrega data/bundle.json e desenha tudo no navegador."""
import re, sys
src = open(sys.argv[1] if len(sys.argv) > 1 else "page.html", encoding="utf-8").read()
src = re.sub(r'<meta name="dash-[^"]+"[^>]*>\s*', "", src)
SHIM = r"""
<script>
// Substituto da API do painel do Claude: lê data/bundle.json e redesenha os elementos marcados com data-draw.
window.dash = (() => {
  const loaders = {}, calcs = {}, cache = {}, draws = {};
  let raw = null, status = 'loading';
  const data = (id) => {
    if (status !== 'ok') return { status, data: [] };
    if (id in cache) return { status: 'ok', data: cache[id] };
    if (loaders[id]) { cache[id] = loaders[id]({ answer: raw }) || []; return { status: 'ok', data: cache[id] }; }
    if (calcs[id]) { const ins = calcs[id].inputs.map(data); if (ins.some((x) => x.status !== 'ok')) return { status: 'loading', data: [] };
      cache[id] = calcs[id].fn(...ins.map((x) => x.data)); return { status: 'ok', data: cache[id] }; }
    return { status: 'missing', data: [] };
  };
  const run = (name) => document.querySelectorAll(`[data-draw="${name}"]`).forEach((el) => {
    if (el.closest('[hidden]')) return;
    try { draws[name](el); } catch (e) { console.error(name, e); }
  });
  const runAll = () => Object.keys(draws).forEach(run);
  const api = {
    loader: (id, o) => { loaders[id] = o.fn; },
    calc: (id, o) => { calcs[id] = o; },
    data,
    draw: (name, fn) => {
      if (fn) {
        if (typeof fn === 'function') draws[name] = fn;
        else { const m = new WeakMap(); draws[name] = (el) => { if (!m.has(el)) m.set(el, fn.mount ? fn.mount(el) : null); fn.update && fn.update(el, m.get(el)); }; }
        if (status === 'ok') run(name);
      } else if (draws[name]) run(name);
    },
    onData: (fn) => fn(),
    setLink: (h) => { try { history.replaceState(null, '', '#' + h); } catch (e) {} setTimeout(runAll, 0); },
    params: () => ({}), setParams: () => {}, resetParams: () => {}, refresh: () => {},
  };
  const b64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
  const abrir = async (senha) => {
    const env = await (await fetch('data/bundle.enc.json?' + Date.now(), { cache: 'no-store' })).json();
    const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(senha), 'PBKDF2', false, ['deriveKey']);
    const key = await crypto.subtle.deriveKey({ name: 'PBKDF2', hash: 'SHA-256', salt: b64(env.sal), iterations: env.iter }, base, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
    const txt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b64(env.iv) }, key, b64(env.dados));
    return JSON.parse(new TextDecoder().decode(txt));
  };
  const entrar = async (senha, lembrar) => {
    const msg = document.getElementById('cofre-msg'); if (msg) msg.textContent = 'Abrindo…';
    try { raw = await abrir(senha); } catch (e) { if (msg) msg.textContent = 'Senha incorreta.'; try { localStorage.removeItem('painel-senha'); } catch (x) {} return; }
    try { if (lembrar) localStorage.setItem('painel-senha', senha); } catch (x) {}
    document.getElementById('cofre').hidden = true; document.getElementById('dash-root').hidden = false;
    status = 'ok'; runAll();
  };
  window.addEventListener('DOMContentLoaded', () => {
    document.getElementById('cofre-form').addEventListener('submit', (e) => { e.preventDefault(); entrar(document.getElementById('cofre-senha').value.trim(), document.getElementById('cofre-lembrar').checked); });
    let salva = null; try { salva = localStorage.getItem('painel-senha'); } catch (x) {}
    if (salva) entrar(salva, true);
    let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(runAll, 200); });
  });
  return api;
})();
</script>
"""
HEAD = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<title>Portal de Algodões 2027</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<style>
:root { --font-anthropic-sans: "Helvetica Neue", Arial, system-ui, sans-serif; --font-anthropic-serif: Georgia, serif; }
html, body { margin: 0; background: #F2E3C9; }
[hidden] { display:none !important; }
.cofre { min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px 16px; box-sizing:border-box; font-family: var(--font-anthropic-sans); }
.cofre form { width:100%; max-width:360px; background:#FBF4E6; border:1.5px solid #161513; border-radius:22px; padding:28px 24px; text-align:center; }
.cofre h1 { margin:12px 0 4px; font-size:26px; letter-spacing:-.02em; text-transform:uppercase; }
.cofre p { margin:0 0 18px; color:#5b5346; font-size:14px; }
.cofre input[type=password] { width:100%; box-sizing:border-box; border:1.5px solid #161513; border-radius:999px; padding:12px 16px; font-size:16px; background:#fff; }
.cofre button { margin-top:12px; width:100%; border:1.5px solid #161513; border-radius:999px; padding:12px; background:#161513; color:#F2E3C9; font-weight:700; font-size:15px; cursor:pointer; }
.cofre label { display:flex; gap:6px; align-items:center; justify-content:center; margin-top:12px; font-size:13px; color:#5b5346; }
.cofre .msg { min-height:18px; margin-top:10px; font-size:13px; color:#c2402f; }
.dash-select { border: 1.5px solid #161513; border-radius: 10px; padding: 4px 8px; background: #fff; color: #161513; font: 12px var(--font-anthropic-sans); }
</style>
""" + SHIM + """</head>
<body>
<div class="cofre" id="cofre">
  <form id="cofre-form" autocomplete="on">
    <svg viewBox="0 0 64 40" width="64" height="40" aria-hidden="true"><path d="M4 34 A28 28 0 0 1 60 34 Z" fill="none" stroke="#161513" stroke-width="3"/><g stroke="#161513" stroke-width="2.4"><line x1="32" y1="34" x2="32" y2="8"/><line x1="32" y1="34" x2="14" y2="14"/><line x1="32" y1="34" x2="50" y2="14"/><line x1="32" y1="34" x2="7" y2="26"/><line x1="32" y1="34" x2="57" y2="26"/></g><circle cx="32" cy="34" r="8" fill="#161513"/><line x1="0" y1="38" x2="64" y2="38" stroke="#161513" stroke-width="3"/></svg>
    <h1>Portal de Algodões</h1>
    <p>Painel dos sócios. Digite a senha para entrar.</p>
    <input type="password" id="cofre-senha" placeholder="Senha" aria-label="Senha" required autofocus>
    <button type="submit">Entrar</button>
    <label><input type="checkbox" id="cofre-lembrar" checked> Lembrar neste aparelho</label>
    <div class="msg" id="cofre-msg" role="status"></div>
  </form>
</div>
<div id="dash-root" hidden>
"""
open("index.html", "w", encoding="utf-8").write(HEAD + src + "\n</div>\n</body>\n</html>\n")
print("index.html gerado")
