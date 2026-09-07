from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import (
    AgendamentoVistoria,
    Checklist,
    Contrato,
    Imovel,
    LogOperacao,
    Problema,
    Usuario,
)
from app.schemas import ok
from app.serializers import paginate

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    imoveis_locados = db.query(Imovel).filter(Imovel.status == "locado").count()
    checklists_pendentes = (
        db.query(Checklist)
        .filter(Checklist.status.in_(["pendente_aceite", "pendente_revisao", "pendente"]))
        .count()
    )
    problemas_abertos = db.query(Problema).filter(Problema.status == "aberto").count()
    vistorias_agendadas = db.query(AgendamentoVistoria).count()

    return ok({
        "imoveis_locados": imoveis_locados,
        "checklists_pendentes": checklists_pendentes,
        "problemas_abertos": problemas_abertos,
        "vistorias_agendadas": vistorias_agendadas,
    })


@router.get("/logs")
def logs(
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    acao: str | None = None,
    entidade: str | None = None,
    usuario_id: str | None = None,
    de: str | None = None,
    ate: str | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles("admin", "gestor")),
):
    q = db.query(LogOperacao)
    if acao:
        q = q.filter(LogOperacao.acao == acao)
    if entidade:
        q = q.filter(LogOperacao.entidade == entidade)
    if usuario_id:
        q = q.filter(LogOperacao.usuario_id == usuario_id)
    if de:
        try:
            de_dt = datetime.fromisoformat(de)
            q = q.filter(LogOperacao.created_at >= de_dt)
        except Exception:
            pass
    if ate:
        try:
            ate_dt = datetime.fromisoformat(f"{ate}T23:59:59") if "T" not in ate else datetime.fromisoformat(ate)
            q = q.filter(LogOperacao.created_at <= ate_dt)
        except Exception:
            pass

    q = q.order_by(LogOperacao.created_at.desc())
    items, pag = paginate(q, pagina, por_pagina)
    return ok([
        {
            "id": l.id,
            "usuario_id": l.usuario_id,
            "acao": l.acao,
            "entidade": l.entidade,
            "entidade_id": l.entidade_id,
            "detalhes": l.detalhes,
            "payload": l.payload,
            "ip": l.ip,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in items
    ], pag)
