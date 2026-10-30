"""Gravação e entrega das imagens enviadas pelos usuários (fotos de vistoria e de problemas)."""
import io
import re
import uuid
from pathlib import Path

from PIL import Image

from app.config import PUBLIC_BASE_URL, UPLOAD_DIR

# O tipo vem do conteúdo, nunca do nome ou do Content-Type enviados pelo cliente
_EXTENSAO_POR_FORMATO = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
_FORMATOS = list(_EXTENSAO_POR_FORMATO)
# Assinaturas conferidas antes de chamar o Pillow: os demais decoders (PSD, TIFF, ...) nunca recebem o arquivo
_ASSINATURAS = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")
# O Pillow emite aviso acima deste valor e recusa (DecompressionBombError) acima do dobro: 50 megapixels
Image.MAX_IMAGE_PIXELS = 25_000_000
MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_NOME_UPLOAD = re.compile(r"[0-9a-f]{32}\.(?:jpg|png|webp)")
_PREFIXO_URL = "/api/v1/uploads/"


class UploadInvalido(ValueError):
    pass


def _assinatura_aceita(content: bytes) -> bool:
    return content.startswith(_ASSINATURAS) or (content[:4] == b"RIFF" and content[8:12] == b"WEBP")


def salvar_imagem(content: bytes) -> str:
    """Valida que o conteúdo é JPEG, PNG ou WebP e grava com nome aleatório e extensão do tipo detectado."""
    if not _assinatura_aceita(content):
        raise UploadInvalido("Envie uma imagem JPEG, PNG ou WebP")
    try:
        with Image.open(io.BytesIO(content), formats=_FORMATOS) as im:
            formato = im.format
            im.verify()
    except Exception:  # inclui conteúdo truncado e DecompressionBombError
        raise UploadInvalido("Envie uma imagem JPEG, PNG ou WebP")
    extensao = _EXTENSAO_POR_FORMATO.get(formato)
    if not extensao:
        raise UploadInvalido("Envie uma imagem JPEG, PNG ou WebP")

    nome = f"{uuid.uuid4().hex}{extensao}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / nome).write_bytes(content)
    return nome


def nome_de_upload_existente(valor) -> str | None:
    """Aceita o nome ou a URL de um upload desta API que exista em disco; qualquer outra coisa é None."""
    if not isinstance(valor, str):
        return None
    nome = valor.strip().removeprefix(PUBLIC_BASE_URL).removeprefix(_PREFIXO_URL)
    if not _NOME_UPLOAD.fullmatch(nome) or not (UPLOAD_DIR / nome).is_file():
        return None
    return nome


def caminho_seguro(filename: str) -> Path | None:
    """Caminho do arquivo dentro de UPLOAD_DIR, ou None se não existir ou escapar do diretório."""
    base = UPLOAD_DIR.resolve()
    path = (base / filename).resolve()
    if path.parent != base or not path.is_file():
        return None
    return path
