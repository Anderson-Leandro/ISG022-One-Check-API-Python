"""
US-015 — Exclusão lógica de checklist, contrato e problema criados por engano (ADR-0008)

Rotas:
  DELETE /api/v1/checklists/{id}   só em preenchimento
  DELETE /api/v1/contratos/{id}    só sem checklist nem problema
  DELETE /api/v1/problemas/{id}    só aberto e sem atualizações

Admin e gestor excluem; vistoriador e locatário recebem 403 (coberto também por
test_seguranca_negacao_por_perfil.py). O registro some das leituras, continua no banco com quem e quando
excluiu, e a exclusão fica no log.
"""

import pytest
from sqlalchemy import select

from app.models import (
    AgendamentoVistoria,
    AtualizacaoProblema,
    Checklist,
    Contrato,
    Imovel,
    LogOperacao,
    Problema,
)
from tests.conftest import auth, foto_do_banco

API = "/api/v1"


@pytest.fixture
def problema(db, contrato):
    pb = Problema(contrato_id=contrato.id, titulo="Infiltração")
    db.add(pb)
    db.flush()
    return pb


def _linha_no_banco(db, modelo, id_):
    """Lê direto da tabela, por fora do filtro de exclusão do ORM."""
    tabela = modelo.__table__
    return db.connection().execute(select(tabela).where(tabela.c.id == id_)).mappings().one()


def _log_de_exclusao(db, entidade, id_):
    db.expire_all()
    return (
        db.query(LogOperacao)
        .filter(LogOperacao.acao == "delete", LogOperacao.entidade == entidade, LogOperacao.entidade_id == id_)
        .all()
    )


def _confere_excluido(db, modelo, entidade, id_, quem):
    linha = _linha_no_banco(db, modelo, id_)
    assert linha["excluido_em"] is not None
    assert linha["excluido_por"] == quem.id
    assert [log.usuario_id for log in _log_de_exclusao(db, entidade, id_)] == [quem.id]


# ── Checklist ───────────────────────────────────────────────────────────────────


class TestExcluirChecklist:
    @pytest.mark.parametrize("perfil", ["admin", "gestor"])
    def test_em_preenchimento_some_das_leituras_e_fica_no_log(
        self, client, db, contrato, checklist, user_admin, user_gestor, token_admin, token_gestor, perfil
    ):
        quem, token = (user_admin, token_admin) if perfil == "admin" else (user_gestor, token_gestor)

        r = client.delete(f"{API}/checklists/{checklist.id}", headers=auth(token))

        assert r.status_code == 200, r.text
        assert r.json() == {"sucesso": True, "dados": None}
        assert client.get(f"{API}/checklists/{checklist.id}", headers=auth(token_admin)).status_code == 404
        listagem = client.get(f"{API}/contratos/{contrato.id}/checklists", headers=auth(token_admin))
        assert listagem.json()["dados"] == []
        _confere_excluido(db, Checklist, "checklist", checklist.id, quem)

    @pytest.mark.parametrize("status", ["pendente_aceite", "aceito", "rejeitado"])
    def test_depois_do_envio_e_recusado(self, client, db, checklist, token_admin, status):
        checklist.status = status
        db.flush()
        antes = foto_do_banco(db)

        r = client.delete(f"{API}/checklists/{checklist.id}", headers=auth(token_admin))

        assert r.status_code == 409, r.text
        assert r.json()["erro"] == f"Não é possível excluir um checklist com status '{status}'"
        assert foto_do_banco(db) == antes

    def test_excluido_nao_pode_ser_excluido_de_novo(self, client, checklist, token_admin):
        assert client.delete(f"{API}/checklists/{checklist.id}", headers=auth(token_admin)).status_code == 200
        r = client.delete(f"{API}/checklists/{checklist.id}", headers=auth(token_admin))
        assert r.status_code == 404
        assert r.json()["erro"] == "Checklist não encontrado"

    def test_vistoriador_nao_altera_checklist_excluido(self, client, db, checklist, token_admin, token_vistoriador):
        client.delete(f"{API}/checklists/{checklist.id}", headers=auth(token_admin))
        r = client.patch(f"{API}/checklists/{checklist.id}/submeter", headers=auth(token_vistoriador))
        assert r.status_code == 404


# ── Contrato ────────────────────────────────────────────────────────────────────


class TestExcluirContrato:
    def test_sem_checklist_nem_problema_some_e_libera_o_imovel(
        self, client, db, contrato, imovel, user_gestor, token_gestor, token_admin
    ):
        assert db.query(AgendamentoVistoria).filter(AgendamentoVistoria.contrato_id == contrato.id).count() == 2

        r = client.delete(f"{API}/contratos/{contrato.id}", headers=auth(token_gestor))

        assert r.status_code == 200, r.text
        assert client.get(f"{API}/contratos/{contrato.id}", headers=auth(token_admin)).status_code == 404
        ids = [c["id"] for c in client.get(f"{API}/contratos", headers=auth(token_admin)).json()["dados"]]
        assert contrato.id not in ids
        _confere_excluido(db, Contrato, "contrato", contrato.id, user_gestor)
        # O imóvel do contrato ativo volta a ficar disponível; os agendamentos somem com o contrato
        assert db.get(Imovel, imovel.id).status == "disponivel"
        assert db.query(AgendamentoVistoria).filter(AgendamentoVistoria.contrato_id == contrato.id).count() == 0
        assert client.get("/api/v1/dashboard", headers=auth(token_admin)).json()["dados"]["vistorias_agendadas"] == 0

    def test_com_checklist_e_recusado(self, client, db, contrato, checklist, token_admin):
        antes = foto_do_banco(db)
        r = client.delete(f"{API}/contratos/{contrato.id}", headers=auth(token_admin))
        assert r.status_code == 409, r.text
        assert r.json()["erro"] == "Exclua antes os checklists deste contrato"
        assert foto_do_banco(db) == antes

    def test_com_problema_e_recusado(self, client, db, contrato, problema, token_admin):
        antes = foto_do_banco(db)
        r = client.delete(f"{API}/contratos/{contrato.id}", headers=auth(token_admin))
        assert r.status_code == 409, r.text
        assert r.json()["erro"] == "Exclua antes os problemas deste contrato"
        assert foto_do_banco(db) == antes

    def test_depois_de_excluir_o_checklist_o_contrato_pode_ser_excluido(self, client, contrato, checklist, token_admin):
        assert client.delete(f"{API}/checklists/{checklist.id}", headers=auth(token_admin)).status_code == 200
        assert client.delete(f"{API}/contratos/{contrato.id}", headers=auth(token_admin)).status_code == 200

    def test_encerrado_nao_muda_o_imovel(self, client, db, contrato, imovel, token_admin):
        contrato.status = "encerrado"
        imovel.status = "em_manutencao"
        db.flush()
        assert client.delete(f"{API}/contratos/{contrato.id}", headers=auth(token_admin)).status_code == 200
        db.expire_all()
        assert db.get(Imovel, imovel.id).status == "em_manutencao"


# ── Problema ────────────────────────────────────────────────────────────────────


class TestExcluirProblema:
    def test_sem_atualizacoes_some_das_leituras(self, client, db, contrato, problema, user_admin, token_admin):
        r = client.delete(f"{API}/problemas/{problema.id}", headers=auth(token_admin))

        assert r.status_code == 200, r.text
        assert client.get(f"{API}/problemas/{problema.id}", headers=auth(token_admin)).status_code == 404
        assert client.get(f"{API}/contratos/{contrato.id}/problemas", headers=auth(token_admin)).json()["dados"] == []
        _confere_excluido(db, Problema, "problema", problema.id, user_admin)

    @pytest.mark.parametrize("status", ["em_andamento", "resolvido"])
    def test_ja_em_tratamento_e_recusado(self, client, db, problema, token_admin, status):
        problema.status = status
        db.flush()
        antes = foto_do_banco(db)

        r = client.delete(f"{API}/problemas/{problema.id}", headers=auth(token_admin))

        assert r.status_code == 409, r.text
        assert r.json()["erro"] == f"Não é possível excluir um problema com status '{status}'"
        assert foto_do_banco(db) == antes

    def test_com_atualizacao_e_recusado(self, client, db, problema, user_admin, token_admin):
        db.add(AtualizacaoProblema(problema_id=problema.id, autor_id=user_admin.id, descricao="Técnico agendado"))
        db.flush()
        antes = foto_do_banco(db)

        r = client.delete(f"{API}/problemas/{problema.id}", headers=auth(token_admin))

        assert r.status_code == 409, r.text
        assert r.json()["erro"] == "Não é possível excluir um problema que já tem atualizações"
        assert foto_do_banco(db) == antes


# ── Perfis sem permissão ────────────────────────────────────────────────────────


@pytest.mark.parametrize("rota", ["checklists/{checklist}", "contratos/{contrato}", "problemas/{problema}"])
@pytest.mark.parametrize("perfil", ["vistoriador", "locatario"])
def test_perfil_sem_permissao_recebe_403(
    client, db, contrato, checklist, problema, token_vistoriador, token_locatario, rota, perfil
):
    tokens = {"vistoriador": token_vistoriador, "locatario": token_locatario}
    antes = foto_do_banco(db)
    caminho = rota.format(checklist=checklist.id, contrato=contrato.id, problema=problema.id)

    r = client.delete(f"{API}/{caminho}", headers=auth(tokens[perfil]))

    assert r.status_code == 403, r.text
    assert foto_do_banco(db) == antes
