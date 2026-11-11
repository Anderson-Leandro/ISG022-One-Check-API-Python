"""
DEBT-020 — Todo erro no envelope {sucesso, erro, erros} (ADR-0003)

Cenário original: as regras de negócio respondiam no envelope, mas o 401 de token, o 403 de perfil
(HTTPException das dependências), o 422 de corpo fora do schema (RequestValidationError do FastAPI), o
404 e o 405 do roteador e o 400 e o 413 do limite de corpo respondiam {"detail": ...}. Quem consome a API
precisava ler dois formatos, e o OpenAPI declarava os dois (DetalheErro).

Regras verificadas:
  - 401, 403, 404, 405, 413, 400 e 429 respondem {sucesso: false, erro, erros}, com o mesmo status
  - os cabeçalhos da exceção continuam na resposta (Retry-After do 429, Allow do 405)
  - o 422 de corpo fora do schema traz em `erros` a mensagem por campo, e `erro` é a primeira delas,
    sem o prefixo "Value error, " do Pydantic
  - nenhum erro responde com `detail`
  - o OpenAPI não declara DetalheErro nem o HTTPValidationError do FastAPI: todo erro é ErroResposta
"""

import pytest
from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import RATE_LIMIT_FALHAS_CONTA
from app.erros import registrar
from app.respostas import ErroResposta
from tests.conftest import TEST_SENHA, auth

API = "/api/v1"


def _envelope(r, status: int) -> dict:
    assert r.status_code == status, r.text
    corpo = r.json()
    assert "detail" not in corpo
    ErroResposta.model_validate(corpo)
    return corpo


class TestErrosDoFramework:
    def test_401_sem_token(self, client):
        corpo = _envelope(client.get(f"{API}/usuarios/me"), 401)
        assert corpo["erro"] == "Token ausente"
        assert corpo["erros"] is None

    def test_401_token_invalido(self, client):
        _envelope(client.get(f"{API}/usuarios/me", headers={"Authorization": "Bearer nao-e-um-jwt"}), 401)

    def test_403_de_perfil(self, client, token_locatario):
        corpo = _envelope(client.get(f"{API}/logs", headers=auth(token_locatario)), 403)
        assert corpo["erro"] == "Permissão negada"

    def test_404_de_rota_inexistente(self, client):
        _envelope(client.get(f"{API}/rota-que-nao-existe"), 404)

    def test_405_mantem_o_allow(self, client):
        r = client.get(f"{API}/auth/login")
        _envelope(r, 405)
        assert "POST" in r.headers["allow"]

    def test_429_mantem_o_retry_after(self, client, user_locatario):
        for _ in range(RATE_LIMIT_FALHAS_CONTA):
            client.post(f"{API}/auth/login", json={"email": user_locatario.email, "senha": "senha-errada"})
        r = client.post(f"{API}/auth/login", json={"email": user_locatario.email, "senha": TEST_SENHA})
        _envelope(r, 429)
        assert int(r.headers["retry-after"]) > 0


class TestLimiteDeCorpo:
    def test_413(self, client, token_admin):
        r = client.post(
            f"{API}/imoveis",
            content=b"{}",
            headers={**auth(token_admin), "Content-Type": "application/json", "Content-Length": str(10**9)},
        )
        assert _envelope(r, 413)["erro"]

    def test_400_content_length_invalido(self, client, token_admin):
        r = client.post(
            f"{API}/imoveis",
            content=b"{}",
            headers={**auth(token_admin), "Content-Type": "application/json", "Content-Length": "abc"},
        )
        assert _envelope(r, 400)["erro"] == "Content-Length inválido"


class TestValidacaoDoCorpo:
    def test_422_traz_a_mensagem_por_campo(self, client):
        corpo = _envelope(client.post(f"{API}/auth/login", json={}), 422)
        assert set(corpo["erros"]) == {"email", "senha"}
        assert corpo["erro"] in corpo["erros"].values()

    def test_422_da_politica_de_senha_sem_o_prefixo_do_pydantic(self, client, token_locatario):
        r = client.put(
            f"{API}/usuarios/me/senha",
            json={"senha_atual": TEST_SENHA, "nova_senha": "curta"},
            headers=auth(token_locatario),
        )
        corpo = _envelope(r, 422)
        assert "pelo menos 10 caracteres" in corpo["erros"]["nova_senha"]
        assert not corpo["erro"].startswith("Value error")

    def test_422_de_parametro_de_consulta(self, client, token_admin):
        corpo = _envelope(client.get(f"{API}/logs?pagina=nao-e-numero", headers=auth(token_admin)), 422)
        assert "pagina" in corpo["erros"]


class _Corpo(BaseModel):
    status: int


@pytest.fixture
def app_isolada():
    """Uma aplicação só com os handlers, para os casos que a API real não tem rota para provocar."""
    app = FastAPI()
    registrar(app)

    @app.get("/quebra")
    def quebra():
        raise RuntimeError("segredo interno que não pode vazar")

    @app.get("/sem-corpo")
    def sem_corpo():
        raise HTTPException(status_code=304)

    @app.get("/detalhe-estruturado")
    def detalhe_estruturado():
        raise HTTPException(status_code=409, detail={"campo": "motivo"})

    @app.post("/mesmo-nome")
    def mesmo_nome(corpo: _Corpo, status: int = Query()):
        return {}

    return TestClient(app, raise_server_exceptions=False)


class TestCasosDosHandlers:
    def test_500_no_envelope_sem_expor_a_excecao(self, app_isolada):
        r = app_isolada.get("/quebra")
        corpo = _envelope(r, 500)
        assert "segredo" not in r.text and "RuntimeError" not in r.text
        assert corpo["erro"].startswith("Erro interno")

    def test_304_sem_corpo(self, app_isolada):
        r = app_isolada.get("/sem-corpo")
        assert r.status_code == 304 and r.content == b""

    def test_detalhe_estruturado_vai_para_erros(self, app_isolada):
        corpo = _envelope(app_isolada.get("/detalhe-estruturado"), 409)
        assert corpo["erros"] == {"campo": "motivo"}

    def test_mesmo_nome_na_consulta_e_no_corpo_nao_se_sobrepoe(self, app_isolada):
        corpo = _envelope(app_isolada.post("/mesmo-nome?status=x", json={"status": "y"}), 422)
        assert len(corpo["erros"]) == 2 and "status" in corpo["erros"]

    def test_json_invalido_vira_corpo(self, app_isolada):
        r = app_isolada.post(
            "/mesmo-nome?status=1", content=b"{nao-e-json", headers={"Content-Type": "application/json"}
        )
        assert "corpo" in _envelope(r, 422)["erros"]


class TestOpenapi:
    @pytest.fixture
    def openapi(self, client):
        return client.get("/openapi.json").json()

    def test_sem_os_formatos_antigos(self, openapi):
        schemas = set(openapi["components"]["schemas"])
        assert "DetalheErro" not in schemas
        assert "HTTPValidationError" not in schemas
        assert "ErroResposta" in schemas

    def test_todo_erro_documentado_e_o_envelope(self, openapi):
        for caminho, ops in openapi["paths"].items():
            for metodo, op in ops.items():
                for codigo, resposta in op.get("responses", {}).items():
                    if str(codigo)[0] in "45":
                        schema = resposta["content"]["application/json"]["schema"]
                        assert schema == {"$ref": "#/components/schemas/ErroResposta"}, (caminho, metodo, codigo)
