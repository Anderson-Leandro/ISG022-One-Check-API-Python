"""
DEBT-003 — Uma rota canônica por operação de MFA (ADR-0013)

- O próprio MFA: /auth/mfa/* (setup, activate, habilitar, desabilitar).
- O MFA de outro usuário: /usuarios/{id}/mfa (POST /enable e DELETE).
- Os aliases continuam funcionando até 2027-01-31, com deprecated=True no OpenAPI e os cabeçalhos
  Deprecation, Sunset e Link (a sucessora) em toda resposta, inclusive 401 e 403.
- GET /auth/mfa/setup (obsoleto desde antes) sai: 405, sem gerar segredo.
"""

import pytest

from app.models import Usuario
from app.obsoletas import ROTAS, sucessora
from tests.conftest import auth

API = "/api/v1"
SUNSET = "Sun, 31 Jan 2027 00:00:00 GMT"
OBSOLETAS = [(r.metodo, r.caminho) for r in ROTAS]
CANONICAS = [
    ("post", "/auth/mfa/setup"),
    ("post", "/auth/mfa/activate"),
    ("post", "/auth/mfa/habilitar"),
    ("post", "/auth/mfa/desabilitar"),
    ("post", "/usuarios/{usuario_id}/mfa/enable"),
    ("delete", "/usuarios/{usuario_id}/mfa"),
]


@pytest.fixture
def openapi(client):
    return client.get("/openapi.json").json()["paths"]


def _no_openapi(caminho):
    return API + caminho


class TestGetSetupRemovido:
    def test_get_responde_405_e_nao_gera_segredo(self, client, db, user_admin, token_admin):
        pendente = user_admin.mfa_secret_pendente

        r = client.get(f"{API}/auth/mfa/setup", headers=auth(token_admin))

        assert r.status_code == 405
        db.expire_all()
        assert db.get(Usuario, user_admin.id).mfa_secret_pendente == pendente

    def test_get_sai_do_openapi_e_o_post_continua(self, openapi):
        assert set(openapi[f"{API}/auth/mfa/setup"]) == {"post"}


class TestOpenapi:
    @pytest.mark.parametrize("metodo,caminho", OBSOLETAS)
    def test_alias_marcado_como_obsoleto_com_a_data(self, openapi, metodo, caminho):
        op = openapi[_no_openapi(caminho)][metodo.lower()]
        assert op.get("deprecated") is True
        assert "2027-01-31" in op["description"]

    @pytest.mark.parametrize("metodo,caminho", CANONICAS)
    def test_canonica_nao_e_obsoleta(self, openapi, metodo, caminho):
        assert not openapi[API + caminho][metodo].get("deprecated")


class TestCabecalhos:
    @pytest.mark.parametrize("metodo,caminho", OBSOLETAS)
    def test_alias_avisa_mesmo_sem_autenticacao(self, client, metodo, caminho):
        r = client.request(metodo, API + caminho.replace("{usuario_id}", "abc"), json={})
        assert r.status_code == 401
        assert r.headers["deprecation"].startswith("@")
        assert r.headers["sunset"] == SUNSET

    def test_link_aponta_a_sucessora_com_o_mesmo_id(self, client, token_admin, user_locatario):
        r = client.post(f"{API}/usuarios/{user_locatario.id}/mfa/habilitar", headers=auth(token_admin))
        assert r.status_code == 200
        assert r.headers["link"] == f'<{API}/usuarios/{user_locatario.id}/mfa/enable>; rel="successor-version"'

    def test_alias_continua_funcionando(self, client, db, token_admin, user_locatario):
        r = client.post(f"{API}/usuarios/{user_locatario.id}/mfa/habilitar", headers=auth(token_admin))
        assert r.json()["sucesso"] is True
        db.expire_all()
        assert db.get(Usuario, user_locatario.id).mfa_enabled is True

    def test_id_vai_codificado_no_link(self, client):
        r = client.post(f"{API}/usuarios/x%3E%3B%20rel%3D%22a%22/mfa/habilitar")
        assert r.status_code == 401
        assert r.headers["link"] == f'<{API}/usuarios/x%3E%3B%20rel%3D%22a%22/mfa/enable>; rel="successor-version"'

    def test_sem_link_quando_a_sucessora_depende_do_corpo(self, client, token_admin, user_locatario):
        r = client.post(f"{API}/auth/mfa/disable", json={"usuario_id": user_locatario.id}, headers=auth(token_admin))
        assert r.headers["sunset"] == SUNSET
        assert "link" not in r.headers

    @pytest.mark.parametrize("metodo,caminho", CANONICAS)
    def test_canonica_nao_avisa(self, client, metodo, caminho):
        r = client.request(metodo, API + caminho.replace("{usuario_id}", "abc"), json={})
        assert "deprecation" not in r.headers and "sunset" not in r.headers

    def test_cors_expoe_os_cabecalhos_do_aviso(self):
        """O front, em outra origem, só lê esses cabeçalhos se o CORS os expuser."""
        from fastapi.middleware.cors import CORSMiddleware

        from app.main import app

        [cors] = [m for m in app.user_middleware if m.cls is CORSMiddleware]
        assert {"Deprecation", "Sunset", "Link"} <= set(cors.kwargs["expose_headers"])


class TestSucessora:
    @pytest.mark.parametrize(
        "metodo,caminho,esperado",
        [
            ("POST", f"{API}/usuarios/me/mfa/setup", f"{API}/auth/mfa/setup"),
            ("DELETE", f"{API}/usuarios/me/mfa", f"{API}/auth/mfa/desabilitar"),
            ("POST", f"{API}/usuarios/u-1/mfa/desabilitar/", f"{API}/usuarios/u-1/mfa"),
        ],
    )
    def test_alias_tem_sucessora(self, metodo, caminho, esperado):
        assert sucessora(metodo, caminho)[1] == esperado

    @pytest.mark.parametrize(
        "metodo,caminho",
        [
            ("GET", f"{API}/usuarios/me/mfa"),
            ("DELETE", f"{API}/usuarios/u-1/mfa"),
            ("POST", f"{API}/usuarios/u-1/mfa/enable"),
            ("POST", f"{API}/usuarios/me/mfa/setup/extra"),
            ("POST", "/usuarios/me/mfa/setup"),
            # "me" não é um id: /usuarios/me/mfa/desabilitar não é o alias do reset de outro usuário
            ("POST", f"{API}/usuarios/me/mfa/desabilitar"),
        ],
    )
    def test_outras_rotas_nao_tem(self, metodo, caminho):
        assert sucessora(metodo, caminho) is None


class TestTabela:
    def test_cada_obsoleta_existe_no_router_e_so_ela_e_deprecated(self, openapi):
        marcadas = {(m.upper(), c) for c, ops in openapi.items() for m, op in ops.items() if op.get("deprecated")}
        assert marcadas == {(r.metodo, API + r.caminho) for r in ROTAS}

    def test_tabela_com_rota_inexistente_falha_ao_gerar_o_openapi(self):
        from fastapi import FastAPI

        from app import obsoletas

        vazio = FastAPI()
        obsoletas.marcar_no_openapi(vazio)
        with pytest.raises(RuntimeError, match="sem rota correspondente"):
            vazio.openapi()
