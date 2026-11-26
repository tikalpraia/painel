"""Criptografa/descriptografa arquivos do painel com a senha (AES-GCM, chave PBKDF2-SHA256 200 mil iterações).
Uso: cofre.py fechar <entrada.json> <saida.enc.json>   |   cofre.py abrir <entrada.enc.json> <saida.json>
A senha vem da variável PAINEL_SENHA."""
import base64, json, os, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
ITER = 200_000
def chave(senha, sal):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sal, iterations=ITER).derive(senha.encode())
def fechar(dados: bytes, senha: str) -> dict:
    sal, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(chave(senha, sal)).encrypt(iv, dados, None)
    b = lambda x: base64.b64encode(x).decode()
    return {"v": 1, "iter": ITER, "sal": b(sal), "iv": b(iv), "dados": b(ct)}
def abrir(env: dict, senha: str) -> bytes:
    d = lambda k: base64.b64decode(env[k])
    return AESGCM(chave(senha, d("sal"))).decrypt(d("iv"), d("dados"), None)
if __name__ == "__main__":
    modo, ent, sai = sys.argv[1:4]; senha = os.environ["PAINEL_SENHA"]
    if modo == "fechar": json.dump(fechar(open(ent, "rb").read(), senha), open(sai, "w"))
    else: open(sai, "wb").write(abrir(json.load(open(ent)), senha))
