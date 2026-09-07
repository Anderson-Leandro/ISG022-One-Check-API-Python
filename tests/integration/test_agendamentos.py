"""
Testes de integração das rotas de Agendamentos de Vistoria (Etapa 6)

Rotas cobertas:
  POST   /api/v1/contratos/{id}/agendamentos
  GET    /api/v1/contratos/{id}/agendamentos
  PUT    /api/v1/agendamentos/{id}
  DELETE /api/v1/agendamentos/{id}
"""
from datetime import datetime, timedelta

from tests.conftest import auth

BASE_CONTRATOS = "/api/v1/contratos"
BASE_AGENDAMENTOS = "/api/v1/agendamentos"


def _data_futura(dias: int = 30) -> str:
    return (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")


def _data_passada(dias: int = 2) -> str:
    return (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")


class TestCriarAgendamento:
    def test_admin_cria_agendamento_valido(self, client, contrato, token_admin):
        r = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/agendamentos",
            json={
                "tipo": "inicial",
                "data_agendada": _data_futura(15),
                "observacao": "Primeira vistoria do imóvel",
            },
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["contrato_id"] == contrato.id
        assert data["dados"]["tipo"] == "inicial"
        assert data["dados"]["observacao"] == "Primeira vistoria do imóvel"

    def test_admin_cria_agendamento_sem_observacao(self, client, contrato, token_admin):
        r = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/agendamentos",
            json={
                "tipo": "encerramento",
                "data_agendada": _data_futura(60),
            },
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["tipo"] == "encerramento"
        assert data["dados"]["observacao"] is None

    def test_tipo_invalido_retorna_falha(self, client, contrato, token_admin):
        r = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/agendamentos",
            json={
                "tipo": "periodica",
                "data_agendada": _data_futura(10),
            },
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is False
        assert "tipo" in data["erro"].lower()

    def test_data_no_passado_retorna_falha(self, client, contrato, token_admin):
        r = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/agendamentos",
            json={
                "tipo": "inicial",
                "data_agendada": _data_passada(5),
            },
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is False
        assert "futura" in data["erro"].lower()

    def test_contrato_inexistente_retorna_falha(self, client, token_admin):
        r = client.post(
            f"{BASE_CONTRATOS}/00000000-0000-0000-0000-000000000000/agendamentos",
            json={
                "tipo": "inicial",
                "data_agendada": _data_futura(10),
            },
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is False

    def test_vistoriador_e_locatario_nao_podem_criar_agendamento(self, client, contrato, token_vistoriador, token_locatario):
        r_vist = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/agendamentos",
            json={"tipo": "inicial", "data_agendada": _data_futura(10)},
            headers=auth(token_vistoriador),
        )
        assert r_vist.status_code == 403

        r_loc = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/agendamentos",
            json={"tipo": "inicial", "data_agendada": _data_futura(10)},
            headers=auth(token_locatario),
        )
        assert r_loc.status_code == 403


class TestListarAgendamentos:
    def test_admin_e_vistoriador_listam_agendamentos(self, client, contrato, token_admin, token_vistoriador):
        r_admin = client.get(f"{BASE_CONTRATOS}/{contrato.id}/agendamentos", headers=auth(token_admin))
        assert r_admin.status_code == 200
        assert r_admin.json()["sucesso"] is True

        r_vist = client.get(f"{BASE_CONTRATOS}/{contrato.id}/agendamentos", headers=auth(token_vistoriador))
        assert r_vist.status_code == 200
        assert r_vist.json()["sucesso"] is True

    def test_locatario_nao_pode_listar_agendamentos(self, client, contrato, token_locatario):
        r = client.get(f"{BASE_CONTRATOS}/{contrato.id}/agendamentos", headers=auth(token_locatario))
        assert r.status_code == 403

    def test_contrato_inexistente_retorna_falha(self, client, token_admin):
        r = client.get(f"{BASE_CONTRATOS}/00000000-0000-0000-0000-000000000000/agendamentos", headers=auth(token_admin))
        assert r.json()["sucesso"] is False


class TestAtualizarEExcluirAgendamento:
    def test_admin_atualiza_agendamento(self, client, db, contrato, token_admin):
        from app.models import AgendamentoVistoria
        ag = AgendamentoVistoria(
            contrato_id=contrato.id,
            tipo="inicial",
            data_agendada=datetime.now() + timedelta(days=5),
            observacao="Antiga",
        )
        db.add(ag)
        db.commit()

        r = client.put(
            f"{BASE_AGENDAMENTOS}/{ag.id}",
            json={
                "tipo": "encerramento",
                "data_agendada": _data_futura(45),
                "observacao": "Nova observacao",
            },
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["tipo"] == "encerramento"
        assert data["dados"]["observacao"] == "Nova observacao"

    def test_atualizar_com_data_passada_retorna_falha(self, client, db, contrato, token_admin):
        from app.models import AgendamentoVistoria
        ag = AgendamentoVistoria(
            contrato_id=contrato.id,
            tipo="inicial",
            data_agendada=datetime.now() + timedelta(days=5),
        )
        db.add(ag)
        db.commit()

        r = client.put(
            f"{BASE_AGENDAMENTOS}/{ag.id}",
            json={"data_agendada": _data_passada(2)},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is False
        assert "futura" in data["erro"].lower()

    def test_admin_exclui_agendamento(self, client, db, contrato, token_admin):
        from app.models import AgendamentoVistoria
        ag = AgendamentoVistoria(
            contrato_id=contrato.id,
            tipo="inicial",
            data_agendada=datetime.now() + timedelta(days=5),
        )
        db.add(ag)
        db.commit()

        r = client.delete(f"{BASE_AGENDAMENTOS}/{ag.id}", headers=auth(token_admin))
        assert r.status_code == 200
        assert r.json()["sucesso"] is True

        # Verificar se foi removido
        assert db.query(AgendamentoVistoria).filter(AgendamentoVistoria.id == ag.id).first() is None

    def test_excluir_agendamento_inexistente(self, client, token_admin):
        r = client.delete(f"{BASE_AGENDAMENTOS}/00000000-0000-0000-0000-000000000000", headers=auth(token_admin))
        assert r.json()["sucesso"] is False

    def test_vistoriador_nao_pode_excluir_nem_atualizar(self, client, db, contrato, token_vistoriador):
        from app.models import AgendamentoVistoria
        ag = AgendamentoVistoria(
            contrato_id=contrato.id,
            tipo="inicial",
            data_agendada=datetime.now() + timedelta(days=5),
        )
        db.add(ag)
        db.commit()

        r_put = client.put(
            f"{BASE_AGENDAMENTOS}/{ag.id}",
            json={"tipo": "encerramento"},
            headers=auth(token_vistoriador),
        )
        assert r_put.status_code == 403

        r_del = client.delete(f"{BASE_AGENDAMENTOS}/{ag.id}", headers=auth(token_vistoriador))
        assert r_del.status_code == 403
