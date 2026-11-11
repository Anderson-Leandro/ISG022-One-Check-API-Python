"""Retenção de dados (LGPD, art. 15 e 16): apaga o que já não tem finalidade."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import LOG_RETENCAO_DIAS
from app.log_append_only import exclusao_autorizada
from app.models import LogOperacao, RefreshToken


def limpar_dados_vencidos(db: Session) -> dict[str, int]:
    """Refresh tokens vencidos e eventos de log_operacao mais antigos que LOG_RETENCAO_DIAS."""
    agora = datetime.now(UTC).replace(tzinfo=None)
    tokens = db.query(RefreshToken).filter(RefreshToken.expires_at < agora).delete(synchronize_session=False)
    limite = agora - timedelta(days=LOG_RETENCAO_DIAS)
    # log_operacao é append-only (SEC-025): só esta transação pode apagar
    with exclusao_autorizada(db, "retencao"):
        logs = db.query(LogOperacao).filter(LogOperacao.created_at < limite).delete(synchronize_session=False)
    db.commit()
    return {"refresh_tokens": tokens, "logs": logs}
