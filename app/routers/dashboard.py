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


def _contratos_visiveis(db: Session, user: Usuario):
    """IDs dos contratos que o perfil vê em GET /contratos; None quando vê todos."""
    if user.role == "locatario":
        return db.query(Contrato.id).filter(Contrato.locatario_id == user.id)
    if user.role == "vistoriador":
        return db.query(Checklist.contrato_id).filter(Checklist.vistoriador_id == user.id)
    return None


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Totais com o mesmo recorte das listagens de cada perfil; null quando o perfil não acessa aquele dado."""
    contratos = _contratos_visiveis(db, user)

    imoveis = db.query(Imovel).filter(Imovel.ativo == True, Imovel.status == "locado")
    if user.role == "locatario":
        # Como em GET /imoveis: só imóveis de contratos ativos do locatário
        imoveis = imoveis.filter(Imovel.id.in_(
            db.query(Contrato.imovel_id).filter(Contrato.locatario_id == user.id, Contrato.status == "ativo")
        ))
    elif contratos is not None:
        imoveis = imoveis.filter(Imovel.id.in_(db.query(Contrato.imovel_id).filter(Contrato.id.in_(contratos))))

    checklists = db.query(Checklist).filter(Checklist.status.in_(["pendente_aceite", "pendente_revisao", "pendente"]))
    if user.role == "vistoriador":
        checklists = checklists.filter(Checklist.vistoriador_id == user.id)
    elif contratos is not None:
        checklists = checklists.filter(Checklist.contrato_id.in_(contratos))

    # Problemas: só admin, gestor e o locatário dono do contrato (assert_acesso_problemas)
    problemas_abertos = None
    if user.role in ("admin", "gestor", "locatario"):
        problemas = db.query(Problema).filter(Problema.status == "aberto")
        if contratos is not None:
            problemas = problemas.filter(Problema.contrato_id.in_(contratos))
        problemas_abertos = problemas.count()

    # Agendamentos: mesmo recorte de GET /contratos/{id}/agendamentos (o locatário vê os dos próprios contratos)
    agendamentos = db.query(AgendamentoVistoria)
    if contratos is not None:
        agendamentos = agendamentos.filter(AgendamentoVistoria.contrato_id.in_(contratos))
    vistorias_agendadas = agendamentos.count()

    return ok({
        "imoveis_locados": imoveis.count(),
        "checklists_pendentes": checklists.count(),
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
