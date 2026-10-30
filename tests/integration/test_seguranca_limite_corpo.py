"""
Segurança — SEC-003: corpo da requisição processado antes da autenticação, sem limite

Cenário original: na rota de foto do checklist (foto: UploadFile = File(...)),
o FastAPI interpretava o multipart inteiro e gravava em arquivo temporário antes
de rodar get_current_user. Não havia limite de tamanho antes da rota, então um
anônimo enviava corpos de vários GB (ou milhares de partes) e só recebia 401
depois. As outras rotas também liam qualquer tamanho de JSON.

Regras verificadas:
  - Content-Length acima do limite recebe 413 sem que o corpo seja lido
  - corpo sem Content-Length (chunked) é cortado ao passar do limite
  - multipart anônimo recebe 401 sem que o formulário seja interpretado
  - o formulário aceita um único arquivo
"""
import pytest
from starlette.formparsers import MultiPartParser

from app.config import MAX_BODY_KB, MAX_UPLOAD_MB
from app.models import ChecklistItem, ImovelComodo, ItemVistoria
from tests.conftest import auth, small_image_bytes

MB = 1024 * 1024


@pytest.fixture
def parses(monkeypatch):
    """Conta quantas vezes um corpo multipart foi interpretado."""
    original = MultiPartParser.parse
    chamadas = []

    async def espiao(self):
        chamadas.append(1)
        return await original(self)

    monkeypatch.setattr(MultiPartParser, "parse", espiao)
    return chamadas


@pytest.fixture
def item_checklist(db, checklist, imovel):
    comodo = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel.id).first()
    iv = ItemVistoria(nome="Piso", categoria="Acabamento")
    db.add(iv)
    db.flush()
    item = ChecklistItem(checklist_id=checklist.id, comodo_id=comodo.id, item_vistoria_id=iv.id, estado="bom")
    db.add(item)
    db.flush()
    return item


def _url_foto(checklist, item):
    return f"/api/v1/checklists/{checklist.id}/itens/{item.id}/fotos"


class TestAnonimo:
    def test_multipart_anonimo_nao_e_interpretado(self, client, checklist, item_checklist, parses):
        r = client.post(_url_foto(checklist, item_checklist), files={"foto": ("a.png", b"x" * (5 * MB), "image/png")})
        assert r.status_code == 401
        assert parses == []

    def test_upload_acima_do_limite_recebe_413(self, client, checklist, item_checklist, parses):
        corpo = b"x" * ((MAX_UPLOAD_MB + 2) * MB)
        r = client.post(_url_foto(checklist, item_checklist), files={"foto": ("a.png", corpo, "image/png")})
        assert r.status_code == 413
        assert parses == []

    def test_json_acima_do_limite_recebe_413(self, client):
        corpo = '{"email": "a@a.com", "senha": "' + "x" * (MAX_BODY_KB * 1024) + '"}'
        r = client.post("/api/v1/auth/login", content=corpo, headers={"Content-Type": "application/json"})
        assert r.status_code == 413

    def test_corpo_chunked_acima_do_limite_recebe_413(self, client):
        def blocos():
            for _ in range(MAX_BODY_KB // 64 + 2):
                yield b"x" * 64 * 1024

        r = client.post("/api/v1/auth/login", content=blocos(), headers={"Content-Type": "application/json"})
        assert r.status_code == 413

    def test_content_length_invalido_recebe_400(self, client):
        r = client.post("/api/v1/auth/login", content=b"{}", headers={"Content-Type": "application/json", "Content-Length": "abc"})
        assert r.status_code == 400


class TestAutenticado:
    def test_upload_acima_do_limite_recebe_413_sem_ler_o_corpo(
        self, client, checklist, item_checklist, token_vistoriador, parses
    ):
        corpo = b"x" * ((MAX_UPLOAD_MB + 2) * MB)
        r = client.post(
            _url_foto(checklist, item_checklist),
            files={"foto": ("a.png", corpo, "image/png")},
            headers=auth(token_vistoriador),
        )
        assert r.status_code == 413
        assert parses == []

    def test_upload_valido_continua_funcionando(self, client, checklist, item_checklist, token_vistoriador):
        r = client.post(
            _url_foto(checklist, item_checklist),
            files={"foto": ("a.png", small_image_bytes(), "image/png")},
            headers=auth(token_vistoriador),
        )
        assert r.json()["sucesso"] is True

    def test_json_normal_continua_funcionando(self, client):
        r = client.post("/api/v1/auth/login", json={"email": "ninguem@x.com", "senha": "errada"})
        assert r.status_code == 200

    def test_mais_de_um_arquivo_e_recusado(self, client, checklist, item_checklist, token_vistoriador):
        img = small_image_bytes()
        r = client.post(
            _url_foto(checklist, item_checklist),
            files=[("foto", ("a.png", img, "image/png")), ("foto", ("b.png", img, "image/png"))],
            headers=auth(token_vistoriador),
        )
        assert r.status_code == 400

    def test_sem_campo_foto_e_recusado(self, client, checklist, item_checklist, token_vistoriador):
        r = client.post(
            _url_foto(checklist, item_checklist),
            files={"outro": ("a.png", small_image_bytes(), "image/png")},
            headers=auth(token_vistoriador),
        )
        assert r.json()["sucesso"] is False
