#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

PORT="${PORT:-8000}"

# Seed automático só em desenvolvimento. Em produção, o primeiro carregamento é feito
# por POST /api/v1/admin/seed (exige SEED_SECRET), que gera senhas aleatórias.
case "${APP_ENV,,}" in
  development|dev|local)
    python scripts/seed.py || echo "Aviso: seed falhou" >&2
    ;;
esac

# Refresh tokens vencidos e logs além de LOG_RETENCAO_DIAS (SEC-014). Uma falha não impede o start
python scripts/limpar_dados_vencidos.py || echo "Aviso: limpeza de dados vencidos falhou" >&2

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
