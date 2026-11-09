from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import MAX_UPLOAD_MB
from app.database import get_db
from app.deps import assert_acesso_problemas, get_current_user, require_roles
from app.exclusao import marcar_excluido
from app.models import AtualizacaoProblema, Contrato, Problema, Usuario
from app.notification_service import notificar_admins, notificar_usuario
from app.respostas import ProblemaResposta, documentar
from app.schemas import (
    STATUS_PROBLEMA,
    STATUS_PROBLEMA_ENCERRADOS,
    AtualizacaoProblemaCreate,
    AtualizacaoProblemaForm,
    ProblemaStatusUpdate,
    corpo_no_openapi,
)
from app.serializers import log_operacao, serialize_atualizacao_problema, serialize_problema
from app.uploads import UploadInvalido, nome_de_upload_existente, salvar_imagem

router = APIRouter(tags=["problemas"])


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
    assert_acesso_problemas(contrato, user)
    return contrato


@router.get("/problemas/{problema_id}", responses=documentar(ProblemaResposta, erros=(401, 403, 404)))
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


@router.delete("/problemas/{problema_id}")
def excluir_problema(
    problema_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    """Exclusão lógica (ADR-0008): só para problema ainda aberto e sem atualizações."""
    pb = db.query(Problema).filter(Problema.id == problema_id).first()
    if not pb:
        return _fail("Problema não encontrado", status_code=404)
    if pb.status != "aberto":
        return _fail(f"Não é possível excluir um problema com status '{pb.status}'", status_code=409)
    if db.query(AtualizacaoProblema.id).filter(AtualizacaoProblema.problema_id == problema_id).first():
        return _fail("Não é possível excluir um problema que já tem atualizações", status_code=409)

    marcar_excluido(pb, user)
    db.commit()
    log_operacao(db, user.id, "delete", "problema", problema_id)
    return _ok(None)


@router.patch("/problemas/{problema_id}/status", openapi_extra=corpo_no_openapi(ProblemaStatusUpdate))
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
    # Um corpo que não é objeto, ou um status que não é texto, é tratado como status ausente (422)
    novo_status = body.get("status") if isinstance(body, dict) else None
    novo_status = novo_status.strip() if isinstance(novo_status, str) else ""
    if not novo_status or novo_status not in STATUS_PROBLEMA:
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


@router.post(
    "/problemas/{problema_id}/atualizacoes",
    openapi_extra=corpo_no_openapi(AtualizacaoProblemaCreate, AtualizacaoProblemaForm),
)
async def criar_atualizacao(
    problema_id: str,
    request: Request,
    db: Session = Depends(get_db),
    # O perfil é barrado antes da busca: um vistoriador não descobre quais IDs de problema existem
    user: Usuario = Depends(require_roles("admin", "gestor", "locatario")),
):
    """Admin e gestor comentam sempre; o locatário dono, enquanto o problema não estiver encerrado (ADR-0012)."""
    pb = db.query(Problema).filter(Problema.id == problema_id).first()
    if not pb:
        return _fail("Problema não encontrado", status_code=404)
    # Autorização antes de ler o corpo: quem não pode comentar não chega a enviar arquivo
    try:
        contrato = _assert_pode_acessar_problema(pb, user, db)
    except HTTPException as e:
        return _fail(e.detail, status_code=e.status_code)
    if user.role == "locatario" and pb.status in STATUS_PROBLEMA_ENCERRADOS:
        return _fail("Não é possível comentar num problema resolvido", status_code=409)

    content_type = request.headers.get("content-type", "")
    descricao = ""
    foto_chave = None

    if "multipart/form-data" in content_type:
        form = await request.form(max_files=1, max_fields=10)
        descricao = str(form.get("descricao") or "")
        foto = form.get("foto")
        if foto and hasattr(foto, "read"):
            content = await foto.read()
            if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
                return _fail(
                    f"A foto não pode exceder {MAX_UPLOAD_MB} MB",
                    status_code=422,
                    erros={"foto": f"A foto não pode exceder {MAX_UPLOAD_MB} MB"},
                )

            try:
                foto_chave = salvar_imagem(content)
            except UploadInvalido as e:
                return _fail(str(e), status_code=422, erros={"foto": str(e)})
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        descricao = str(body.get("descricao") or "")
        if body.get("foto_url"):
            foto_chave = nome_de_upload_existente(body.get("foto_url"))
            if not foto_chave:
                return _fail("Foto inválida", status_code=422, erros={"foto_url": "Envie a foto pelo upload da API"})

    descricao = descricao.strip()
    if not descricao or len(descricao) < 5:
        return _fail(
            "Descrição deve ter no mínimo 5 caracteres",
            status_code=422,
            erros={"descricao": "O campo descrição deve ter pelo menos 5 caracteres"},
        )

    # O status pode ter mudado durante o upload: confere de novo antes de gravar
    db.refresh(pb)
    if user.role == "locatario" and pb.status in STATUS_PROBLEMA_ENCERRADOS:
        return _fail("Não é possível comentar num problema resolvido", status_code=409)

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

    if user.role == "locatario":
        notificar_admins(
            db,
            f"Novo comentário do locatário — {pb.titulo}",
            f"O locatário comentou no problema.\n\nProblema: {pb.titulo}\nComentário: {descricao}\n\nAcesse o painel para visualizar os detalhes.",
        )
    elif contrato:
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
