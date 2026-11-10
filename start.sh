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

# --no-proxy-headers: o uvicorn não troca o client pelo primeiro item do X-Forwarded-For, que o
# cliente controla. O IP real sai do item do proxy, no app/ip_cliente.py (SEC-017, PROXY_SALTOS)
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --no-proxy-headers
