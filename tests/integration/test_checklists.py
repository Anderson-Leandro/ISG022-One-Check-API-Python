"""
Fase 2.5 — Testes de integração das rotas de checklists

Rotas cobertas:
  GET    /api/v1/itens-vistoria
  GET    /api/v1/checklists/{id}
  POST   /api/v1/checklists/{id}/itens
  PUT    /api/v1/checklists/{id}/itens/{item_id}
  POST   /api/v1/checklists/{id}/itens/{item_id}/fotos
  DELETE /api/v1/checklists/{id}/itens/{item_id}/fotos/{foto_id}
  PATCH  /api/v1/checklists/{id}/submeter
  PATCH  /api/v1/checklists/{id}/aceitar
  PATCH  /api/v1/checklists/{id}/rejeitar
"""
import pytest

from app.models import ChecklistItem, ChecklistItemFoto, ImovelComodo
from tests.conftest import auth, small_image_bytes

BASE = "/api/v1/checklists"
ITENS_BASE = "/api/v1/itens-vistoria"


# ── Helpers ───────────────────────────────────────────────────────────────────────

def _primeiro_comodo(db, imovel_id: str) -> ImovelComodo:
    return db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel_id).first()


def _cria_item(db, checklist_id: str, comodo_id: str, item_vistoria_id: str, estado: str = "bom") -> ChecklistItem:
    item = ChecklistItem(
        checklist_id=checklist_id,
        comodo_id=comodo_id,
        item_vistoria_id=item_vistoria_id,
        estado=estado,
    )
    db.add(item)
    db.flush()
    return item


def _submete(client, checklist_id: str, token: str) -> None:
    client.patch(f"{BASE}/{checklist_id}/submeter", headers=auth(token))


# ── GET /itens-vistoria ───────────────────────────────────────────────────────────

class TestListItensVistoria:
    def test_lista_itens_autenticado(self, client, item_vistoria, token_admin):
        r = client.get(ITENS_BASE, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert any(i["id"] == item_vistoria.id for i in data["dados"])

    def test_campos_do_item(self, client, item_vistoria, token_admin):
        r = client.get(ITENS_BASE, headers=auth(token_admin))
        item = next(i for i in r.json()["dados"] if i["id"] == item_vistoria.id)
        assert item["nome"] == "Pintura"
        assert item["categoria"] == "Acabamento"

    def test_sem_autenticacao_retorna_401(self, client):
        r = client.get(ITENS_BASE)
        assert r.status_code == 401


# ── GET /checklists/{id} ──────────────────────────────────────────────────────────

class TestGetChecklist:
    def test_admin_obtem_checklist(self, client, checklist, token_admin):
        r = client.get(f"{BASE}/{checklist.id}", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["id"] == checklist.id
        assert "itens" in data["dados"]
        assert "comodos" in data["dados"]

    def test_vistoriador_obtem_seu_checklist(self, client, checklist, token_vistoriador):
        r = client.get(f"{BASE}/{checklist.id}", headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is True

    def test_locatario_obtem_checklist_do_seu_contrato(self, client, checklist, token_locatario):
        r = client.get(f"{BASE}/{checklist.id}", headers=auth(token_locatario))
        data = r.json()
        assert data["sucesso"] is True

    def test_visualizador_obtem_checklist(self, client, checklist, token_visualizador):
        r = client.get(f"{BASE}/{checklist.id}", headers=auth(token_visualizador))
        data = r.json()
        assert data["sucesso"] is True

    def test_id_inexistente_retorna_falha(self, client, token_admin):
        r = client.get(f"{BASE}/id-invalido", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "encontrado" in data["erro"].lower()

    def test_sem_autenticacao_retorna_401(self, client, checklist):
        r = client.get(f"{BASE}/{checklist.id}")
        assert r.status_code == 401


# ── POST /checklists/{id}/itens ───────────────────────────────────────────────────

class TestAddItem:
    def test_vistoriador_adiciona_item(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        r = client.post(f"{BASE}/{checklist.id}/itens", json={
            "comodo_id": comodo.id,
            "item_vistoria_id": item_vistoria.id,
            "estado": "bom",
        }, headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["estado"] == "bom"

    def test_admin_adiciona_item(self, client, db, checklist, item_vistoria, imovel, token_admin):
        comodo = _primeiro_comodo(db, imovel.id)
        r = client.post(f"{BASE}/{checklist.id}/itens", json={
            "comodo_id": comodo.id,
            "item_vistoria_id": item_vistoria.id,
            "estado": "otimo",
            "observacao": "Perfeito estado",
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["observacao"] == "Perfeito estado"

    def test_upsert_item_existente_atualiza_estado(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        payload = {"comodo_id": comodo.id, "item_vistoria_id": item_vistoria.id, "estado": "bom"}
        client.post(f"{BASE}/{checklist.id}/itens", json=payload, headers=auth(token_vistoriador))
        payload["estado"] = "ruim"
        r = client.post(f"{BASE}/{checklist.id}/itens", json=payload, headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["estado"] == "ruim"
        # Verifica que só existe um item (não duplicou)
        count = db.query(ChecklistItem).filter(
            ChecklistItem.checklist_id == checklist.id,
            ChecklistItem.comodo_id == comodo.id,
            ChecklistItem.item_vistoria_id == item_vistoria.id,
        ).count()
        assert count == 1

    def test_estado_invalido_retorna_falha(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        r = client.post(f"{BASE}/{checklist.id}/itens", json={
            "comodo_id": comodo.id,
            "item_vistoria_id": item_vistoria.id,
            "estado": "perfeito",
        }, headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is False
        assert "estado" in data["erro"].lower()

    def test_locatario_nao_pode_adicionar_item(self, client, db, checklist, item_vistoria, imovel, token_locatario):
        comodo = _primeiro_comodo(db, imovel.id)
        r = client.post(f"{BASE}/{checklist.id}/itens", json={
            "comodo_id": comodo.id,
            "item_vistoria_id": item_vistoria.id,
            "estado": "bom",
        }, headers=auth(token_locatario))
        assert r.status_code == 403

    def test_checklist_inexistente_retorna_falha(self, client, item_vistoria, token_admin):
        r = client.post(f"{BASE}/id-invalido/itens", json={
            "comodo_id": "qualquer",
            "item_vistoria_id": item_vistoria.id,
            "estado": "bom",
        }, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client, checklist, item_vistoria):
        r = client.post(f"{BASE}/{checklist.id}/itens", json={
            "comodo_id": "qualquer",
            "item_vistoria_id": item_vistoria.id,
            "estado": "bom",
        })
        assert r.status_code == 401


# ── PUT /checklists/{id}/itens/{item_id} ──────────────────────────────────────────

class TestUpdateItem:
    def test_atualiza_estado_do_item(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        item = _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        r = client.put(f"{BASE}/{checklist.id}/itens/{item.id}", json={
            "estado": "regular",
        }, headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["estado"] == "regular"

    def test_atualiza_observacao_do_item(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        item = _cria_item(db, checklist.id, comodo.id, item_vistoria.id)
        r = client.put(f"{BASE}/{checklist.id}/itens/{item.id}", json={
            "observacao": "Necessita reparo",
        }, headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["observacao"] == "Necessita reparo"

    def test_estado_invalido_retorna_falha(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        item = _cria_item(db, checklist.id, comodo.id, item_vistoria.id)
        r = client.put(f"{BASE}/{checklist.id}/itens/{item.id}", json={
            "estado": "excelente",
        }, headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is False

    def test_item_inexistente_retorna_falha(self, client, checklist, token_vistoriador):
        r = client.put(f"{BASE}/{checklist.id}/itens/id-invalido", json={
            "estado": "bom",
        }, headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client, db, checklist, item_vistoria, imovel):
        comodo = _primeiro_comodo(db, imovel.id)
        item = _cria_item(db, checklist.id, comodo.id, item_vistoria.id)
        r = client.put(f"{BASE}/{checklist.id}/itens/{item.id}", json={"estado": "bom"})
        assert r.status_code == 401


# ── POST /checklists/{id}/itens/{item_id}/fotos ───────────────────────────────────

class TestUploadFoto:
    def test_upload_foto_valida(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        item = _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        r = client.post(
            f"{BASE}/{checklist.id}/itens/{item.id}/fotos",
            files={"foto": ("test.jpg", small_image_bytes(), "image/jpeg")},
            headers=auth(token_vistoriador),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert "url" in data["dados"]
        assert data["dados"]["url"].startswith("/api/v1/uploads/")

    def test_foto_substitui_anterior(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        item = _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        client.post(
            f"{BASE}/{checklist.id}/itens/{item.id}/fotos",
            files={"foto": ("a.jpg", small_image_bytes(), "image/jpeg")},
            headers=auth(token_vistoriador),
        )
        client.post(
            f"{BASE}/{checklist.id}/itens/{item.id}/fotos",
            files={"foto": ("b.jpg", small_image_bytes(), "image/jpeg")},
            headers=auth(token_vistoriador),
        )
        db.expire_all()
        count = db.query(ChecklistItemFoto).filter(ChecklistItemFoto.item_id == item.id).count()
        assert count == 1

    def test_item_sem_estado_nao_aceita_foto(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        item = ChecklistItem(
            checklist_id=checklist.id,
            comodo_id=comodo.id,
            item_vistoria_id=item_vistoria.id,
            estado=None,
        )
        db.add(item)
        db.flush()
        r = client.post(
            f"{BASE}/{checklist.id}/itens/{item.id}/fotos",
            files={"foto": ("test.jpg", small_image_bytes(), "image/jpeg")},
            headers=auth(token_vistoriador),
        )
        data = r.json()
        assert data["sucesso"] is False
        assert "estado" in data["erro"].lower()

    def test_item_inexistente_retorna_falha(self, client, checklist, token_vistoriador):
        r = client.post(
            f"{BASE}/{checklist.id}/itens/id-invalido/fotos",
            files={"foto": ("test.jpg", small_image_bytes(), "image/jpeg")},
            headers=auth(token_vistoriador),
        )
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client, db, checklist, item_vistoria, imovel):
        comodo = _primeiro_comodo(db, imovel.id)
        item = _cria_item(db, checklist.id, comodo.id, item_vistoria.id)
        r = client.post(
            f"{BASE}/{checklist.id}/itens/{item.id}/fotos",
            files={"foto": ("test.jpg", small_image_bytes(), "image/jpeg")},
        )
        assert r.status_code == 401


# ── DELETE /checklists/{id}/itens/{item_id}/fotos/{foto_id} ──────────────────────

class TestDeleteFoto:
    def _upload(self, client, checklist_id, item_id, token):
        r = client.post(
            f"{BASE}/{checklist_id}/itens/{item_id}/fotos",
            files={"foto": ("test.jpg", small_image_bytes(), "image/jpeg")},
            headers=auth(token),
        )
        return r.json()["dados"]["id"]

    def test_deleta_foto(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        item = _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        foto_id = self._upload(client, checklist.id, item.id, token_vistoriador)

        r = client.delete(
            f"{BASE}/{checklist.id}/itens/{item.id}/fotos/{foto_id}",
            headers=auth(token_vistoriador),
        )
        data = r.json()
        assert data["sucesso"] is True
        db.expire_all()
        assert db.query(ChecklistItemFoto).filter(ChecklistItemFoto.id == foto_id).first() is None

    def test_foto_inexistente_retorna_falha(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        item = _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        r = client.delete(
            f"{BASE}/{checklist.id}/itens/{item.id}/fotos/id-invalido",
            headers=auth(token_vistoriador),
        )
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client, db, checklist, item_vistoria, imovel):
        comodo = _primeiro_comodo(db, imovel.id)
        item = _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        r = client.delete(f"{BASE}/{checklist.id}/itens/{item.id}/fotos/qualquer-id")
        assert r.status_code == 401


# ── PATCH /checklists/{id}/submeter ───────────────────────────────────────────────

class TestSubmeterChecklist:
    def test_submete_com_item_preenchido(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        r = client.patch(f"{BASE}/{checklist.id}/submeter", headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["status"] == "pendente_aceite"

    def test_sem_itens_retorna_falha(self, client, checklist, token_vistoriador):
        r = client.patch(f"{BASE}/{checklist.id}/submeter", headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is False
        assert "item" in data["erro"].lower()

    def test_ja_submetido_retorna_falha(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        _submete(client, checklist.id, token_vistoriador)
        r = client.patch(f"{BASE}/{checklist.id}/submeter", headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is False
        assert "submetido" in data["erro"].lower()

    def test_outro_vistoriador_nao_pode_submeter(self, client, db, checklist, item_vistoria, imovel, token_gestor):
        # gestor não é o vistoriador do checklist
        comodo = _primeiro_comodo(db, imovel.id)
        _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        r = client.patch(f"{BASE}/{checklist.id}/submeter", headers=auth(token_gestor))
        assert r.status_code == 403

    def test_checklist_inexistente_retorna_falha(self, client, token_admin):
        r = client.patch(f"{BASE}/id-invalido/submeter", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client, checklist):
        r = client.patch(f"{BASE}/{checklist.id}/submeter")
        assert r.status_code == 401


# ── PATCH /checklists/{id}/aceitar ────────────────────────────────────────────────

class TestAceitarChecklist:
    def _prepara_pendente(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        _submete(client, checklist.id, token_vistoriador)

    def test_admin_aceita_checklist(self, client, db, checklist, item_vistoria, imovel, token_vistoriador, token_admin):
        self._prepara_pendente(client, db, checklist, item_vistoria, imovel, token_vistoriador)
        r = client.patch(f"{BASE}/{checklist.id}/aceitar", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["status"] == "aceito"

    def test_gestor_aceita_checklist(self, client, db, checklist, item_vistoria, imovel, token_vistoriador, token_gestor):
        self._prepara_pendente(client, db, checklist, item_vistoria, imovel, token_vistoriador)
        r = client.patch(f"{BASE}/{checklist.id}/aceitar", headers=auth(token_gestor))
        data = r.json()
        assert data["sucesso"] is True

    def test_vistoriador_nao_pode_aceitar(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        self._prepara_pendente(client, db, checklist, item_vistoria, imovel, token_vistoriador)
        r = client.patch(f"{BASE}/{checklist.id}/aceitar", headers=auth(token_vistoriador))
        assert r.status_code == 403

    def test_nao_pendente_retorna_falha(self, client, checklist, token_admin):
        # checklist ainda está em_preenchimento
        r = client.patch(f"{BASE}/{checklist.id}/aceitar", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "pendente" in data["erro"].lower()

    def test_sem_autenticacao_retorna_401(self, client, checklist):
        r = client.patch(f"{BASE}/{checklist.id}/aceitar")
        assert r.status_code == 401


# ── PATCH /checklists/{id}/rejeitar ──────────────────────────────────────────────

class TestRejeitarChecklist:
    def _prepara_pendente(self, client, db, checklist, item_vistoria, imovel, token_vistoriador):
        comodo = _primeiro_comodo(db, imovel.id)
        _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        _submete(client, checklist.id, token_vistoriador)

    def test_admin_rejeita_checklist(self, client, db, checklist, item_vistoria, imovel, token_vistoriador, token_admin):
        self._prepara_pendente(client, db, checklist, item_vistoria, imovel, token_vistoriador)
        r = client.patch(f"{BASE}/{checklist.id}/rejeitar", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["status"] == "rejeitado"

    def test_locatario_nao_pode_rejeitar(self, client, db, checklist, item_vistoria, imovel, token_vistoriador, token_locatario):
        self._prepara_pendente(client, db, checklist, item_vistoria, imovel, token_vistoriador)
        r = client.patch(f"{BASE}/{checklist.id}/rejeitar", headers=auth(token_locatario))
        assert r.status_code == 403

    def test_nao_pendente_retorna_falha(self, client, checklist, token_admin):
        r = client.patch(f"{BASE}/{checklist.id}/rejeitar", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client, checklist):
        r = client.patch(f"{BASE}/{checklist.id}/rejeitar")
        assert r.status_code == 401


# ── PATCH /checklists/{id}/enviar-para-aceite ─────────────────────────────────────

class TestEnviarParaAceite:
    def test_admin_envia_para_aceite_sucesso(self, client, db, checklist, item_vistoria, imovel, token_admin):
        comodo = _primeiro_comodo(db, imovel.id)
        _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        r = client.patch(f"{BASE}/{checklist.id}/enviar-para-aceite", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["status"] == "pendente_aceite"

    def test_envio_sem_itens_retorna_falha(self, client, checklist, token_admin):
        r = client.patch(f"{BASE}/{checklist.id}/enviar-para-aceite", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "ao menos um item" in data["erro"].lower()

    def test_bloqueia_adicionar_itens_em_checklist_pendente(self, client, db, checklist, item_vistoria, imovel, token_vistoriador, token_admin):
        comodo = _primeiro_comodo(db, imovel.id)
        _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        client.patch(f"{BASE}/{checklist.id}/enviar-para-aceite", headers=auth(token_admin))

        # Tentar adicionar item após envio
        r = client.post(f"{BASE}/{checklist.id}/itens", json={
            "comodo_id": comodo.id,
            "item_vistoria_id": item_vistoria.id,
            "estado": "otimo",
        }, headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is False
        assert "não é possível adicionar" in data["erro"].lower()

    def test_bloqueia_editar_itens_em_checklist_pendente(self, client, db, checklist, item_vistoria, imovel, token_vistoriador, token_admin):
        comodo = _primeiro_comodo(db, imovel.id)
        item = _cria_item(db, checklist.id, comodo.id, item_vistoria.id, "bom")
        client.patch(f"{BASE}/{checklist.id}/enviar-para-aceite", headers=auth(token_admin))

        # Tentar editar item após envio
        r = client.put(f"{BASE}/{checklist.id}/itens/{item.id}", json={
            "estado": "regular",
        }, headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is False
        assert "não é possível editar" in data["erro"].lower()
