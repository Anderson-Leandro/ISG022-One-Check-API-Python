"""
Segurança — N3: criação de checklist sem autorização (+ item 3 do PENDENCIAS_API.md)

Cenário de ataque original: POST /contratos/{id}/checklists só exigia estar
autenticado e usava o vistoriador_id do corpo. A locatária criava um checklist
no próprio contrato informando a si mesma como vistoriadora, preenchia os itens,
submetia e aceitava a própria vistoria.

Rotas cobertas:
  POST  /contratos/{id}/checklists
  PATCH /checklists/{id}/aceitar
  PATCH /checklists/{id}/rejeitar
"""
from datetime import date

import pytest

from app.models import Checklist, Contrato, Imovel, Usuario
from tests.conftest import _SENHA_HASH, auth

BASE = "/api/v1/contratos"


def _criar(client, contrato_id, vistoriador_id, token, tipo="encerramento"):
    return client.post(
        f"{BASE}/{contrato_id}/checklists",
        json={"tipo": tipo, "vistoriador_id": vistoriador_id},
        headers=auth(token),
    )


def _checklists(db, contrato_id) -> int:
    db.expire_all()
    return db.query(Checklist).filter(Checklist.contrato_id == contrato_id).count()


@pytest.fixture
def contrato_alheio(db, user_vistoriador):
    outro = Usuario(nome="Outro Loc", email="outro_loc@test.com", senha_hash=_SENHA_HASH, role="locatario", ativo=True)
    im = Imovel(tipo="casa", titulo="Casa Alheia", codigo="CASA-9", status="locado", garagem=False, garagem_vagas=0)
    db.add_all([outro, im])
    db.flush()
    ct = Contrato(
        imovel_id=im.id, locatario_id=outro.id, data_inicio=date(2025, 1, 1),
        data_fim=date(2025, 12, 31), valor_mensal=1000, status="ativo",
    )
    db.add(ct)
    db.flush()
    return ct


# ── Ataque: quem pode criar ─────────────────────────────────────────────────────

class TestQuemPodeCriarChecklist:
    def test_locatario_nao_cria_checklist_se_nomeando_vistoriador(
        self, client, db, contrato, user_locatario, token_locatario
    ):
        r = _criar(client, contrato.id, user_locatario.id, token_locatario)
        assert r.status_code == 403
        assert _checklists(db, contrato.id) == 0

    def test_locatario_nao_cria_checklist_em_contrato_alheio(
        self, client, db, contrato_alheio, user_vistoriador, token_locatario
    ):
        r = _criar(client, contrato_alheio.id, user_vistoriador.id, token_locatario)
        assert r.status_code == 403
        assert _checklists(db, contrato_alheio.id) == 0

    def test_vistoriador_nao_cria_checklist(self, client, db, contrato, user_vistoriador, token_vistoriador):
        r = _criar(client, contrato.id, user_vistoriador.id, token_vistoriador)
        assert r.status_code == 403

    def test_visualizador_nao_cria_checklist(self, client, db, contrato, user_vistoriador, token_visualizador):
        r = _criar(client, contrato.id, user_vistoriador.id, token_visualizador)
        assert r.status_code == 403

    def test_gestor_cria_checklist(self, client, db, contrato, user_vistoriador, token_gestor):
        r = _criar(client, contrato.id, user_vistoriador.id, token_gestor)
        assert r.json()["sucesso"] is True
        assert _checklists(db, contrato.id) == 1


# ── Validação do vistoriador e do contrato ──────────────────────────────────────

class TestValidacaoCriacaoChecklist:
    def test_vistoriador_inexistente_nao_gera_500(self, client, db, contrato, token_admin):
        r = _criar(client, contrato.id, "00000000-0000-0000-0000-000000000000", token_admin)
        assert r.status_code == 200
        assert r.json()["sucesso"] is False
        assert "Vistoriador não encontrado" in r.json()["erro"]
        assert _checklists(db, contrato.id) == 0

    def test_usuario_sem_perfil_vistoriador_e_rejeitado(self, client, db, contrato, user_locatario, token_admin):
        r = _criar(client, contrato.id, user_locatario.id, token_admin)
        assert r.json()["sucesso"] is False
        assert _checklists(db, contrato.id) == 0

    def test_admin_nao_pode_ser_nomeado_vistoriador(self, client, db, contrato, user_admin, token_admin):
        r = _criar(client, contrato.id, user_admin.id, token_admin)
        assert r.json()["sucesso"] is False

    def test_vistoriador_inativo_e_rejeitado(self, client, db, contrato, user_vistoriador, token_admin):
        user_vistoriador.ativo = False
        db.flush()
        r = _criar(client, contrato.id, user_vistoriador.id, token_admin)
        assert r.json()["sucesso"] is False

    def test_contrato_nao_ativo_e_rejeitado(self, client, db, contrato, user_vistoriador, token_admin):
        contrato.status = "encerrado"
        db.flush()
        r = _criar(client, contrato.id, user_vistoriador.id, token_admin)
        assert r.json()["sucesso"] is False
        assert _checklists(db, contrato.id) == 0


# ── Separação de deveres no aceite ──────────────────────────────────────────────

class TestSeparacaoDeDeveresNoAceite:
    @pytest.fixture
    def checklist_do_gestor(self, db, contrato, user_gestor):
        """Checklist legado em que o vistoriador é o próprio gestor (ex.: perfil alterado depois)."""
        ck = Checklist(
            contrato_id=contrato.id, vistoriador_id=user_gestor.id, tipo="inicial",
            status="pendente_aceite", data_vistoria=date.today(),
        )
        db.add(ck)
        db.flush()
        return ck

    def test_quem_vistoriou_nao_aceita(self, client, db, checklist_do_gestor, token_gestor):
        r = client.patch(f"/api/v1/checklists/{checklist_do_gestor.id}/aceitar", headers=auth(token_gestor))
        assert r.status_code == 403
        db.refresh(checklist_do_gestor)
        assert checklist_do_gestor.status == "pendente_aceite"

    def test_quem_vistoriou_nao_rejeita(self, client, db, checklist_do_gestor, token_gestor):
        r = client.patch(f"/api/v1/checklists/{checklist_do_gestor.id}/rejeitar", headers=auth(token_gestor))
        assert r.status_code == 403

    def test_outro_aprovador_aceita(self, client, checklist_do_gestor, token_admin):
        r = client.patch(f"/api/v1/checklists/{checklist_do_gestor.id}/aceitar", headers=auth(token_admin))
        assert r.json()["sucesso"] is True
