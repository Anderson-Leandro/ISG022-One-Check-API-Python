"""
DEBT-016 — Os tipos de agendamento (inicial, encerramento) aparecem no OpenAPI (ADR-0012, item 11)

A validação continua nas rotas, com a mesma mensagem de campo; o schema passa a declarar o enum para quem
integra ver os valores aceitos.
"""
import pytest

from tests.conftest import auth

API = "/api/v1"
TIPOS = ["inicial", "encerramento"]
MENSAGEM = "Tipo inválido. Deve ser 'inicial' ou 'encerramento'"


def _schema(client, nome):
    return client.app.openapi()["components"]["schemas"][nome]["properties"]["tipo"]


def test_criacao_declara_o_enum(client):
    assert _schema(client, "AgendamentoCreate")["enum"] == TIPOS


def test_alteracao_declara_o_enum_e_aceita_nulo(client):
    tipo = _schema(client, "AgendamentoUpdate")
    opcoes = tipo["anyOf"]
    assert {"type": "null"} in opcoes
    assert [o for o in opcoes if o.get("type") == "string"][0]["enum"] == TIPOS


@pytest.mark.parametrize("acao", ["criar", "alterar"])
def test_tipo_fora_do_enum_continua_422_com_mensagem_de_campo(client, db, contrato, token_admin, acao):
    from app.models import AgendamentoVistoria
    if acao == "criar":
        r = client.post(f"{API}/contratos/{contrato.id}/agendamentos", headers=auth(token_admin),
                        json={"tipo": "periodica", "data_agendada": "2099-01-01T10:00:00"})
    else:
        ag = db.query(AgendamentoVistoria).filter(AgendamentoVistoria.contrato_id == contrato.id).first()
        assert ag is not None
        tipo_antes = ag.tipo
        r = client.put(f"{API}/agendamentos/{ag.id}", headers=auth(token_admin), json={"tipo": "periodica"})
        db.expire_all()
        assert db.get(AgendamentoVistoria, ag.id).tipo == tipo_antes
    assert r.status_code == 422, r.text
    assert r.json()["erros"] == {"tipo": MENSAGEM}
