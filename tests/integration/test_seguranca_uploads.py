"""
Segurança — N7: uploads sem validação de tipo, servidos publicamente

Cenário original: as três rotas de upload gravavam qualquer conteúdo e usavam a
extensão do nome enviado pelo cliente. GET /uploads/{arquivo} servia o arquivo
sem autenticação, com Content-Type deduzido da extensão: um HTML ou SVG enviado
como "foto" virava XSS armazenado na origem da API. O campo JSON foto_url de
problemas e atualizações aceitava qualquer texto (ex.: javascript:...).

Regras verificadas:
  - só JPEG, PNG e WebP, detectados pelo conteúdo; a extensão vem do tipo detectado
  - conteúdo recusado não é gravado em disco
  - o download nunca é servido como HTML/SVG e sempre leva nosniff e CSP restritiva
  - foto_url por JSON só referencia um upload existente
"""
import uuid

import pytest

from app.config import UPLOAD_DIR
from app.models import ChecklistItem, ImovelComodo, ItemVistoria, Problema
from tests.conftest import auth, small_image_bytes

HTML = b"<html><body><script>alert(document.domain)</script></body></html>"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'

MALICIOSOS = [
    ("foto.jpg", HTML, "image/jpeg"),
    ("foto.html", HTML, "text/html"),
    ("foto.svg", SVG, "image/svg+xml"),
    ("foto.png", b"\x89PNG\r\n\x1a\n" + HTML, "image/png"),  # só a assinatura, sem imagem
]


def _arquivos():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return set(p.name for p in UPLOAD_DIR.iterdir())


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


@pytest.fixture
def problema(db, contrato):
    pb = Problema(contrato_id=contrato.id, titulo="Infiltração", descricao="Mancha no teto")
    db.add(pb)
    db.flush()
    return pb


def _upload_checklist(client, checklist, item, token, arquivo):
    return client.post(f"/api/v1/checklists/{checklist.id}/itens/{item.id}/fotos", files={"foto": arquivo}, headers=auth(token))


def _upload_problema(client, contrato, token, arquivo):
    return client.post(
        f"/api/v1/contratos/{contrato.id}/problemas",
        data={"titulo": "Vazamento", "descricao": "Vazamento na pia da cozinha"},
        files={"foto": arquivo},
        headers=auth(token),
    )


def _upload_atualizacao(client, problema, token, arquivo):
    return client.post(
        f"/api/v1/problemas/{problema.id}/atualizacoes",
        data={"descricao": "Técnico trocou a vedação"},
        files={"foto": arquivo},
        headers=auth(token),
    )


# ── Conteúdo recusado ────────────────────────────────────────────────────────────

class TestConteudoRecusado:
    @pytest.mark.parametrize("arquivo", MALICIOSOS, ids=[a[0] for a in MALICIOSOS])
    def test_checklist(self, client, checklist, item_checklist, token_vistoriador, arquivo):
        antes = _arquivos()
        r = _upload_checklist(client, checklist, item_checklist, token_vistoriador, arquivo)
        assert r.json()["sucesso"] is False
        assert _arquivos() == antes

    @pytest.mark.parametrize("arquivo", MALICIOSOS, ids=[a[0] for a in MALICIOSOS])
    def test_problema(self, client, contrato, token_locatario, arquivo):
        antes = _arquivos()
        r = _upload_problema(client, contrato, token_locatario, arquivo)
        assert r.status_code == 422
        assert _arquivos() == antes

    @pytest.mark.parametrize("arquivo", MALICIOSOS, ids=[a[0] for a in MALICIOSOS])
    def test_atualizacao(self, client, problema, token_admin, arquivo):
        antes = _arquivos()
        r = _upload_atualizacao(client, problema, token_admin, arquivo)
        assert r.status_code == 422
        assert _arquivos() == antes


# ── Extensão vem do conteúdo ─────────────────────────────────────────────────────

class TestExtensaoPeloConteudo:
    def test_checklist(self, client, checklist, item_checklist, token_vistoriador):
        r = _upload_checklist(client, checklist, item_checklist, token_vistoriador, ("x.html", small_image_bytes(), "text/html"))
        assert r.json()["sucesso"] is True
        assert r.json()["dados"]["url"].endswith(".png")

    def test_problema(self, client, contrato, token_locatario):
        r = _upload_problema(client, contrato, token_locatario, ("x.svg", small_image_bytes(), "image/svg+xml"))
        assert r.status_code == 201
        assert r.json()["dados"]["foto_url"].endswith(".png")

    def test_atualizacao(self, client, problema, token_admin):
        r = _upload_atualizacao(client, problema, token_admin, ("x.html", small_image_bytes(), "text/html"))
        assert r.status_code == 201
        assert r.json()["dados"]["foto_url"].endswith(".png")


# ── Download ─────────────────────────────────────────────────────────────────────

class TestDownload:
    def test_arquivo_legado_html_nao_e_servido_como_html(self, client):
        nome = f"{uuid.uuid4().hex}.html"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOAD_DIR / nome).write_bytes(HTML)
        try:
            r = client.get(f"/api/v1/uploads/{nome}")
            assert r.status_code == 200
            assert "html" not in r.headers["content-type"]
            assert r.headers["content-disposition"].startswith("attachment")
            assert r.headers["x-content-type-options"] == "nosniff"
        finally:
            (UPLOAD_DIR / nome).unlink(missing_ok=True)

    def test_imagem_tem_cabecalhos_de_protecao(self, client):
        nome = f"{uuid.uuid4().hex}.png"
        (UPLOAD_DIR / nome).write_bytes(small_image_bytes())
        try:
            r = client.get(f"/api/v1/uploads/{nome}")
            assert r.status_code == 200
            assert r.headers["content-type"] == "image/png"
            assert r.headers["x-content-type-options"] == "nosniff"
            assert "default-src 'none'" in r.headers["content-security-policy"]
        finally:
            (UPLOAD_DIR / nome).unlink(missing_ok=True)

    @pytest.mark.parametrize("caminho", ["..%2Fapp%2Fconfig.py", "%2E%2E", "..%5C..%5Capp%5Cconfig.py"])
    def test_travessia_de_diretorio(self, client, caminho):
        r = client.get(f"/api/v1/uploads/{caminho}")
        assert r.status_code == 404


# ── foto_url por JSON ────────────────────────────────────────────────────────────

FOTO_URL_INVALIDAS = ["javascript:alert(1)", "https://evil.example/x.png", "../../etc/passwd", f"{uuid.uuid4().hex}.png"]


class TestFotoUrlJson:
    @pytest.mark.parametrize("valor", FOTO_URL_INVALIDAS)
    def test_problema_recusa(self, client, contrato, token_locatario, valor):
        r = client.post(
            f"/api/v1/contratos/{contrato.id}/problemas",
            json={"titulo": "Vazamento", "foto_url": valor},
            headers=auth(token_locatario),
        )
        assert r.status_code == 422

    @pytest.mark.parametrize("valor", FOTO_URL_INVALIDAS)
    def test_atualizacao_recusa(self, client, problema, token_admin, valor):
        r = client.post(
            f"/api/v1/problemas/{problema.id}/atualizacoes",
            json={"descricao": "Técnico agendado", "foto_url": valor},
            headers=auth(token_admin),
        )
        assert r.status_code == 422

    @pytest.mark.parametrize("prefixo", ["", "/api/v1/uploads/"])
    def test_referencia_a_upload_existente_e_aceita(self, client, problema, token_admin, prefixo):
        nome = f"{uuid.uuid4().hex}.png"
        (UPLOAD_DIR / nome).write_bytes(small_image_bytes())
        try:
            r = client.post(
                f"/api/v1/problemas/{problema.id}/atualizacoes",
                json={"descricao": "Foto do reparo", "foto_url": f"{prefixo}{nome}"},
                headers=auth(token_admin),
            )
            assert r.status_code == 201
            assert r.json()["dados"]["foto_url"] == nome
        finally:
            (UPLOAD_DIR / nome).unlink(missing_ok=True)
