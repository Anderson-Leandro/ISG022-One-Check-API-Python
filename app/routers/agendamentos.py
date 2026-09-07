from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import AgendamentoVistoria, Usuario
from app.schemas import AgendamentoUpdate, fail, ok
from app.serializers import log_operacao, serialize_agendamento

router = APIRouter(prefix="/agendamentos", tags=["agendamentos"])


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


@router.put("/{agendamento_id}")
def update_agendamento(
    agendamento_id: str,
    body: AgendamentoUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    ag = db.query(AgendamentoVistoria).filter(AgendamentoVistoria.id == agendamento_id).first()
    if not ag:
        return fail("Agendamento não encontrado")

    if body.tipo is not None:
        if body.tipo not in ("inicial", "encerramento"):
            return fail("Tipo inválido. Deve ser 'inicial' ou 'encerramento'")
        ag.tipo = body.tipo

    if body.data_agendada is not None:
        try:
            parsed_dt = _parse_datetime(body.data_agendada)
        except Exception:
            return fail("Formato de data_agendada inválido")
        now = datetime.now() if parsed_dt.tzinfo is None else datetime.now(timezone.utc)
        if parsed_dt <= now:
            return fail("A data agendada deve ser uma data futura")
        ag.data_agendada = parsed_dt.replace(tzinfo=None) if parsed_dt.tzinfo else parsed_dt

    if body.observacao is not None:
        ag.observacao = body.observacao

    db.commit()
    db.refresh(ag)
    log_operacao(db, user.id, "update", "agendamento_vistoria", ag.id)
    return ok(serialize_agendamento(ag))


@router.delete("/{agendamento_id}")
def delete_agendamento(
    agendamento_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    ag = db.query(AgendamentoVistoria).filter(AgendamentoVistoria.id == agendamento_id).first()
    if not ag:
        return fail("Agendamento não encontrado")

    db.delete(ag)
    db.commit()
    log_operacao(db, user.id, "delete", "agendamento_vistoria", agendamento_id)
    return ok(None)
