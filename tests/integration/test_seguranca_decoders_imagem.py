"""
Segurança — SEC-002: decoders vulneráveis do Pillow alcançáveis pelo upload

Cenário original: salvar_imagem chamava Image.open sem restringir formatos, com
Pillow 11.1.0. O Pillow testava todos os plugins (PSD, TIFF, FITS, JPEG2000...)
antes de o código checar se era JPEG/PNG/WebP, então um locatário enviava um
PSD malicioso como "foto" e alcançava decoders com CVEs (inclusive de execução
de código).

Regras verificadas:
  - a assinatura (magic bytes) é conferida antes de o Pillow receber o arquivo
  - Image.open só pode usar os plugins JPEG, PNG e WebP
  - imagens válidas de outros formatos são recusadas sem chegar ao Pillow
  - imagens acima de 50 megapixels são recusadas (decompression bomb)
"""
import io

import pytest
from PIL import Image

import app.uploads as uploads
from app.models import ChecklistItem, ImovelComodo, ItemVistoria
from app.uploads import UploadInvalido, salvar_imagem
from tests.conftest import auth


def _imagem(formato: str, tamanho=(4, 4), modo="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(modo, tamanho, (10, 20, 30) if modo == "RGB" else 0).save(buf, format=formato)
    return buf.getvalue()


@pytest.fixture
def chamadas_open(monkeypatch):
    """Registra os formatos passados a Image.open sem impedir a chamada real."""
    original = Image.open
    chamadas = []

    def espiao(fp, mode="r", formats=None):
        chamadas.append(formats)
        return original(fp, mode, formats)

    monkeypatch.setattr(uploads.Image, "open", espiao)
    return chamadas


class TestFormatosAceitos:
    @pytest.mark.parametrize("formato,extensao", [("JPEG", ".jpg"), ("PNG", ".png"), ("WEBP", ".webp")])
    def test_aceita(self, formato, extensao, chamadas_open):
        assert salvar_imagem(_imagem(formato)).endswith(extensao)
        assert chamadas_open == [["JPEG", "PNG", "WEBP"]]


class TestOutrosFormatos:
    @pytest.mark.parametrize("formato", ["TIFF", "GIF", "BMP", "PPM", "ICO", "TGA"])
    def test_imagem_valida_de_outro_formato_nao_chega_ao_pillow(self, formato, chamadas_open):
        with pytest.raises(UploadInvalido):
            salvar_imagem(_imagem(formato))
        assert chamadas_open == []

    def test_psd_nao_chega_ao_pillow(self, chamadas_open):
        psd = b"8BPS\x00\x01" + b"\x00" * 64
        with pytest.raises(UploadInvalido):
            salvar_imagem(psd)
        assert chamadas_open == []

    @pytest.mark.parametrize("prefixo", [b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF\x00\x00\x00\x00WEBP"])
    def test_outro_formato_com_assinatura_falsa_e_recusado(self, prefixo, chamadas_open):
        # Passa pela assinatura, mas o Pillow só pode tentar os plugins permitidos
        with pytest.raises(UploadInvalido):
            salvar_imagem(prefixo + _imagem("TIFF"))
        assert chamadas_open == [["JPEG", "PNG", "WEBP"]]


class TestDecompressionBomb:
    def test_imagem_acima_de_50_megapixels_e_recusada(self):
        # 8000 x 8000 = 64 MP; em modo 1 bit o PNG fica pequeno
        with pytest.raises(UploadInvalido):
            salvar_imagem(_imagem("PNG", tamanho=(8000, 8000), modo="1"))

    def test_imagem_grande_dentro_do_limite_e_aceita(self):
        assert salvar_imagem(_imagem("PNG", tamanho=(6000, 4000), modo="1")).endswith(".png")


class TestRota:
    @pytest.fixture
    def item_checklist(self, db, checklist, imovel):
        comodo = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel.id).first()
        iv = ItemVistoria(nome="Piso", categoria="Acabamento")
        db.add(iv)
        db.flush()
        item = ChecklistItem(checklist_id=checklist.id, comodo_id=comodo.id, item_vistoria_id=iv.id, estado="bom")
        db.add(item)
        db.flush()
        return item

    def test_tiff_enviado_como_jpg_e_recusado(self, client, checklist, item_checklist, token_vistoriador, chamadas_open):
        r = client.post(
            f"/api/v1/checklists/{checklist.id}/itens/{item_checklist.id}/fotos",
            files={"foto": ("foto.jpg", _imagem("TIFF"), "image/jpeg")},
            headers=auth(token_vistoriador),
        )
        assert r.json()["sucesso"] is False
        assert chamadas_open == []
