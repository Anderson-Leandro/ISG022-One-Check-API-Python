import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import MAX_UPLOAD_MB, UPLOAD_DIR
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import (
    AgendamentoVistoria,
    Checklist,
    Contrato,
    Imovel,
    ImovelComodo,
    Problema,
    Usuario,
)
from app.notification_service import notificar_admins
from app.schemas import (
    AgendamentoCreate,
    ChecklistCreate,
    ContratoCreate,
    ProblemaCreate,
    fail,
    ok,
)
from app.serializers import (
    log_operacao,
    paginate,
    serialize_agendamento,
    serialize_checklist,
    serialize_contrato,
    serialize_problema,
)

router = APIRouter(prefix="/contratos", tags=["contratos"])


@router.get("")
def list_contratos(
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    status: str | None = None,
    imovel_id: str | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    q = db.query(Contrato)
    if user.role == "locatario":
        q = q.filter(Contrato.locatario_id == user.id)
    elif user.role == "vistoriador":
        q = (
            q.join(Checklist, Checklist.contrato_id == Contrato.id)
            .filter(Checklist.vistoriador_id == user.id)
            .distinct()
        )
    if status:
        q = q.filter(Contrato.status == status)
    if imovel_id:
        q = q.filter(Contrato.imovel_id == imovel_id)
    q = q.order_by(Contrato.created_at.desc())
    items, pag = paginate(q, pagina, por_pagina)
    return ok([serialize_contrato(c) for c in items], pag)


@router.post("")
def create_contrato(
    body: ContratoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    if body.data_fim <= body.data_inicio:
        return fail("A data de fim deve ser posterior à data de início.")

    imovel = db.query(Imovel).filter(Imovel.id == body.imovel_id, Imovel.ativo == True).first()
    if not imovel:
        return fail("Imóvel não encontrado")
    if imovel.status == "locado":
        return fail("Imóvel já está locado")
    if db.query(Contrato).filter(Contrato.imovel_id == body.imovel_id, Contrato.status == "ativo").first():
        return fail("Este imóvel já possui um contrato ativo")

    locatario = db.query(Usuario).filter(Usuario.id == body.locatario_id, Usuario.ativo == True).first()
    if not locatario:
        return fail("Locatário não encontrado")
    if locatario.role != "locatario":
        return fail("O usuário informado não possui a role de locatário")

    ct = Contrato(
        imovel_id=body.imovel_id,
        locatario_id=body.locatario_id,
        data_inicio=body.data_inicio,
        data_fim=body.data_fim,
        valor_mensal=body.valor_mensal,
        status="ativo",
    )
    db.add(ct)
    imovel.status = "locado"
    db.flush()

    for tipo in ("inicial", "encerramento"):
        db.add(
            AgendamentoVistoria(
                contrato_id=ct.id,
                tipo=tipo,
                data_agendada=body.data_inicio if tipo == "inicial" else body.data_fim,
                observacao=f"Vistoria de {tipo}",
            )
        )

    db.commit()
    db.refresh(ct)
    log_operacao(db, user.id, "create", "contrato", ct.id)
    return ok(serialize_contrato(ct))


@router.get("/{contrato_id}")
def get_contrato(
    contrato_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ct = db.query(Contrato).filter(Contrato.id == contrato_id).first()
    if not ct:
        return fail("Contrato não encontrado")

    if user.role == "locatario" and ct.locatario_id != user.id:
        raise HTTPException(status_code=403, detail="Você não tem acesso a este contrato")

    return ok(serialize_contrato(ct))


@router.patch("/{contrato_id}/encerrar")
@router.post("/{contrato_id}/encerrar")
def encerrar_contrato(
    contrato_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    ct = db.query(Contrato).filter(Contrato.id == contrato_id).first()
    if not ct:
        return fail("Contrato não encontrado")

    if ct.status != "ativo":
        return fail(f"Não é possível encerrar um contrato com status '{ct.status}'")

    ct.status = "encerrado"
    imovel = db.query(Imovel).filter(Imovel.id == ct.imovel_id).first()
    if imovel:
        imovel.status = "disponivel"

    db.commit()
    db.refresh(ct)
    log_operacao(db, user.id, "update", "contrato", ct.id, "encerrar")
    return ok(serialize_contrato(ct))


@router.patch("/{contrato_id}/cancelar")
@router.post("/{contrato_id}/cancelar")
def cancelar_contrato(
    contrato_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    ct = db.query(Contrato).filter(Contrato.id == contrato_id).first()
    if not ct:
        return fail("Contrato não encontrado")

    if ct.status != "ativo":
        return fail(f"Não é possível cancelar um contrato com status '{ct.status}'")

    ct.status = "cancelado"
    imovel = db.query(Imovel).filter(Imovel.id == ct.imovel_id).first()
    if imovel:
        imovel.status = "disponivel"

    db.commit()
    db.refresh(ct)
    log_operacao(db, user.id, "update", "contrato", ct.id, "cancelar")
    return ok(serialize_contrato(ct))


def _parse_datetime(dt_val) -> datetime:
    if isinstance(dt_val, datetime):
        return dt_val
    if isinstance(dt_val, date):
        return datetime.combine(dt_val, datetime.min.time())
    if isinstance(dt_val, str):
        dt_val = dt_val.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(dt_val)
        except Exception:
            raise ValueError("Formato de data inválido")
    raise ValueError("Formato de data inválido")


@router.get("/{contrato_id}/agendamentos")
def list_agendamentos(
    contrato_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ct = db.query(Contrato).filter(Contrato.id == contrato_id).first()
    if not ct:
        return fail("Contrato não encontrado")

    if user.role == "locatario":
        raise HTTPException(status_code=403, detail="Você não tem acesso aos agendamentos deste contrato")

    rows = (
        db.query(AgendamentoVistoria)
        .filter(AgendamentoVistoria.contrato_id == contrato_id)
        .order_by(AgendamentoVistoria.created_at)
        .all()
    )
    return ok([serialize_agendamento(r) for r in rows])


@router.post("/{contrato_id}/agendamentos")
def create_agendamento(
    contrato_id: str,
    body: AgendamentoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    ct = db.query(Contrato).filter(Contrato.id == contrato_id).first()
    if not ct:
        return fail("Contrato não encontrado")

    if ct.status != "ativo":
        return fail("Agendamentos só podem ser criados em contratos ativos")

    if body.tipo not in ("inicial", "encerramento"):
        return fail("Tipo inválido. Deve ser 'inicial' ou 'encerramento'")

    try:
        parsed_dt = _parse_datetime(body.data_agendada)
    except Exception:
        return fail("Formato de data_agendada inválido")

    now = datetime.now() if parsed_dt.tzinfo is None else datetime.now(timezone.utc)
    if parsed_dt <= now:
        return fail("A data agendada deve ser uma data futura")

    ag = AgendamentoVistoria(
        contrato_id=contrato_id,
        tipo=body.tipo,
        data_agendada=parsed_dt.replace(tzinfo=None) if parsed_dt.tzinfo else parsed_dt,
        observacao=body.observacao,
    )
    db.add(ag)
    db.commit()
    db.refresh(ag)
    log_operacao(db, user.id, "create", "agendamento_vistoria", ag.id)
    return ok(serialize_agendamento(ag))


@router.get("/{contrato_id}/checklists")
def list_checklists(
    contrato_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ct = db.query(Contrato).filter(Contrato.id == contrato_id).first()
    if not ct:
        return fail("Contrato não encontrado")
    if user.role == "locatario" and ct.locatario_id != user.id:
        return fail("Sem permissão para ver vistorias deste contrato")

    q = db.query(Checklist).filter(Checklist.contrato_id == contrato_id)
    if user.role == "vistoriador":
        q = q.filter(Checklist.vistoriador_id == user.id)
    rows = q.order_by(Checklist.created_at.desc()).all()
    return ok([serialize_checklist(c) for c in rows])


@router.post("/{contrato_id}/checklists")
def create_checklist(
    contrato_id: str,
    body: ChecklistCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ct = db.query(Contrato).filter(Contrato.id == contrato_id).first()
    if not ct:
        return fail("Contrato não encontrado")

    if body.tipo not in ("inicial", "encerramento"):
        return fail("Tipo deve ser 'inicial' ou 'encerramento'")

    existing = (
        db.query(Checklist)
        .filter(Checklist.contrato_id == contrato_id, Checklist.tipo == body.tipo)
        .first()
    )
    if existing and body.tipo == "inicial":
        return fail("Este contrato já possui vistoria inicial")

    ck = Checklist(
        contrato_id=contrato_id,
        vistoriador_id=body.vistoriador_id,
        tipo=body.tipo,
        status="em_preenchimento",
        data_vistoria=body.data_vistoria or date.today(),
    )
    db.add(ck)

    ag = (
        db.query(AgendamentoVistoria)
        .filter(AgendamentoVistoria.contrato_id == contrato_id, AgendamentoVistoria.tipo == body.tipo)
        .first()
    )
    if ag and body.data_vistoria:
        ag.data_agendada = body.data_vistoria

    db.commit()
    db.refresh(ck)
    log_operacao(db, user.id, "create", "checklist", ck.id, body.tipo)
    return ok(serialize_checklist(ck))


def _assert_pode_problema(contrato: Contrato, user: Usuario) -> None:
    if user.role in ("admin", "gestor"):
        return
    if user.role == "locatario" and contrato.locatario_id == user.id:
        return
    raise HTTPException(status_code=403, detail="Você não tem permissão para registrar problemas neste contrato")


@router.post("/{contrato_id}/problemas")
async def create_problema(
    contrato_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ct = db.query(Contrato).filter(Contrato.id == contrato_id).first()
    if not ct:
        return JSONResponse(status_code=404, content={"sucesso": False, "erro": "Contrato não encontrado"})
    
    if ct.status != "ativo":
        return JSONResponse(
            status_code=422,
            content={"sucesso": False, "erro": "Problemas só podem ser registrados em contratos ativos"},
        )

    try:
        _assert_pode_problema(ct, user)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"sucesso": False, "erro": e.detail})

    content_type = request.headers.get("content-type", "")
    foto_chave = None
    titulo = ""
    descricao = None
    comodo_id = None
    prioridade = "normal"
    status_val = "aberto"

    if "multipart/form-data" in content_type:
        form = await request.form()
        titulo = str(form.get("titulo") or "").strip()
        descricao = form.get("descricao")
        if descricao is not None:
            descricao = str(descricao).strip()
        comodo_id = form.get("comodo_id")
        if comodo_id:
            comodo_id = str(comodo_id).strip()
        if form.get("prioridade"):
            prioridade = str(form.get("prioridade")).strip()
        if form.get("status"):
            status_val = str(form.get("status")).strip()
        
        foto = form.get("foto")
        if foto and hasattr(foto, "read"):
            content = await foto.read()
            if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
                return JSONResponse(
                    status_code=422,
                    content={"sucesso": False, "erro": f"A foto não pode exceder {MAX_UPLOAD_MB} MB", "erros": {"foto": f"A foto não pode exceder {MAX_UPLOAD_MB} MB"}},
                )
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
        titulo = str(body.get("titulo") or "").strip()
        descricao = body.get("descricao")
        if descricao is not None:
            descricao = str(descricao).strip()
        comodo_id = body.get("comodo_id")
        if comodo_id:
            comodo_id = str(comodo_id).strip()
        prioridade = str(body.get("prioridade") or "normal").strip()
        status_val = str(body.get("status") or "aberto").strip()
        foto_chave = body.get("foto_url")

    erros = {}
    if not titulo:
        erros["titulo"] = "O campo título é obrigatório"

    if comodo_id:
        comodo = (
            db.query(ImovelComodo)
            .filter(ImovelComodo.id == comodo_id, ImovelComodo.imovel_id == ct.imovel_id)
            .first()
        )
        if not comodo:
            return JSONResponse(status_code=404, content={"sucesso": False, "erro": "Cômodo não encontrado"})

    if prioridade not in ("normal", "alta", "urgente"):
        return JSONResponse(status_code=422, content={"sucesso": False, "erro": "Prioridade inválida", "erros": {"prioridade": "Prioridade inválida"}})

    if status_val not in ("aberto", "em_andamento", "em_analise", "resolvido", "fechado"):
        return JSONResponse(status_code=422, content={"sucesso": False, "erro": "Status inválido", "erros": {"status": "Status inválido"}})

    if erros:
        return JSONResponse(status_code=422, content={"sucesso": False, "erro": "Dados inválidos", "erros": erros})

    pb = Problema(
        contrato_id=contrato_id,
        comodo_id=comodo_id,
        titulo=titulo,
        descricao=descricao,
        foto_url=foto_chave,
        prioridade=prioridade,
        status=status_val,
    )
    db.add(pb)
    db.commit()
    db.refresh(pb)

    log_operacao(
        db,
        user.id,
        "create",
        "registro_problema",
        pb.id,
        payload={"contrato_id": contrato_id, "comodo_id": pb.comodo_id, "titulo": pb.titulo},
    )

    notificar_admins(
        db,
        f"Novo problema registrado — {pb.titulo}",
        f"Um novo problema foi registrado no contrato {contrato_id}.\n\nTítulo: {pb.titulo}\nDescrição: {pb.descricao}\n\nAcesse o painel para visualizar os detalhes.",
    )

    return JSONResponse(status_code=201, content={"sucesso": True, "dados": serialize_problema(pb)})


@router.get("/{contrato_id}/problemas")
def list_problemas(
    contrato_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ct = db.query(Contrato).filter(Contrato.id == contrato_id).first()
    if not ct:
        return JSONResponse(status_code=404, content={"sucesso": False, "erro": "Contrato não encontrado"})
    try:
        _assert_pode_problema(ct, user)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"sucesso": False, "erro": e.detail})

    rows = (
        db.query(Problema)
        .filter(Problema.contrato_id == contrato_id)
        .order_by(Problema.created_at.desc())
        .all()
    )
    return ok([serialize_problema(p) for p in rows])
