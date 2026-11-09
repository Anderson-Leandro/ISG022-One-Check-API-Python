import re
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, negar_perfil_desconhecido, require_roles
from app.models import (
    AgendamentoVistoria,
    Checklist,
    Contrato,
    Imovel,
    LogOperacao,
    Problema,
    Usuario,
)
from app.schemas import fail, ok
from app.serializers import paginate

router = APIRouter(tags=["dashboard"])


def _contratos_visiveis(db: Session, user: Usuario):
    """IDs dos contratos que o perfil vê em GET /contratos; None quando vê todos (só admin e gestor)."""
    negar_perfil_desconhecido(user)
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
        imoveis = imoveis.filter(
            Imovel.id.in_(
                db.query(Contrato.imovel_id).filter(Contrato.locatario_id == user.id, Contrato.status == "ativo")
            )
        )
    elif contratos is not None:
        imoveis = imoveis.filter(Imovel.id.in_(db.query(Contrato.imovel_id).filter(Contrato.id.in_(contratos))))

    checklists = db.query(Checklist).filter(Checklist.status == "pendente_aceite")
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

    return ok(
        {
            "imoveis_locados": imoveis.count(),
            "checklists_pendentes": checklists.count(),
            "problemas_abertos": problemas_abertos,
            "vistorias_agendadas": vistorias_agendadas,
        }
    )


_MSG_DATA = "Use uma data ISO 8601: AAAA-MM-DD ou AAAA-MM-DDTHH:MM:SS (fuso opcional, ex.: Z ou -03:00)"
_SO_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
_DATA_E_HORA = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}:\d{2})?")


def _instante(valor: str | None, fim_do_dia: bool = False) -> datetime | None:
    """Data ou data e hora ISO 8601 (só as duas formas da mensagem), em UTC sem fuso; None se vazia ou inválida.

    O created_at é gravado sem fuso pelo banco, em UTC (o padrão do Postgres do Render e do SQLite).
    Só a data, no fim do intervalo (`ate`), vale o dia inteiro: devolve o início do dia seguinte, que a
    consulta usa como limite exclusivo."""
    if not valor:
        return None
    texto = valor.strip()
    try:
        if _SO_DATA.fullmatch(texto):
            dia = date.fromisoformat(texto)
            inicio = datetime(dia.year, dia.month, dia.day)
            return inicio + timedelta(days=1) if fim_do_dia else inicio
        if not _DATA_E_HORA.fullmatch(texto):
            return None
        instante = datetime.fromisoformat(texto)
        if instante.tzinfo:
            instante = instante.astimezone(UTC).replace(tzinfo=None)
        # Com hora, o fim é inclusivo: o limite exclusivo fica um microssegundo depois
        return instante + timedelta(microseconds=1) if fim_do_dia else instante
    except (ValueError, OverflowError):  # data inexistente, ou nos limites do calendário (9999-12-31)
        return None


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
    # Só o admin: a trilha traz IP e horário de login de todas as contas e as tentativas de login contra
    # elas (SEC-018, decisão do PO em 2026-11-08)
    _: Usuario = Depends(require_roles("admin")),
):
    q = db.query(LogOperacao)
    if acao:
        q = q.filter(LogOperacao.acao == acao)
    if entidade:
        q = q.filter(LogOperacao.entidade == entidade)
    if usuario_id:
        q = q.filter(LogOperacao.usuario_id == usuario_id)
    # Data inválida responde 422 (SEC-020): ignorá-la devolveria o período todo a quem pediu um recorte
    erros = {}
    de_dt, ate_dt = _instante(de), _instante(ate, fim_do_dia=True)
    if de and de_dt is None:
        erros["de"] = _MSG_DATA
    if ate and ate_dt is None:
        erros["ate"] = _MSG_DATA
    if not erros and de_dt and ate_dt and de_dt >= ate_dt:
        erros["ate"] = "A data final não pode ser anterior à inicial"
    if erros:
        return fail("Filtro de data inválido", status_code=422, erros=erros)
    if de_dt:
        q = q.filter(LogOperacao.created_at >= de_dt)
    if ate_dt:
        q = q.filter(LogOperacao.created_at < ate_dt)

    q = q.order_by(LogOperacao.created_at.desc())
    items, pag = paginate(q, pagina, por_pagina)
    return ok(
        [
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
        ],
        pag,
    )
