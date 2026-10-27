"""
Segurança — SEC-007: CORS * com credenciais, /docs público e sem cabeçalhos de segurança

Cenário original: CORS_ORIGINS="*" por padrão (e no render.yaml) com
allow_credentials=True, o que faz o Starlette devolver a origem de qualquer site
como permitida. /docs, /redoc e /openapi.json ficavam abertos em produção, e as
respostas não tinham nosniff, HSTS nem Cache-Control: no-store.

Regras verificadas:
  - CORS: só as origens configuradas; nunca com credenciais; sem CORS_ORIGINS
    em produção, nenhuma origem; Retry-After legível pelo front
  - /docs, /redoc e /openapi.json desligados em produção (DOCS_ENABLED liga)
  - nosniff, X-Frame-Options, Referrer-Policy e Cache-Control: no-store em toda
    resposta da API, inclusive erros; HSTS fora de desenvolvimento
  - fotos (/uploads) mantêm o cache e os cabeçalhos próprios

Os casos de produção rodam num processo novo, porque a configuração é lida na importação.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import auth, small_image_bytes

RAIZ = Path(__file__).resolve().parents[2]
FRONT = "https://front.onecheck.exemplo"
ESTRANHO = "https://site-malicioso.exemplo"

# Executado no processo novo: faz as requisições e imprime status e cabeçalhos em JSON
_SCRIPT = """
import json, sys
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
saida = []
for metodo, url, headers in json.loads(sys.argv[1]):
    r = c.request(metodo, url, headers=headers)
    saida.append({"status": r.status_code, "headers": {k.lower(): v for k, v in r.headers.items()}})
print(json.dumps(saida))
"""


def _em_producao(requisicoes, tmp_path, **env):
    base = {k: v for k, v in os.environ.items() if k not in ("CORS_ORIGINS", "DOCS_ENABLED")}
    base.update({
        "APP_ENV": "production", "JWT_SECRET": "x" * 48, "SEED_SECRET": "",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'prod.db'}", "UPLOAD_DIR": str(tmp_path / "uploads"),
        "CORS_ORIGINS": "", "DOCS_ENABLED": "",
    })
    base.update(env)
    # None remove a variável do ambiente (caso "não configurada")
    base = {k: v for k, v in base.items() if v is not None}
    r = subprocess.run([sys.executable, "-c", _SCRIPT, json.dumps(requisicoes)],
                       cwd=RAIZ, env=base, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _preflight(origem):
    return ["OPTIONS", "/api/v1/auth/login", {"Origin": origem, "Access-Control-Request-Method": "POST"}]


class TestCorsProducao:
    @pytest.mark.parametrize("valor", [None, ""], ids=["ausente", "vazio"])
    def test_sem_cors_origins_nenhuma_origem_e_aceita(self, tmp_path, valor):
        r, simples = _em_producao([_preflight(FRONT), ["GET", "/api/v1/health", {"Origin": ESTRANHO}]], tmp_path, CORS_ORIGINS=valor)
        assert "access-control-allow-origin" not in r["headers"]
        assert "access-control-allow-origin" not in simples["headers"]

    def test_origem_configurada_aceita_sem_credenciais(self, tmp_path):
        [r] = _em_producao([_preflight(FRONT)], tmp_path, CORS_ORIGINS=FRONT)
        assert r["headers"]["access-control-allow-origin"] == FRONT
        assert "access-control-allow-credentials" not in r["headers"]

    def test_origem_nao_configurada_recusada(self, tmp_path):
        [r] = _em_producao([_preflight(ESTRANHO)], tmp_path, CORS_ORIGINS=FRONT)
        assert r["headers"].get("access-control-allow-origin") != ESTRANHO

    def test_curinga_nao_reflete_a_origem_nem_libera_credenciais(self, tmp_path):
        [r] = _em_producao([["GET", "/api/v1/health", {"Origin": ESTRANHO}]], tmp_path, CORS_ORIGINS="*")
        assert r["headers"]["access-control-allow-origin"] == "*"
        assert "access-control-allow-credentials" not in r["headers"]

    def test_retry_after_exposto_ao_front(self, tmp_path):
        [r] = _em_producao([["GET", "/api/v1/health", {"Origin": FRONT}]], tmp_path, CORS_ORIGINS=FRONT)
        assert "retry-after" in r["headers"]["access-control-expose-headers"].lower()


class TestDocsProducao:
    def test_docs_desligados(self, tmp_path):
        rotas = ["/docs", "/redoc", "/openapi.json"]
        respostas = _em_producao([["GET", u, {}] for u in rotas], tmp_path)
        assert [r["status"] for r in respostas] == [404, 404, 404]

    def test_docs_enabled_liga(self, tmp_path):
        [r] = _em_producao([["GET", "/openapi.json", {}]], tmp_path, DOCS_ENABLED="true")
        assert r["status"] == 200

    def test_hsts_fora_de_desenvolvimento(self, tmp_path):
        [r] = _em_producao([["GET", "/api/v1/health", {}]], tmp_path)
        assert "max-age=" in r["headers"]["strict-transport-security"]


class TestCabecalhos:
    BASICOS = {"x-content-type-options": "nosniff", "x-frame-options": "DENY", "referrer-policy": "no-referrer"}

    def _confere(self, r, cache=True):
        for nome, valor in self.BASICOS.items():
            assert r.headers.get(nome) == valor, nome
        if cache:
            assert r.headers.get("cache-control") == "no-store"

    def test_resposta_autenticada(self, client, token_admin):
        self._confere(client.get("/api/v1/usuarios/me", headers=auth(token_admin)))

    def test_login(self, client):
        self._confere(client.post("/api/v1/auth/login", json={"email": "x@x.com", "senha": "y"}))

    @pytest.mark.parametrize("caso", ["401", "404", "413"])
    def test_erros(self, client, caso):
        if caso == "401":
            r = client.get("/api/v1/usuarios/me")
        elif caso == "404":
            r = client.get("/api/v1/nao-existe")
        else:
            r = client.post("/api/v1/auth/login", content=b"{}", headers={"Content-Type": "application/json", "Content-Length": str(10**9)})
        assert r.status_code == int(caso)
        self._confere(r)

    def test_sem_hsts_em_desenvolvimento(self, client):
        assert "strict-transport-security" not in client.get("/api/v1/health").headers

    def test_foto_mantem_cache_e_csp(self, client, db, checklist, imovel, token_vistoriador):
        from app.models import ChecklistItem, ImovelComodo, ItemVistoria
        comodo = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel.id).first()
        iv = ItemVistoria(nome="Piso", categoria="Acabamento")
        db.add(iv)
        db.flush()
        item = ChecklistItem(checklist_id=checklist.id, comodo_id=comodo.id, item_vistoria_id=iv.id, estado="bom")
        db.add(item)
        db.flush()
        up = client.post(f"/api/v1/checklists/{checklist.id}/itens/{item.id}/fotos",
                         files={"foto": ("a.png", small_image_bytes(), "image/png")}, headers=auth(token_vistoriador))
        url = up.json()["dados"]["url"]
        r = client.get(url[url.index("/api/v1/"):])
        assert r.status_code == 200
        assert r.headers.get("cache-control") != "no-store"
        assert "sandbox" in r.headers["content-security-policy"]
        self._confere(r, cache=False)

    def test_desenvolvimento_mantem_docs(self, client):
        assert client.get("/openapi.json").status_code == 200
