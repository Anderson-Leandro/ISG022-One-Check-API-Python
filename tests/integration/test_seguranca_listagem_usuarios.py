"""
Segurança — Item 2: qualquer perfil listava todos os usuários

Cenário original: GET /usuarios exigia só um access token. Locatário,
vistoriador e visualizador recebiam nome, e-mail, CPF e estado do MFA de todos
os usuários ativos; com ?role=admin, a lista exata das contas mais valiosas.

Regra verificada: a listagem segue as demais rotas do recurso (admin e gestor).
"""
import pytest

from tests.conftest import auth

BASE = "/api/v1/usuarios"


class TestPerfisSemPermissao:
    @pytest.mark.parametrize("token_fixture", ["token_locatario", "token_vistoriador", "token_visualizador"])
    @pytest.mark.parametrize("query", ["", "?role=admin"])
    def test_listagem_negada(self, client, request, user_admin, token_fixture, query):
        token = request.getfixturevalue(token_fixture)
        r = client.get(f"{BASE}{query}", headers=auth(token))
        assert r.status_code == 403
        assert user_admin.email not in r.text


class TestPerfisComPermissao:
    @pytest.mark.parametrize("token_fixture", ["token_admin", "token_gestor"])
    def test_listagem_permitida(self, client, request, user_locatario, token_fixture):
        token = request.getfixturevalue(token_fixture)
        r = client.get(f"{BASE}?role=locatario", headers=auth(token))
        data = r.json()
        assert data["sucesso"] is True
        assert [u["email"] for u in data["dados"]] == [user_locatario.email]
