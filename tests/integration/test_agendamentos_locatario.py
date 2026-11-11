"""
US-018 — O locatário vê os agendamentos do próprio contrato (ADR-0012, item 5)

GET /contratos/{id}/agendamentos passa a seguir assert_acesso_contrato: o locatário lê os do próprio
contrato e recebe 403 nos dos outros. Criar, alterar e excluir continuam só com admin e gestor. O dashboard
conta os agendamentos com o mesmo recorte.
"""

from datetime import date

import pytest

from app.models import AgendamentoVistoria, Contrato, Imovel
from tests.conftest import auth, foto_do_banco

API = "/api/v1"


@pytest.fixture
def contrato_alheio(db, user_locatario_2):
    im = Imovel(tipo="casa", status="locado", garagem=False, garagem_vagas=0)
    db.add(im)
    db.flush()
    ct = Contrato(
        imovel_id=im.id,
        locatario_id=user_locatario_2.id,
        data_inicio=date(2025, 1, 1),
        data_fim=date(2025, 12, 31),
        status="ativo",
    )
    db.add(ct)
    db.flush()
    db.add(AgendamentoVistoria(contrato_id=ct.id, tipo="inicial", data_agendada=date(2025, 1, 1)))
    db.flush()
    return ct


def test_locatario_lista_os_agendamentos_do_proprio_contrato(client, db, contrato, token_locatario):
    esperados = {a.id for a in db.query(AgendamentoVistoria).filter(AgendamentoVistoria.contrato_id == contrato.id)}

    r = client.get(f"{API}/contratos/{contrato.id}/agendamentos", headers=auth(token_locatario))

    assert r.status_code == 200, r.text
    assert {a["id"] for a in r.json()["dados"]} == esperados
    assert len(esperados) == 2


def test_locatario_nao_ve_a_observacao_interna(client, db, contrato, token_locatario, token_gestor):
    ag = db.query(AgendamentoVistoria).filter(AgendamentoVistoria.contrato_id == contrato.id).first()
    ag.observacao = "Nota interna da equipe"
    db.flush()

    do_locatario = client.get(f"{API}/contratos/{contrato.id}/agendamentos", headers=auth(token_locatario)).json()[
        "dados"
    ]
    do_gestor = client.get(f"{API}/contratos/{contrato.id}/agendamentos", headers=auth(token_gestor)).json()["dados"]

    assert all("observacao" not in a for a in do_locatario)
    assert {"tipo", "data_agendada"} <= set(do_locatario[0])
    assert "Nota interna da equipe" in [a["observacao"] for a in do_gestor]


def test_locatario_nao_lista_os_de_outro_contrato(client, contrato_alheio, token_locatario):
    r = client.get(f"{API}/contratos/{contrato_alheio.id}/agendamentos", headers=auth(token_locatario))

    assert r.status_code == 403, r.text
    assert r.json()["erro"] == "Você não tem acesso a este contrato"
    assert "dados" not in r.json()


@pytest.mark.parametrize("acao", ["criar", "alterar", "excluir"])
def test_locatario_continua_sem_escrita(client, db, contrato, token_locatario, acao):
    ag = db.query(AgendamentoVistoria).filter(AgendamentoVistoria.contrato_id == contrato.id).first()
    antes = foto_do_banco(db)
    if acao == "criar":
        r = client.post(
            f"{API}/contratos/{contrato.id}/agendamentos",
            headers=auth(token_locatario),
            json={"tipo": "encerramento", "data_agendada": "2099-01-01T10:00:00"},
        )
    elif acao == "alterar":
        r = client.put(f"{API}/agendamentos/{ag.id}", headers=auth(token_locatario), json={"observacao": "x"})
    else:
        r = client.delete(f"{API}/agendamentos/{ag.id}", headers=auth(token_locatario))
    assert r.status_code == 403, r.text
    assert foto_do_banco(db) == antes


def test_dashboard_do_locatario_conta_so_os_proprios(client, contrato, contrato_alheio, token_locatario, token_admin):
    assert client.get(f"{API}/dashboard", headers=auth(token_locatario)).json()["dados"]["vistorias_agendadas"] == 2
    assert client.get(f"{API}/dashboard", headers=auth(token_admin)).json()["dados"]["vistorias_agendadas"] == 3
