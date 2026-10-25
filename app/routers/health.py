from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.schemas import ok
from app.uploads import MEDIA_TYPES, caminho_seguro

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return ok({"status": "ok", "service": "onecheck-api"})


@router.get("/uploads/{filename}")
def serve_upload(filename: str):
    path = caminho_seguro(filename)
    if not path:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    # nosniff + CSP sandbox: mesmo um arquivo malicioso antigo não executa na origem da API
    headers = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox"}
    media_type = MEDIA_TYPES.get(path.suffix.lower())
    if media_type:
        return FileResponse(path, media_type=media_type, headers=headers)
    # Extensão fora da lista (uploads antigos): só como download, nunca renderizado
    return FileResponse(path, media_type="application/octet-stream", filename=path.name, headers=headers)
