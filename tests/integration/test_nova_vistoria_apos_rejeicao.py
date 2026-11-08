"""
US-020 — Nova vistoria depois de uma rejeição, e fim do status pendente_revisao (ADR-0012, item 8)

A vistoria rejeitada é evidência e não muda (R-003). Antes, uma vistoria inicial rejeitada travava o
contrato: criar outra inicial dava 409, e a exclusão (ADR-0008) não aceita vistoria rejeitada. Agora uma
nova inicial pode ser criada quando todas as anteriores foram rejeitadas.
"""
import pytest

from app.models import Checklist
from tests.conftest import auth, foto_do_banco

API = "/api/v1"


def _criar_inicial(client, contrato_id, vistoriador_id, token):
    return client.post(f"{API}/contratos/{contrato_id}/checklists", headers=auth(token),
                       json={"tipo": "inicial", "vistoriador_id": vistoriador_id})


def test_nova_inicial_depois_de_rejeitada(client, db, contrato, checklist, user_vistoriador, token_gestor):
    checklist.status = "rejeitado"
    db.flush()
    rejeitada = (checklist.id, checklist.status, checklist.vistoriador_id)

    r = _criar_inicial(client, contrato.id, user_vistoriador.id, token_gestor)

    assert r.status_code == 200, r.text
    nova = r.json()["dados"]
    assert (nova["tipo"], nova["status"]) == ("inicial", "em_preenchimento")
    assert nova["id"] != checklist.id
    db.expire_all()
    antiga = db.get(Checklist, checklist.id)
    assert (antiga.id, antiga.status, antiga.vistoriador_id) == rejeitada


@pytest.mark.parametrize("status", ["em_preenchimento", "pendente_aceite", "aceito"])
def test_inicial_que_nao_foi_rejeitada_continua_bloqueando(client, db, contrato, checklist, user_vistoriador,
                                                          token_gestor, status):
    checklist.status = status
    db.flush()
    antes = foto_do_banco(db)

    r = _criar_inicial(client, contrato.id, user_vistoriador.id, token_gestor)

    assert r.status_code == 409, r.text
    assert r.json()["erro"] == "Este contrato já possui vistoria inicial"
    assert foto_do_banco(db) == antes


def test_rejeitada_mais_uma_em_andamento_bloqueia(client, db, contrato, checklist, user_vistoriador, token_gestor):
    checklist.status = "rejeitado"
    db.flush()
    assert _criar_inicial(client, contrato.id, user_vistoriador.id, token_gestor).status_code == 200
    r = _criar_inicial(client, contrato.id, user_vistoriador.id, token_gestor)
    assert r.status_code == 409, r.text


def test_pendente_revisao_saiu_do_dominio(db, checklist):
    from app.data_status import get_data_status
    assert get_data_status(db)["checklists_por_status"] == {
        "em_preenchimento": 1, "pendente_aceite": 0, "aceito": 0, "rejeitado": 0,
    }


def test_status_antigo_aparece_na_contagem_e_nao_trava_o_contrato(client, db, contrato, checklist, user_vistoriador,
                                                                  token_gestor):
    """Um valor antigo gravado direto no banco não some da contagem nem bloqueia uma nova vistoria inicial."""
    from app.data_status import get_data_status
    checklist.status = "pendente_revisao"
    db.flush()
    assert get_data_status(db)["checklists_por_status"]["pendente_revisao"] == 1
    assert _criar_inicial(client, contrato.id, user_vistoriador.id, token_gestor).status_code == 200


def test_dashboard_conta_so_pendente_aceite(client, db, checklist, token_admin):
    checklist.status = "pendente_aceite"
    db.flush()
    assert client.get(f"{API}/dashboard", headers=auth(token_admin)).json()["dados"]["checklists_pendentes"] == 1
    checklist.status = "pendente_revisao"  # valor antigo, gravado direto no banco: não conta mais
    db.flush()
    assert client.get(f"{API}/dashboard", headers=auth(token_admin)).json()["dados"]["checklists_pendentes"] == 0
