import uuid
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import MAX_UPLOAD_MB, UPLOAD_DIR
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import AtualizacaoProblema, Contrato, Problema, Usuario
from app.notification_service import notificar_usuario
from app.serializers import log_operacao, serialize_atualizacao_problema, serialize_problema

router = APIRouter(tags=["problemas"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp"}


def _ok(dados: Any = None, mensagem: str | None = None, status_code: int = 200) -> JSONResponse:
    res = {"sucesso": True, "dados": dados}
    if mensagem:
        res["mensagem"] = mensagem
    return JSONResponse(status_code=status_code, content=res)


def _fail(erro: str, status_code: int = 400, erros: dict | None = None) -> JSONResponse:
    res = {"sucesso": False, "erro": erro}
    if erros:
        res["erros"] = erros
    return JSONResponse(status_code=status_code, content=res)


def _assert_pode_acessar_problema(pb: Problema, user: Usuario, db: Session) -> Contrato:
    contrato = db.query(Contrato).filter(Contrato.id == pb.contrato_id).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    if user.role == "locatario" and contrato.locatario_id != user.id:
        raise HTTPException(status_code=403, detail="Você não tem acesso a este problema")
    return contrato


@router.get("/problemas/{problema_id}")
def get_problema_by_id(
    problema_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    pb = db.query(Problema).filter(Problema.id == problema_id).first()
    if not pb:
        return _fail("Problema não encontrado", status_code=404)

    try:
        _assert_pode_acessar_problema(pb, user, db)
    except HTTPException as e:
        return _fail(e.detail, status_code=e.status_code)

    return _ok(serialize_problema(pb))


@router.patch("/problemas/{problema_id}/status")
async def atualizar_status_problema(
    problema_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    pb = db.query(Problema).filter(Problema.id == problema_id).first()
    if not pb:
        return _fail("Problema não encontrado", status_code=404)

    try:
        body = await request.json()
    except Exception:
        body = {}

    novo_status = (body.get("status") or "").strip()
    status_permitidos = {"aberto", "em_andamento", "em_analise", "resolvido", "fechado"}
    if not novo_status or novo_status not in status_permitidos:
        return _fail("Status inválido", status_code=422, erros={"status": "Status inválido"})

    status_ant = pb.status
    pb.status = novo_status
    db.commit()
    db.refresh(pb)

    log_operacao(
        db,
        user.id,
        "update",
        "registro_problema",
        pb.id,
        payload={"status_anterior": status_ant, "status_novo": novo_status},
    )

    return _ok(serialize_problema(pb))


@router.post("/problemas/{problema_id}/atualizacoes")
async def criar_atualizacao(
    problema_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    pb = db.query(Problema).filter(Problema.id == problema_id).first()
    if not pb:
        return _fail("Problema não encontrado", status_code=404)

    content_type = request.headers.get("content-type", "")
    descricao = ""
    foto_chave = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        descricao = str(form.get("descricao") or "")
        foto = form.get("foto")
        if foto and hasattr(foto, "read"):
            content = await foto.read()
            if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
                return _fail(f"A foto não pode exceder {MAX_UPLOAD_MB} MB", status_code=422, erros={"foto": f"A foto não pode exceder {MAX_UPLOAD_MB} MB"})
            
            ext = Path(getattr(foto, "filename", "foto.jpg") or "foto.jpg").suffix or ".jpg"
            filename = f"{uuid.uuid4().hex}{ext}"
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            filepath = UPLOAD_DIR / filename
            filepath.write_bytes(content)
            foto_chave = filename
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        descricao = str(body.get("descricao") or "")
        foto_chave = body.get("foto_url")

    descricao = descricao.strip()
    if not descricao or len(descricao) < 5:
        return _fail(
            "Descrição deve ter no mínimo 5 caracteres",
            status_code=422,
            erros={"descricao": "O campo descrição deve ter pelo menos 5 caracteres"},
        )

    atualizacao = AtualizacaoProblema(
        problema_id=problema_id,
        autor_id=user.id,
        descricao=descricao,
        foto_url=foto_chave,
    )
    db.add(atualizacao)
    db.commit()
    db.refresh(atualizacao)

    log_operacao(
        db,
        user.id,
        "create",
        "atualizacao_problema",
        atualizacao.id,
        payload={"problema_id": problema_id, "autor_id": user.id},
    )

    contrato = db.query(Contrato).filter(Contrato.id == pb.contrato_id).first()
    if contrato:
        notificar_usuario(
            db,
            contrato.locatario_id,
            f"Atualização no seu problema — {pb.titulo}",
            f"Seu problema recebeu uma atualização.\n\nProblema: {pb.titulo}\nAtualização: {descricao}\n\nAcesse o painel para visualizar os detalhes.",
        )

    return _ok(serialize_atualizacao_problema(atualizacao), status_code=201)


@router.get("/problemas/{problema_id}/atualizacoes")
def listar_atualizacoes(
    problema_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    pb = db.query(Problema).filter(Problema.id == problema_id).first()
    if not pb:
        return _fail("Problema não encontrado", status_code=404)

    try:
        _assert_pode_acessar_problema(pb, user, db)
    except HTTPException as e:
        return _fail(e.detail, status_code=e.status_code)

    atualizacoes = (
        db.query(AtualizacaoProblema)
        .filter(AtualizacaoProblema.problema_id == problema_id)
        .order_by(AtualizacaoProblema.created_at.asc())
        .all()
    )

    return _ok([serialize_atualizacao_problema(a) for a in atualizacoes])
