"""
Segurança — SEC-032: negação de acesso aos checklists por quem não é dono

A avaliação SPK-005 (docs/quality/avaliacao-testes-2026-11-02.md) mostrou que a negação em
_assert_pode_ver_checklist e _assert_pode_aceitar (app/routers/checklists.py) nunca era
executada: trocar 'and' por 'or' na checagem do locatário não fazia nenhum teste falhar.
Estes testes cobrem quem não é dono em cada rota e conferem que nada muda no banco.

Rotas cobertas:
  GET    /checklists/{id}
  PUT    /checklists/{id}/itens/{item_id}
  POST   /checklists/{id}/itens/{item_id}/fotos
  DELETE /checklists/{id}/itens/{item_id}/fotos/{foto_id}
  PATCH  /checklists/{id}/submeter
  PATCH  /checklists/{id}/aceitar
  PATCH  /checklists/{id}/rejeitar
  GET    /checklists/{id}/pdf e /download-pdf
  GET    /contratos/{id}/checklists
"""
from datetime import date

import pytest

from app.auth import create_access_token
from app.models import (
    AceiteChecklist,
    Checklist,
    ChecklistItem,
    ChecklistItemFoto,
    ImovelComodo,
    ItemVistoria,
    Usuario,
)
from tests.conftest import _SENHA_HASH, auth, small_image_bytes

API = "/api/v1"


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def outro_vistoriador(db):
    u = Usuario(nome="Outro Vistoriador", email="outro.vist@test.com", senha_hash=_SENHA_HASH,
                role="vistoriador", ativo=True)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def token_outro_vistoriador(outro_vistoriador):
    return create_access_token(outro_vistoriador.id, outro_vistoriador.role)


@pytest.fixture
def outro_locatario(db):
    u = Usuario(nome="Outro Locatário", email="outro.loc@test.com", senha_hash=_SENHA_HASH,
                role="locatario", ativo=True)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def token_outro_locatario(outro_locatario):
    return create_access_token(outro_locatario.id, outro_locatario.role)


@pytest.fixture
def item(db, checklist, imovel):
    comodo = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel.id).first()
    iv = ItemVistoria(nome="Piso", categoria="Acabamento")
    db.add(iv)
    db.flush()
    it = ChecklistItem(checklist_id=checklist.id, comodo_id=comodo.id, item_vistoria_id=iv.id,
                       estado="bom", observacao="original")
    db.add(it)
    db.flush()
    return it


@pytest.fixture
def foto(db, item):
    f = ChecklistItemFoto(item_id=item.id, arquivo="foto-original.png")
    db.add(f)
    db.flush()
    return f


@pytest.fixture
def checklist_pendente(db, checklist, item):
    checklist.status = "pendente_aceite"
    db.flush()
    return checklist


def _recarregar(db, modelo, id_):
    db.expire_all()
    return db.get(modelo, id_)


def _negado(r):
    assert r.status_code == 403, r.text
    corpo = r.json()
    assert "dados" not in corpo
    return corpo


# ── Leitura ─────────────────────────────────────────────────────────────────────

class TestVerChecklist:
    def test_locatario_de_outro_contrato_recebe_403_sem_dados(self, client, checklist, item, token_outro_locatario):
        corpo = _negado(client.get(f"{API}/checklists/{checklist.id}", headers=auth(token_outro_locatario)))
        assert corpo["detail"] == "Sem permissão para ver esta vistoria"

    def test_outro_vistoriador_recebe_403_sem_dados(self, client, checklist, item, token_outro_vistoriador):
        corpo = _negado(client.get(f"{API}/checklists/{checklist.id}", headers=auth(token_outro_vistoriador)))
        assert corpo["detail"] == "Sem permissão para ver esta vistoria"

    def test_locatario_dono_ve_o_checklist(self, client, checklist, item, token_locatario):
        r = client.get(f"{API}/checklists/{checklist.id}", headers=auth(token_locatario))
        assert r.status_code == 200
        assert r.json()["dados"]["id"] == checklist.id

    def test_vistoriador_do_checklist_ve_o_checklist(self, client, checklist, item, token_vistoriador):
        r = client.get(f"{API}/checklists/{checklist.id}", headers=auth(token_vistoriador))
        assert r.status_code == 200
        assert r.json()["dados"]["id"] == checklist.id

    def test_gestor_ve_o_checklist(self, client, checklist, item, token_gestor):
        r = client.get(f"{API}/checklists/{checklist.id}", headers=auth(token_gestor))
        assert r.status_code == 200
        assert r.json()["dados"]["id"] == checklist.id


class TestListarChecklistsDoContrato:
    def test_vistoriador_so_lista_os_proprios_checklists(
        self, client, db, contrato, checklist, outro_vistoriador, token_vistoriador, token_outro_vistoriador
    ):
        alheio = Checklist(contrato_id=contrato.id, vistoriador_id=outro_vistoriador.id, tipo="encerramento",
                           status="em_preenchimento", data_vistoria=date.today())
        db.add(alheio)
        db.flush()

        meus = client.get(f"{API}/contratos/{contrato.id}/checklists", headers=auth(token_vistoriador))
        dele = client.get(f"{API}/contratos/{contrato.id}/checklists", headers=auth(token_outro_vistoriador))
        assert [c["id"] for c in meus.json()["dados"]] == [checklist.id]
        assert [c["id"] for c in dele.json()["dados"]] == [alheio.id]


# ── Escrita pelo vistoriador ────────────────────────────────────────────────────

class TestOutroVistoriadorNaoAlteraChecklist:
    def test_nao_edita_item(self, client, db, checklist, item, token_outro_vistoriador):
        r = client.put(f"{API}/checklists/{checklist.id}/itens/{item.id}",
                       json={"estado": "ruim", "observacao": "alterado"}, headers=auth(token_outro_vistoriador))
        _negado(r)
        depois = _recarregar(db, ChecklistItem, item.id)
        assert (depois.estado, depois.observacao) == ("bom", "original")

    def test_nao_envia_foto(self, client, db, checklist, item, token_outro_vistoriador):
        r = client.post(f"{API}/checklists/{checklist.id}/itens/{item.id}/fotos",
                        files={"foto": ("a.png", small_image_bytes(), "image/png")},
                        headers=auth(token_outro_vistoriador))
        _negado(r)
        db.expire_all()
        assert db.query(ChecklistItemFoto).filter(ChecklistItemFoto.item_id == item.id).count() == 0

    def test_nao_exclui_foto(self, client, db, checklist, item, foto, token_outro_vistoriador):
        r = client.delete(f"{API}/checklists/{checklist.id}/itens/{item.id}/fotos/{foto.id}",
                          headers=auth(token_outro_vistoriador))
        _negado(r)
        assert _recarregar(db, ChecklistItemFoto, foto.id) is not None

    def test_nao_submete(self, client, db, checklist, item, token_outro_vistoriador):
        r = client.patch(f"{API}/checklists/{checklist.id}/submeter", headers=auth(token_outro_vistoriador))
        _negado(r)
        assert _recarregar(db, Checklist, checklist.id).status == "em_preenchimento"


# ── Aceite pelo locatário ───────────────────────────────────────────────────────

class TestLocatarioDeOutroContratoNaoDecide:
    @pytest.mark.parametrize("acao", ["aceitar", "rejeitar"])
    def test_recebe_403_e_o_status_nao_muda(self, client, db, checklist_pendente, token_outro_locatario, acao):
        r = client.patch(f"{API}/checklists/{checklist_pendente.id}/{acao}", json={"motivo": "teste"},
                         headers=auth(token_outro_locatario))
        corpo = _negado(r)
        assert corpo["detail"] == "Sem permissão para aceitar ou rejeitar esta vistoria"
        assert _recarregar(db, Checklist, checklist_pendente.id).status == "pendente_aceite"
        assert db.query(AceiteChecklist).filter(AceiteChecklist.checklist_id == checklist_pendente.id).count() == 0

    def test_locatario_dono_aceita(self, client, db, checklist_pendente, token_locatario):
        r = client.patch(f"{API}/checklists/{checklist_pendente.id}/aceitar", headers=auth(token_locatario))
        assert r.status_code == 200
        assert _recarregar(db, Checklist, checklist_pendente.id).status == "aceito"


# ── PDF ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rota", ["pdf", "download-pdf"])
class TestPdfDoChecklist:
    def test_locatario_dono_baixa_o_pdf(self, client, checklist, item, token_locatario, rota):
        r = client.get(f"{API}/checklists/{checklist.id}/{rota}", headers=auth(token_locatario))
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content.startswith(b"%PDF")

    def test_locatario_de_outro_contrato_recebe_403(self, client, checklist, item, token_outro_locatario, rota):
        r = client.get(f"{API}/checklists/{checklist.id}/{rota}", headers=auth(token_outro_locatario))
        assert r.status_code == 403
        assert r.json()["detail"] == "Você não tem permissão para baixar o PDF deste checklist"
        assert not r.content.startswith(b"%PDF")
