from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import (
    AgendamentoVistoria,
    Checklist,
    Contrato,
    Imovel,
    Problema,
    Usuario,
)
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
    if user.role in ("admin", "gestor", "vistoriador"):
        return
    if user.role == "locatario" and contrato.locatario_id == user.id:
        return
    raise HTTPException(status_code=403, detail="Sem permissão para registrar problemas neste contrato")


@router.post("/{contrato_id}/problemas")
def create_problema(
    contrato_id: str,
    body: ProblemaCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ct = db.query(Contrato).filter(Contrato.id == contrato_id).first()
    if not ct:
        return fail("Contrato não encontrado")
    _assert_pode_problema(ct, user)

    if body.prioridade not in ("normal", "alta", "urgente"):
        return fail("Prioridade inválida")
    if body.status not in ("aberto", "em_analise", "resolvido", "fechado"):
        return fail("Status inválido")

    pb = Problema(
        contrato_id=contrato_id,
        titulo=body.titulo.strip(),
        descricao=body.descricao,
        prioridade=body.prioridade,
        status=body.status,
    )
    db.add(pb)
    db.commit()
    db.refresh(pb)
    log_operacao(db, user.id, "create", "problema", pb.id)
    return ok({
        "id": pb.id,
        "contrato_id": pb.contrato_id,
        "titulo": pb.titulo,
        "descricao": pb.descricao,
        "prioridade": pb.prioridade,
        "status": pb.status,
        "created_at": pb.created_at.isoformat() if pb.created_at else None,
    })


@router.get("/{contrato_id}/problemas")
def list_problemas(
    contrato_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ct = db.query(Contrato).filter(Contrato.id == contrato_id).first()
    if not ct:
        return fail("Contrato não encontrado")
    try:
        _assert_pode_problema(ct, user)
    except HTTPException:
        return fail("Sem permissão para ver problemas deste contrato")
    rows = (
        db.query(Problema)
        .filter(Problema.contrato_id == contrato_id)
        .order_by(Problema.created_at.desc())
        .all()
    )
    return ok([
        {
            "id": p.id,
            "contrato_id": p.contrato_id,
            "titulo": p.titulo,
            "descricao": p.descricao,
            "prioridade": p.prioridade,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in rows
    ])
