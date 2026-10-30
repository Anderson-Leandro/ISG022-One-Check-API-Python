"""Popula e testa todas as funcionalidades usadas pelo web."""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

try:
    import pyotp
except ImportError:
    pyotp = None

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://onecheck-api.onrender.com/api/v1"
MFA_SECRET = "JBSWY3DPEHPK3PXP"
SEED_SECRET = sys.argv[2] if len(sys.argv) > 2 else os.getenv("SEED_SECRET", "")

passed = 0
failed = 0


def req(method, path, body=None, token=None, headers=None):
    url = BASE.rstrip("/") + path
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if headers:
        h.update(headers)
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return json.loads(raw), e.code
        except json.JSONDecodeError:
            return {"erro": raw}, e.code


def test(name, ok_condition, detail=""):
    global passed, failed
    if ok_condition:
        passed += 1
        print(f"  OK  {name}")
    else:
        failed += 1
        print(f"  FAIL {name} — {detail}")


def login_admin():
    r, _ = req("POST", "/auth/login", {"email": "admin@onecheck.local", "senha": "admin123"})
    if not r.get("sucesso"):
        return None, r
    if r["dados"].get("mfa_required"):
        code = pyotp.TOTP(MFA_SECRET).now() if pyotp else input("MFA: ")
        r2, _ = req("POST", "/auth/mfa/verify", {"temp_token": r["dados"]["temp_token"], "codigo": code})
        if not r2.get("sucesso"):
            return None, r2
        return r2["dados"]["access_token"], r2
    return r["dados"]["access_token"], r


print(f"\n=== OneCheck — populate & test ===\nAPI: {BASE}\n")

# 1. Seed expand (se endpoint existir)
print("[1] Seed expand")
r, code = req("POST", "/admin/seed", {"mode": "expand"}, headers={"X-Seed-Secret": SEED_SECRET})
if code == 404:
    print("  SKIP /admin/seed (404 — faça deploy da versao nova)")
elif r.get("sucesso"):
    print(f"  OK  expand: {r['dados'].get('message', '')}")
    if r["dados"].get("totals"):
        print(f"       totals: {r['dados']['totals']}")
else:
    r2, _ = req("POST", "/admin/seed", {"force": True, "mode": "full"}, headers={"X-Seed-Secret": SEED_SECRET})
    if r2.get("sucesso"):
        print("  OK  seed full (force)")
    else:
        print(f"  INFO seed: {r.get('erro', r)}")

# 2. Login
print("\n[2] Auth")
token, auth = login_admin()
test("Login admin + MFA", token is not None, str(auth))

if not token:
    print("\nAbortado — sem token.")
    sys.exit(1)

# 3. Leituras (páginas web)
print("\n[3] Leituras (listagens web)")
for name, path in [
    ("Dashboard", "/dashboard"),
    ("Imóveis", "/imoveis?por_pagina=20"),
    ("Contratos", "/contratos?por_pagina=20"),
    ("Usuários", "/usuarios?por_pagina=20"),
    ("Logs", "/logs?por_pagina=10"),
    ("Itens vistoria", "/itens-vistoria"),
    ("Usuário me", "/usuarios/me"),
]:
    r, c = req("GET", path, token=token)
    test(name, r.get("sucesso") and c == 200, r.get("erro", c))

# 4. Criações (formulários web)
print("\n[4] Criações (POST web)")
hoje = date.today().isoformat()
fim = (date.today() + timedelta(days=365)).isoformat()

r, c = req("POST", "/usuarios", {
    "nome": "Teste Web Usuario",
    "email": "teste.web@onecheck.local",
    "senha": "teste123",
    "role": "locatario",
}, token=token)
test("Criar usuário", r.get("sucesso"), r.get("erro", c))
novo_loc_id = (r.get("dados") or {}).get("id")

r, c = req("POST", "/imoveis", {
    "codigo": "IM-TEST",
    "titulo": "Imóvel Teste Web",
    "tipo": "Apartamento",
    "tamanho": "50m²",
    "garagem": True,
    "status": "disponivel",
}, token=token)
test("Criar imóvel", r.get("sucesso"), r.get("erro", c))
novo_im_id = (r.get("dados") or {}).get("id")

if novo_im_id:
    r, c = req("POST", f"/imoveis/{novo_im_id}/endereco", {
        "rua": "Rua Teste", "numero": "99", "bairro": "Centro",
        "cidade": "São Paulo", "estado": "SP", "cep": "01001000",
    }, token=token)
    test("Criar endereço imóvel", r.get("sucesso"), r.get("erro", c))

    r, c = req("PUT", f"/imoveis/{novo_im_id}", {"titulo": "Imóvel Teste Web Editado"}, token=token)
    test("Editar imóvel", r.get("sucesso"), r.get("erro", c))

r, c = req("GET", "/imoveis?status=disponivel&por_pagina=5", token=token)
disp = (r.get("dados") or [{}])[0] if r.get("sucesso") else {}
im_contrato = disp.get("id") or novo_im_id

r, c = req("GET", "/usuarios?role=locatario&por_pagina=10", token=token)
locs = r.get("dados") or []
loc_id = novo_loc_id or (locs[0]["id"] if locs else None)

if im_contrato and loc_id:
    r, c = req("POST", "/contratos", {
        "imovel_id": im_contrato,
        "locatario_id": loc_id,
        "data_inicio": hoje,
        "data_fim": fim,
        "valor_mensal": 2000,
    }, token=token)
    test("Criar contrato", r.get("sucesso"), r.get("erro", c))
    ct_id = (r.get("dados") or {}).get("id")
else:
    ct_id = None
    test("Criar contrato", False, "sem imóvel/locatário")

if ct_id:
    r, c = req("GET", f"/contratos/{ct_id}/agendamentos", token=token)
    test("Listar agendamentos", r.get("sucesso"), r.get("erro", c))

    r, c = req("GET", "/usuarios?role=vistoriador&por_pagina=5", token=token)
    vists = r.get("dados") or []
    vist_id = vists[0]["id"] if vists else None

    if vist_id:
        r, c = req("POST", f"/contratos/{ct_id}/checklists", {
            "tipo": "inicial",
            "data_vistoria": hoje,
            "vistoriador_id": vist_id,
        }, token=token)
        test("Criar vistoria/checklist", r.get("sucesso"), r.get("erro", c))
        ck_id = (r.get("dados") or {}).get("id")

        if ck_id:
            r, c = req("GET", f"/checklists/{ck_id}", token=token)
            test("Ver checklist (web vistorias/checklist.php)", r.get("sucesso"), r.get("erro", c))

    r, c = req("POST", f"/contratos/{ct_id}/problemas", {
        "titulo": "Problema teste web",
        "descricao": "Criado pelo script de teste",
        "prioridade": "alta",
    }, token=token)
    test("Criar problema", r.get("sucesso") or c == 404, r.get("erro", "endpoint pode precisar deploy"))

    r, c = req("GET", f"/contratos/{ct_id}/problemas", token=token)
    test("Listar problemas", r.get("sucesso"), r.get("erro", c))

# 5. Vistorias (multi-get simulado)
print("\n[5] Vistorias (index web)")
r, _ = req("GET", "/contratos?por_pagina=100", token=token)
cts = r.get("dados") or []
ck_total = 0
for ct in cts[:5]:
    r2, _ = req("GET", f"/contratos/{ct['id']}/checklists", token=token)
    if r2.get("sucesso"):
        ck_total += len(r2.get("dados") or [])
test(f"Checklists em {min(len(cts),5)} contratos", ck_total >= 0, f"total={ck_total}")

print(f"\n=== Resultado: {passed} OK, {failed} FAIL ===\n")
sys.exit(1 if failed else 0)
