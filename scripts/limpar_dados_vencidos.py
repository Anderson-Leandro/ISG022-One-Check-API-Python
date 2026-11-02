"""Apaga refresh tokens vencidos e eventos de auditoria além da retenção (LOG_RETENCAO_DIAS).

Roda em todo start (start.sh). Para instâncias que ficam muito tempo no ar, agende
também como cron job (Render Cron Job ou cron do host):
    python scripts/limpar_dados_vencidos.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import LOG_RETENCAO_DIAS
from app.database import SessionLocal, ensure_schema_updates
from app.retencao import limpar_dados_vencidos


def main() -> int:
    # Roda antes do uvicorn: no primeiro start as tabelas ainda não existem
    ensure_schema_updates()
    with SessionLocal() as session:
        apagados = limpar_dados_vencidos(session)
    print(
        f"Limpeza: {apagados['refresh_tokens']} refresh token(s) vencido(s) e "
        f"{apagados['logs']} evento(s) de log com mais de {LOG_RETENCAO_DIAS} dias."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
