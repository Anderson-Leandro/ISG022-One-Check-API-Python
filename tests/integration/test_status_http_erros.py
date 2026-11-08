"""
Status HTTP dos erros de negócio (ADR-0003, DEBT-014)

O envelope continua {"sucesso": false, "erro": ..., "erros"?}; o status acompanha o resultado.
Uma amostra de cada linha da tabela do ADR. A regra geral (nenhum sucesso=false com 2xx) é
conferida em todos os testes pelo cliente de tests/conftest.py.

Rotas cobertas:
  POST /auth/login, POST /auth/refresh
  PUT  /usuarios/me/senha, POST /usuarios
  GET  /imoveis/{id}
  POST /contratos/{id}/agendamentos
"""

from tests.conftest import TEST_SENHA, auth

API = "/api/v1"
SENHA_NOVA = "Outra.Senha#2026x"


class TestSemSessaoValida401:
    def test_login_recusado(self, client, user_locatario):
        r = client.post(f"{API}/auth/login", json={"email": user_locatario.email, "senha": "errada"})
        assert r.status_code == 401
        assert r.json()["erro"] == "Credenciais inválidas"

    def test_login_de_email_inexistente_tem_a_mesma_resposta(self, client, user_locatario):
        existente = client.post(f"{API}/auth/login", json={"email": user_locatario.email, "senha": "errada"})
        inexistente = client.post(f"{API}/auth/login", json={"email": "nao.existe@test.com", "senha": "errada"})
        assert (inexistente.status_code, inexistente.json()) == (existente.status_code, existente.json())

    def test_refresh_recusado(self, client):
        r = client.post(f"{API}/auth/refresh", json={"refresh_token": "invalido"})
        assert r.status_code == 401
        assert r.json()["sucesso"] is False


class TestReautenticacaoComSessao403:
    def test_senha_atual_errada_responde_403_e_nao_401(self, client, db, user_locatario, token_locatario):
        # 401 levaria o cliente a renovar a sessão e repetir a tentativa (ADR-0003)
        hash_antes = user_locatario.senha_hash
        r = client.put(
            f"{API}/usuarios/me/senha",
            json={"senha_atual": "errada", "nova_senha": SENHA_NOVA},
            headers=auth(token_locatario),
        )
        assert r.status_code == 403
        assert r.json()["erro"] == "Senha atual incorreta"
        db.refresh(user_locatario)
        assert user_locatario.senha_hash == hash_antes

    def test_senha_atual_correta_continua_funcionando(self, client, token_locatario):
        r = client.put(
            f"{API}/usuarios/me/senha",
            json={"senha_atual": TEST_SENHA, "nova_senha": SENHA_NOVA},
            headers=auth(token_locatario),
        )
        assert r.status_code == 200
        assert r.json()["sucesso"] is True


class TestRecursoEConflito:
    def test_recurso_inexistente_responde_404(self, client, token_admin):
        r = client.get(f"{API}/imoveis/00000000-0000-0000-0000-000000000000", headers=auth(token_admin))
        assert r.status_code == 404
        assert r.json() == {"sucesso": False, "erro": "Imóvel não encontrado"}

    def test_email_duplicado_responde_409(self, client, user_locatario, token_admin):
        r = client.post(
            f"{API}/usuarios",
            json={"nome": "Duplicado", "email": user_locatario.email, "senha": SENHA_NOVA, "role": "locatario"},
            headers=auth(token_admin),
        )
        assert r.status_code == 409
        assert r.json()["sucesso"] is False


class TestCampoInvalido422:
    def test_campo_invalido_traz_erros_por_campo(self, client, contrato, token_admin):
        r = client.post(
            f"{API}/contratos/{contrato.id}/agendamentos",
            json={"tipo": "qualquer", "data_agendada": "2099-01-01T10:00:00"},
            headers=auth(token_admin),
        )
        assert r.status_code == 422
        corpo = r.json()
        assert corpo["sucesso"] is False
        assert "tipo" in corpo["erros"]
