"""
DEBT-001 — Os corpos das rotas de problemas aparecem no OpenAPI

As três rotas leem o corpo à mão (JSON ou multipart, e só depois da autorização), então não ganhavam
requestBody no OpenAPI. Os modelos de app/schemas.py passam a documentá-lo, sem mudar a leitura nem as
mensagens de erro. Os valores aceitos vêm das mesmas constantes que as rotas usam.
"""

import pytest

from app.schemas import PRIORIDADES_PROBLEMA, STATUS_PROBLEMA
from tests.conftest import auth

API = "/api/v1"


@pytest.fixture
def paths(client):
    return client.get("/openapi.json").json()["paths"]


def _corpo(paths, caminho, metodo):
    corpo = paths[API + caminho][metodo]["requestBody"]
    assert corpo["required"] is True
    return corpo["content"]


def test_criar_problema_em_json_e_multipart(paths):
    conteudo = _corpo(paths, "/contratos/{contrato_id}/problemas", "post")
    json = conteudo["application/json"]["schema"]
    assert json["required"] == ["titulo"]
    assert json["properties"]["prioridade"]["enum"] == list(PRIORIDADES_PROBLEMA)
    assert json["properties"]["status"]["enum"] == ["aberto"]
    assert "foto_url" in json["properties"] and "foto" not in json["properties"]
    form = conteudo["multipart/form-data"]["schema"]
    assert form["properties"]["foto"]["format"] == "binary"
    assert "foto_url" not in form["properties"]


def test_mudar_status_em_json_com_os_status_aceitos(paths):
    conteudo = _corpo(paths, "/problemas/{problema_id}/status", "patch")
    assert set(conteudo) == {"application/json"}
    schema = conteudo["application/json"]["schema"]
    assert schema["required"] == ["status"]
    assert schema["properties"]["status"]["enum"] == list(STATUS_PROBLEMA)


def test_atualizacao_em_json_e_multipart(paths):
    conteudo = _corpo(paths, "/problemas/{problema_id}/atualizacoes", "post")
    assert conteudo["application/json"]["schema"]["required"] == ["descricao"]
    form = conteudo["multipart/form-data"]["schema"]
    assert form["required"] == ["descricao"]
    assert form["properties"]["foto"]["format"] == "binary"


@pytest.mark.parametrize("status", STATUS_PROBLEMA)
def test_cada_status_documentado_e_aceito(client, db, contrato, token_gestor, status):
    from app.models import Problema

    pb = Problema(contrato_id=contrato.id, titulo="Infiltração")
    db.add(pb)
    db.flush()
    r = client.patch(f"{API}/problemas/{pb.id}/status", json={"status": status}, headers=auth(token_gestor))
    assert r.status_code == 200, r.text


def test_status_fora_do_documentado_continua_422_com_a_mensagem_de_campo(client, db, contrato, token_gestor):
    from app.models import Problema

    pb = Problema(contrato_id=contrato.id, titulo="Infiltração")
    db.add(pb)
    db.flush()
    r = client.patch(f"{API}/problemas/{pb.id}/status", json={"status": "pendente"}, headers=auth(token_gestor))
    assert r.status_code == 422
    assert r.json()["erros"] == {"status": "Status inválido"}
    db.expire_all()
    assert db.get(Problema, pb.id).status == "aberto"


@pytest.mark.parametrize("prioridade", PRIORIDADES_PROBLEMA)
def test_cada_prioridade_documentada_e_aceita(client, contrato, token_gestor, prioridade):
    r = client.post(
        f"{API}/contratos/{contrato.id}/problemas",
        json={"titulo": "Vazamento", "prioridade": prioridade},
        headers=auth(token_gestor),
    )
    assert r.status_code in (200, 201), r.text
    assert r.json()["dados"]["prioridade"] == prioridade


@pytest.mark.parametrize("corpo", ["null", "[]", '"aberto"', '{"status": 1}', '{"status": null}'])
def test_corpo_fora_do_formato_no_status_e_422_e_nao_500(client, db, contrato, token_gestor, corpo):
    from app.models import Problema

    pb = Problema(contrato_id=contrato.id, titulo="Infiltração")
    db.add(pb)
    db.flush()
    r = client.patch(
        f"{API}/problemas/{pb.id}/status",
        content=corpo,
        headers={**auth(token_gestor), "Content-Type": "application/json"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["erros"] == {"status": "Status inválido"}


@pytest.mark.parametrize("corpo", ["null", "[]", "5"])
def test_corpo_que_nao_e_objeto_na_criacao_e_na_atualizacao_e_422(client, db, contrato, token_gestor, corpo):
    from app.models import Problema

    cabecalhos = {**auth(token_gestor), "Content-Type": "application/json"}
    criar = client.post(f"{API}/contratos/{contrato.id}/problemas", content=corpo, headers=cabecalhos)
    assert criar.status_code == 422, criar.text

    pb = Problema(contrato_id=contrato.id, titulo="Infiltração")
    db.add(pb)
    db.flush()
    comentar = client.post(f"{API}/problemas/{pb.id}/atualizacoes", content=corpo, headers=cabecalhos)
    assert comentar.status_code == 422, comentar.text
    assert "descricao" in comentar.json()["erros"]


def test_descricao_da_atualizacao_publica_o_minimo(paths):
    for tipo in ("application/json", "multipart/form-data"):
        schema = _corpo(paths, "/problemas/{problema_id}/atualizacoes", "post")[tipo]["schema"]
        assert schema["properties"]["descricao"]["minLength"] == 5


def test_modelo_aninhado_e_recusado_pelo_helper():
    from pydantic import BaseModel

    from app.schemas import corpo_no_openapi

    class Item(BaseModel):
        nome: str

    class Corpo(BaseModel):
        itens: list[Item]

    with pytest.raises(ValueError, match="aninhado"):
        corpo_no_openapi(Corpo)
