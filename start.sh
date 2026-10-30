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

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
