"""
Fase 2.4 — Testes de integração das rotas de contratos

Rotas cobertas:
  GET  /api/v1/contratos
  POST /api/v1/contratos
  GET  /api/v1/contratos/{id}/agendamentos
  GET  /api/v1/contratos/{id}/checklists
  POST /api/v1/contratos/{id}/checklists
  POST /api/v1/contratos/{id}/problemas
  GET  /api/v1/contratos/{id}/problemas
"""
from datetime import date

from tests.conftest import auth

BASE = "/api/v1/contratos"


# ── GET /contratos ────────────────────────────────────────────────────────────────

class TestListContratos:
    def test_admin_lista_todos(self, client, contrato, token_admin):
        r = client.get(BASE, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert any(c["id"] == contrato.id for c in data["dados"])

    def test_paginacao_presente(self, client, contrato, token_admin):
        r = client.get(BASE, headers=auth(token_admin))
        assert "paginacao" in r.json()

    def test_filtra_por_status(self, client, contrato, token_admin):
        r = client.get(f"{BASE}?status=ativo", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        for c in data["dados"]:
            assert c["status"] == "ativo"

    def test_locatario_ve_apenas_seus_contratos(self, client, contrato, token_locatario):
        r = client.get(BASE, headers=auth(token_locatario))
        data = r.json()
        assert data["sucesso"] is True
        for c in data["dados"]:
            assert c["locatario_id"] == contrato.locatario_id

    def test_vistoriador_ve_contratos_com_seus_checklists(self, client, checklist, token_vistoriador):
        r = client.get(BASE, headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is True
        assert len(data["dados"]) >= 1

    def test_sem_autenticacao_retorna_401(self, client):
        r = client.get(BASE)
        assert r.status_code == 401


# ── POST /contratos ───────────────────────────────────────────────────────────────

class TestCreateContrato:
    def test_cria_contrato_valido(self, client, imovel, user_locatario, token_admin):
        r = client.post(BASE, json={
            "imovel_id": imovel.id,
            "locatario_id": user_locatario.id,
            "data_inicio": "2025-01-01",
            "data_fim": "2025-12-31",
            "valor_mensal": 1800.00,
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["imovel_id"] == imovel.id
        assert data["dados"]["status"] == "ativo"

    def test_criacao_marca_imovel_como_locado(self, client, db, imovel, user_locatario, token_admin):
        from app.models import Imovel
        client.post(BASE, json={
            "imovel_id": imovel.id,
            "locatario_id": user_locatario.id,
            "data_inicio": "2025-01-01",
            "data_fim": "2025-12-31",
        }, headers=auth(token_admin))
        db.expire(imovel)
        assert imovel.status == "locado"

    def test_criacao_gera_agendamentos(self, client, db, imovel, user_locatario, token_admin):
        from app.models import AgendamentoVistoria, Contrato
        r = client.post(BASE, json={
            "imovel_id": imovel.id,
            "locatario_id": user_locatario.id,
            "data_inicio": "2025-01-01",
            "data_fim": "2025-12-31",
        }, headers=auth(token_admin))
        ct_id = r.json()["dados"]["id"]
        ags = db.query(AgendamentoVistoria).filter(AgendamentoVistoria.contrato_id == ct_id).all()
        tipos = {a.tipo for a in ags}
        assert tipos == {"inicial", "encerramento"}

    def test_imovel_inexistente_retorna_falha(self, client, user_locatario, token_admin):
        r = client.post(BASE, json={
            "imovel_id": "id-invalido",
            "locatario_id": user_locatario.id,
            "data_inicio": "2025-01-01",
            "data_fim": "2025-12-31",
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "encontrado" in data["erro"].lower()

    def test_imovel_ja_locado_retorna_falha(self, client, contrato, user_locatario, token_admin):
        # contrato fixture deixa o imovel como "locado"
        r = client.post(BASE, json={
            "imovel_id": contrato.imovel_id,
            "locatario_id": user_locatario.id,
            "data_inicio": "2026-01-01",
            "data_fim": "2026-12-31",
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "locado" in data["erro"].lower()

    def test_sem_autenticacao_retorna_401(self, client, imovel, user_locatario):
        r = client.post(BASE, json={
            "imovel_id": imovel.id,
            "locatario_id": user_locatario.id,
            "data_inicio": "2025-01-01",
            "data_fim": "2025-12-31",
        })
        assert r.status_code == 401


# ── GET /contratos/{id}/agendamentos ─────────────────────────────────────────────

class TestListAgendamentos:
    def test_lista_agendamentos_do_contrato(self, client, contrato, token_admin):
        r = client.get(f"{BASE}/{contrato.id}/agendamentos", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert len(data["dados"]) == 2
        tipos = {a["tipo"] for a in data["dados"]}
        assert tipos == {"inicial", "encerramento"}

    def test_campos_do_agendamento(self, client, contrato, token_admin):
        r = client.get(f"{BASE}/{contrato.id}/agendamentos", headers=auth(token_admin))
        ag = r.json()["dados"][0]
        assert "id" in ag
        assert "tipo" in ag
        assert "data_agendada" in ag
        assert "observacao" in ag

    def test_sem_autenticacao_retorna_401(self, client, contrato):
        r = client.get(f"{BASE}/{contrato.id}/agendamentos")
        assert r.status_code == 401


# ── GET /contratos/{id}/checklists ────────────────────────────────────────────────

class TestListChecklists:
    def test_lista_checklists_do_contrato(self, client, checklist, contrato, token_admin):
        r = client.get(f"{BASE}/{contrato.id}/checklists", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert any(c["id"] == checklist.id for c in data["dados"])

    def test_contrato_inexistente_retorna_falha(self, client, token_admin):
        r = client.get(f"{BASE}/id-invalido/checklists", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False

    def test_locatario_ve_checklists_do_seu_contrato(self, client, checklist, contrato, token_locatario):
        r = client.get(f"{BASE}/{contrato.id}/checklists", headers=auth(token_locatario))
        data = r.json()
        assert data["sucesso"] is True

    def test_locatario_nao_ve_checklist_de_contrato_alheio(self, client, db, checklist, token_locatario):
        from app.models import Contrato, Imovel, Usuario
        from tests.conftest import _SENHA_HASH
        outro_loc = Usuario(nome="Outro", email="outro@t.com", senha_hash=_SENHA_HASH,
                           role="locatario", mfa_enabled=False, ativo=True)
        db.add(outro_loc)
        db.flush()
        outro_imovel = Imovel(tipo="casa", status="disponivel", garagem=False, garagem_vagas=0)
        db.add(outro_imovel)
        db.flush()
        outro_ct = Contrato(imovel_id=outro_imovel.id, locatario_id=outro_loc.id,
                           data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31), status="ativo")
        db.add(outro_ct)
        db.flush()

        r = client.get(f"{BASE}/{outro_ct.id}/checklists", headers=auth(token_locatario))
        data = r.json()
        assert data["sucesso"] is False
        assert "permissão" in data["erro"].lower()

    def test_sem_autenticacao_retorna_401(self, client, contrato):
        r = client.get(f"{BASE}/{contrato.id}/checklists")
        assert r.status_code == 401


# ── POST /contratos/{id}/checklists ───────────────────────────────────────────────

class TestCreateChecklist:
    def test_cria_checklist_inicial(self, client, contrato, user_vistoriador, token_admin):
        r = client.post(f"{BASE}/{contrato.id}/checklists", json={
            "tipo": "inicial",
            "vistoriador_id": user_vistoriador.id,
            "data_vistoria": str(date.today()),
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["tipo"] == "inicial"
        assert data["dados"]["status"] == "em_preenchimento"

    def test_nao_permite_duplicar_checklist_inicial(self, client, checklist, contrato, user_vistoriador, token_admin):
        # checklist fixture já criou um "inicial"
        r = client.post(f"{BASE}/{contrato.id}/checklists", json={
            "tipo": "inicial",
            "vistoriador_id": user_vistoriador.id,
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "inicial" in data["erro"].lower()

    def test_cria_checklist_encerramento(self, client, contrato, user_vistoriador, token_admin):
        r = client.post(f"{BASE}/{contrato.id}/checklists", json={
            "tipo": "encerramento",
            "vistoriador_id": user_vistoriador.id,
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["tipo"] == "encerramento"

    def test_tipo_invalido_retorna_falha(self, client, contrato, user_vistoriador, token_admin):
        r = client.post(f"{BASE}/{contrato.id}/checklists", json={
            "tipo": "intermediario",
            "vistoriador_id": user_vistoriador.id,
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "tipo" in data["erro"].lower()

    def test_contrato_inexistente_retorna_falha(self, client, user_vistoriador, token_admin):
        r = client.post(f"{BASE}/id-invalido/checklists", json={
            "tipo": "inicial",
            "vistoriador_id": user_vistoriador.id,
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client, contrato, user_vistoriador):
        r = client.post(f"{BASE}/{contrato.id}/checklists", json={
            "tipo": "inicial",
            "vistoriador_id": user_vistoriador.id,
        })
        assert r.status_code == 401


# ── POST /contratos/{id}/problemas ────────────────────────────────────────────────

class TestCreateProblema:
    def test_admin_registra_problema(self, client, contrato, token_admin):
        r = client.post(f"{BASE}/{contrato.id}/problemas", json={
            "titulo": "Vazamento na cozinha",
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["titulo"] == "Vazamento na cozinha"
        assert data["dados"]["prioridade"] == "normal"
        assert data["dados"]["status"] == "aberto"

    def test_locatario_registra_problema_no_seu_contrato(self, client, contrato, token_locatario):
        r = client.post(f"{BASE}/{contrato.id}/problemas", json={
            "titulo": "Porta com defeito",
            "prioridade": "alta",
        }, headers=auth(token_locatario))
        data = r.json()
        assert data["sucesso"] is True

    def test_locatario_nao_pode_registrar_em_contrato_alheio(self, client, db, contrato, token_locatario):
        from app.models import Contrato, Imovel, Usuario
        from tests.conftest import _SENHA_HASH
        outro = Usuario(nome="O", email="o@o.com", senha_hash=_SENHA_HASH,
                       role="locatario", mfa_enabled=False, ativo=True)
        db.add(outro)
        db.flush()
        outro_im = Imovel(tipo="casa", status="disponivel", garagem=False, garagem_vagas=0)
        db.add(outro_im)
        db.flush()
        outro_ct = Contrato(imovel_id=outro_im.id, locatario_id=outro.id,
                           data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31), status="ativo")
        db.add(outro_ct)
        db.flush()

        r = client.post(f"{BASE}/{outro_ct.id}/problemas", json={"titulo": "X"},
                       headers=auth(token_locatario))
        assert r.status_code == 403

    def test_prioridade_invalida_retorna_falha(self, client, contrato, token_admin):
        r = client.post(f"{BASE}/{contrato.id}/problemas", json={
            "titulo": "X",
            "prioridade": "critica",
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "prioridade" in data["erro"].lower()

    def test_contrato_inexistente_retorna_falha(self, client, token_admin):
        r = client.post(f"{BASE}/id-invalido/problemas", json={"titulo": "X"},
                       headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client, contrato):
        r = client.post(f"{BASE}/{contrato.id}/problemas", json={"titulo": "X"})
        assert r.status_code == 401


# ── GET /contratos/{id}/problemas ─────────────────────────────────────────────────

class TestListProblemas:
    def test_lista_problemas_do_contrato(self, client, contrato, token_admin):
        # Cria um problema primeiro
        client.post(f"{BASE}/{contrato.id}/problemas", json={"titulo": "P1"},
                   headers=auth(token_admin))
        r = client.get(f"{BASE}/{contrato.id}/problemas", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert len(data["dados"]) >= 1

    def test_campos_do_problema(self, client, contrato, token_admin):
        client.post(f"{BASE}/{contrato.id}/problemas", json={"titulo": "Infiltração"},
                   headers=auth(token_admin))
        r = client.get(f"{BASE}/{contrato.id}/problemas", headers=auth(token_admin))
        p = r.json()["dados"][0]
        assert "id" in p
        assert "titulo" in p
        assert "prioridade" in p
        assert "status" in p

    def test_contrato_inexistente_retorna_falha(self, client, token_admin):
        r = client.get(f"{BASE}/id-invalido/problemas", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client, contrato):
        r = client.get(f"{BASE}/{contrato.id}/problemas")
        assert r.status_code == 401


# ── GET /contratos/{id} ───────────────────────────────────────────────────────────

class TestGetContrato:
    def test_admin_busca_contrato_por_id(self, client, contrato, token_admin):
        r = client.get(f"{BASE}/{contrato.id}", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["id"] == contrato.id
        assert data["dados"]["status"] == "ativo"

    def test_locatario_acessa_proprio_contrato(self, client, contrato, token_locatario):
        r = client.get(f"{BASE}/{contrato.id}", headers=auth(token_locatario))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["id"] == contrato.id

    def test_locatario_nao_acessa_contrato_alheio(self, client, db, contrato):
        from app.auth import create_access_token
        from app.models import Usuario
        from tests.conftest import _SENHA_HASH
        u2 = Usuario(nome="Locatario 2", email="loc2@test.com", senha_hash=_SENHA_HASH, role="locatario", ativo=True)
        db.add(u2)
        db.flush()
        token2 = create_access_token(u2.id, u2.role)

        r = client.get(f"{BASE}/{contrato.id}", headers=auth(token2))
        assert r.status_code == 403

    def test_contrato_inexistente_retorna_falha(self, client, token_admin):
        r = client.get(f"{BASE}/00000000-0000-0000-0000-000000000000", headers=auth(token_admin))
        assert r.json()["sucesso"] is False


# ── PATCH /contratos/{id}/encerrar e /cancelar ────────────────────────────────────

class TestCicloVidaContrato:
    def test_admin_encerra_contrato_e_libera_imovel(self, client, db, imovel, user_locatario, token_admin):
        # Criar contrato
        r_create = client.post(BASE, json={
            "imovel_id": imovel.id,
            "locatario_id": user_locatario.id,
            "data_inicio": "2025-01-01",
            "data_fim": "2025-12-31",
        }, headers=auth(token_admin))
        ct_id = r_create.json()["dados"]["id"]

        # Encerrar
        r = client.patch(f"{BASE}/{ct_id}/encerrar", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["status"] == "encerrado"

        # Verificar que imóvel foi liberado
        db.refresh(imovel)
        assert imovel.status == "disponivel"

    def test_admin_cancela_contrato_e_libera_imovel(self, client, db, imovel, user_locatario, token_admin):
        # Criar contrato
        r_create = client.post(BASE, json={
            "imovel_id": imovel.id,
            "locatario_id": user_locatario.id,
            "data_inicio": "2025-01-01",
            "data_fim": "2025-12-31",
        }, headers=auth(token_admin))
        ct_id = r_create.json()["dados"]["id"]

        # Cancelar
        r = client.patch(f"{BASE}/{ct_id}/cancelar", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["status"] == "cancelado"

        # Verificar que imóvel foi liberado
        db.refresh(imovel)
        assert imovel.status == "disponivel"

    def test_encerrar_contrato_ja_encerrado_retorna_falha(self, client, contrato, token_admin):
        client.patch(f"{BASE}/{contrato.id}/encerrar", headers=auth(token_admin))
        r = client.patch(f"{BASE}/{contrato.id}/encerrar", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "encerrado" in data["erro"].lower()

    def test_locatario_nao_pode_encerrar_contrato(self, client, contrato, token_locatario):
        r = client.patch(f"{BASE}/{contrato.id}/encerrar", headers=auth(token_locatario))
        assert r.status_code == 403


# ── Validações de Regra de Negócio na Criação ────────────────────────────────────

class TestValidacoesCriacaoContrato:
    def test_data_fim_anterior_a_inicio_retorna_falha(self, client, imovel, user_locatario, token_admin):
        r = client.post(BASE, json={
            "imovel_id": imovel.id,
            "locatario_id": user_locatario.id,
            "data_inicio": "2025-12-31",
            "data_fim": "2025-01-01",
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "posterior" in data["erro"].lower()

    def test_usuario_com_role_admin_como_locatario_retorna_falha(self, client, imovel, user_admin, token_admin):
        r = client.post(BASE, json={
            "imovel_id": imovel.id,
            "locatario_id": user_admin.id,
            "data_inicio": "2025-01-01",
            "data_fim": "2025-12-31",
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "locatário" in data["erro"].lower()

    def test_filtra_contratos_por_imovel_id(self, client, contrato, token_admin):
        r = client.get(f"{BASE}?imovel_id={contrato.imovel_id}", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        for c in data["dados"]:
            assert c["imovel_id"] == contrato.imovel_id
