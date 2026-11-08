"""
Segurança — SEC-033: travas do checklist e do contrato depois que saem do estado editável

A avaliação SPK-005 (docs/quality/avaliacao-testes-2026-11-02.md, seção 1) mostrou que nenhum teste
executava as recusas de:
  - enviar ou excluir foto num checklist que já saiu de em_preenchimento (checklists.py, upload_foto e
    delete_foto);
  - enviar para aceite um checklist fora de em_preenchimento (checklists.py, enviar_para_aceite);
  - cancelar ou agendar vistoria num contrato que não está ativo (contratos.py, cancelar_contrato e
    create_agendamento).
Cada teste confere a recusa (409 e a mensagem) e que nada mudou no banco nem no disco.
"""
import pytest

from app.config import UPLOAD_DIR
from app.models import (
    AgendamentoVistoria,
    Checklist,
    ChecklistItem,
    ChecklistItemFoto,
    Contrato,
    Imovel,
    ImovelComodo,
    ItemVistoria,
)
from tests.conftest import auth, small_image_bytes

API = "/api/v1"
CONTEUDO_ORIGINAL = b"conteudo-da-foto-original"
ESTADOS_TRAVADOS = ["pendente_aceite", "aceito", "rejeitado"]


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def item(db, checklist, imovel):
    comodo = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel.id).first()
    iv = ItemVistoria(nome="Piso", categoria="Acabamento")
    db.add(iv)
    db.flush()
    it = ChecklistItem(checklist_id=checklist.id, comodo_id=comodo.id, item_vistoria_id=iv.id, estado="bom")
    db.add(it)
    db.flush()
    return it


@pytest.fixture
def foto(db, item):
    """Foto já gravada no banco e no disco, como depois de um upload real."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    nome = f"sec033-{item.id}.png"
    (UPLOAD_DIR / nome).write_bytes(CONTEUDO_ORIGINAL)
    f = ChecklistItemFoto(item_id=item.id, arquivo=nome)
    db.add(f)
    db.flush()
    return f


def _travar(db, checklist, status):
    checklist.status = status
    db.flush()


def _recusado(r, mensagem):
    assert r.status_code == 409, r.text
    corpo = r.json()
    assert corpo["sucesso"] is False
    assert corpo["erro"] == mensagem
    return corpo


def _arquivos_no_disco():
    return sorted(p.name for p in UPLOAD_DIR.iterdir()) if UPLOAD_DIR.exists() else []


def _fotos_do_item(db, item_id):
    db.expire_all()
    return [(f.id, f.arquivo) for f in db.query(ChecklistItemFoto).filter(ChecklistItemFoto.item_id == item_id)]


# ── Fotos depois do envio ───────────────────────────────────────────────────────

@pytest.mark.parametrize("status", ESTADOS_TRAVADOS)
class TestFotoEmChecklistTravado:
    def test_upload_recusado_e_foto_antiga_preservada(self, client, db, checklist, item, foto, token_vistoriador, status):
        _travar(db, checklist, status)
        antes_disco = _arquivos_no_disco()

        r = client.post(f"{API}/checklists/{checklist.id}/itens/{item.id}/fotos",
                        files={"foto": ("nova.png", small_image_bytes(), "image/png")},
                        headers=auth(token_vistoriador))

        _recusado(r, f"Não é possível adicionar fotos a um checklist com status '{status}'")
        # o upload troca a foto antiga: recusado, a antiga continua no banco e no disco, e nada novo é gravado
        assert _fotos_do_item(db, item.id) == [(foto.id, foto.arquivo)]
        assert _arquivos_no_disco() == antes_disco
        assert (UPLOAD_DIR / foto.arquivo).read_bytes() == CONTEUDO_ORIGINAL

    def test_exclusao_recusada_e_foto_preservada(self, client, db, checklist, item, foto, token_vistoriador, status):
        _travar(db, checklist, status)

        r = client.delete(f"{API}/checklists/{checklist.id}/itens/{item.id}/fotos/{foto.id}",
                          headers=auth(token_vistoriador))

        _recusado(r, f"Não é possível excluir fotos de um checklist com status '{status}'")
        assert _fotos_do_item(db, item.id) == [(foto.id, foto.arquivo)]
        assert (UPLOAD_DIR / foto.arquivo).read_bytes() == CONTEUDO_ORIGINAL


def test_em_preenchimento_a_exclusao_e_permitida(client, db, checklist, item, foto, token_vistoriador):
    """Controle positivo: a mesma exclusão passa enquanto o checklist está em preenchimento."""
    r = client.delete(f"{API}/checklists/{checklist.id}/itens/{item.id}/fotos/{foto.id}",
                      headers=auth(token_vistoriador))
    assert r.status_code == 200, r.text
    assert _fotos_do_item(db, item.id) == []
    assert not (UPLOAD_DIR / foto.arquivo).exists()


# ── Envio para aceite ───────────────────────────────────────────────────────────

class TestEnviarParaAceiteForaDePreenchimento:
    @pytest.mark.parametrize("status", ESTADOS_TRAVADOS)
    def test_recusado_e_status_nao_muda(self, client, db, checklist, item, token_admin, status):
        _travar(db, checklist, status)

        r = client.patch(f"{API}/checklists/{checklist.id}/enviar-para-aceite", headers=auth(token_admin))

        _recusado(r, f"Não é possível enviar para aceite um checklist com status '{status}'")
        db.expire_all()
        assert db.get(Checklist, checklist.id).status == status

    def test_segundo_envio_e_recusado(self, client, db, checklist, item, token_admin):
        primeiro = client.patch(f"{API}/checklists/{checklist.id}/enviar-para-aceite", headers=auth(token_admin))
        assert primeiro.status_code == 200

        segundo = client.patch(f"{API}/checklists/{checklist.id}/enviar-para-aceite", headers=auth(token_admin))

        _recusado(segundo, "Não é possível enviar para aceite um checklist com status 'pendente_aceite'")
        db.expire_all()
        assert db.get(Checklist, checklist.id).status == "pendente_aceite"


# ── Contrato que não está ativo ─────────────────────────────────────────────────

@pytest.mark.parametrize("status", ["encerrado", "cancelado"])
class TestContratoNaoAtivo:
    def _inativar(self, db, contrato, imovel, status):
        contrato.status = status
        imovel.status = "disponivel"
        db.flush()

    def test_cancelar_recusado_e_nada_muda(self, client, db, contrato, imovel, token_admin, status):
        self._inativar(db, contrato, imovel, status)

        r = client.patch(f"{API}/contratos/{contrato.id}/cancelar", headers=auth(token_admin))

        _recusado(r, f"Não é possível cancelar um contrato com status '{status}'")
        db.expire_all()
        assert db.get(Contrato, contrato.id).status == status
        assert db.get(Imovel, imovel.id).status == "disponivel"

    def test_agendar_recusado_e_nenhum_agendamento_criado(self, client, db, contrato, imovel, token_admin, status):
        self._inativar(db, contrato, imovel, status)
        antes = db.query(AgendamentoVistoria).filter(AgendamentoVistoria.contrato_id == contrato.id).count()

        r = client.post(f"{API}/contratos/{contrato.id}/agendamentos",
                        json={"tipo": "encerramento", "data_agendada": "2099-01-01T10:00:00"},
                        headers=auth(token_admin))

        _recusado(r, "Agendamentos só podem ser criados em contratos ativos")
        db.expire_all()
        assert db.query(AgendamentoVistoria).filter(AgendamentoVistoria.contrato_id == contrato.id).count() == antes
