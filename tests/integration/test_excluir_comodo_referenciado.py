"""
BUG-001 — Excluir cômodo referenciado por item de checklist ou por problema

delete_comodo apagava o cômodo sem conferir referências. No PostgreSQL, a chave estrangeira recusava e a
rota respondia 500; no SQLite dos testes, a FK não é aplicada e sobrava referência solta. Com a exclusão
lógica (ADR-0008), a referência pode estar num checklist ou problema excluído, invisível para quem chama.
Agora: cômodo em uso → 409 e nada é apagado.
"""
import pytest

from app.exclusao import marcar_excluido
from app.models import ChecklistItem, ImovelComodo, ItemVistoria, Problema
from tests.conftest import auth, foto_do_banco

API = "/api/v1"


@pytest.fixture
def comodo(db, imovel):
    return db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel.id).first()


def _excluir(client, imovel, comodo, token):
    return client.delete(f"{API}/imoveis/{imovel.id}/comodos/{comodo.id}", headers=auth(token))


def _usar_em_checklist(db, checklist, comodo):
    iv = ItemVistoria(nome="Piso", categoria="Acabamento")
    db.add(iv)
    db.flush()
    db.add(ChecklistItem(checklist_id=checklist.id, comodo_id=comodo.id, item_vistoria_id=iv.id, estado="bom"))
    db.flush()


@pytest.mark.parametrize("excluido", [False, True], ids=["checklist_ativo", "checklist_excluido"])
def test_comodo_usado_em_checklist_responde_409(client, db, imovel, comodo, checklist, user_admin, token_admin, excluido):
    _usar_em_checklist(db, checklist, comodo)
    if excluido:
        marcar_excluido(checklist, user_admin)
        db.flush()
    antes = foto_do_banco(db)

    r = _excluir(client, imovel, comodo, token_admin)

    assert r.status_code == 409, r.text
    assert r.json()["erro"] == "Este cômodo é usado em vistorias ou problemas e não pode ser excluído"
    assert foto_do_banco(db) == antes


@pytest.mark.parametrize("excluido", [False, True], ids=["problema_ativo", "problema_excluido"])
def test_comodo_usado_em_problema_responde_409(client, db, imovel, comodo, contrato, user_admin, token_gestor, excluido):
    pb = Problema(contrato_id=contrato.id, comodo_id=comodo.id, titulo="Infiltração")
    db.add(pb)
    db.flush()
    if excluido:
        marcar_excluido(pb, user_admin)
        db.flush()
    antes = foto_do_banco(db)

    r = _excluir(client, imovel, comodo, token_gestor)

    assert r.status_code == 409, r.text
    assert r.json()["erro"] == "Este cômodo é usado em vistorias ou problemas e não pode ser excluído"
    assert foto_do_banco(db) == antes


def test_fk_recusada_no_commit_vira_409(client, db, imovel, comodo, token_admin, monkeypatch):
    """Rede de segurança: se o banco recusar o delete (corrida ou FK nova), a resposta é 409, não 500."""
    from sqlalchemy.exc import IntegrityError
    from app.routers import imoveis as rota
    monkeypatch.setattr(rota, "_comodo_em_uso", lambda db, cid: False)
    original = db.commit

    def commit_com_fk(*a, **k):
        if any(isinstance(o, ImovelComodo) for o in db.deleted):
            raise IntegrityError("DELETE", {}, Exception("violates foreign key constraint"))
        return original(*a, **k)

    monkeypatch.setattr(db, "commit", commit_com_fk)
    r = _excluir(client, imovel, comodo, token_admin)
    assert r.status_code == 409, r.text
    assert r.json()["erro"] == "Este cômodo é usado em vistorias ou problemas e não pode ser excluído"


def test_comodo_sem_referencia_continua_sendo_excluido(client, db, imovel, comodo, token_admin):
    r = _excluir(client, imovel, comodo, token_admin)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(ImovelComodo, comodo.id) is None
