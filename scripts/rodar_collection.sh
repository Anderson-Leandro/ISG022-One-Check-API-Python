#!/usr/bin/env bash
# Roda a collection do Insomnia do zero contra uma API local descartável (TK-020).
#
# - sobe a API numa porta livre (nunca a 8000 do docker compose), com banco SQLite e uploads temporários;
# - roda o seed de desenvolvimento e monta as variáveis da collection num arquivo temporário (apagado no fim);
# - executa a collection com docs/insomnia/executar.mjs e para a API, mesmo quando falha.
#
# Uso: bash scripts/rodar_collection.sh            (pula a pasta 00a, de primeiro acesso)
#      PULAR= bash scripts/rodar_collection.sh     (roda tudo)
# Requer: Python com requirements.lock instalado e Node 18+.
set -euo pipefail
cd "$(dirname "$0")/.."
RAIZ="$(pwd)"
PY="${PYTHON:-python3}"
PULAR="${PULAR-00a}"

umask 077
TMP="$(mktemp -d)"
API_PID=""
limpar() {
  if [ -n "$API_PID" ]; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap limpar EXIT

PORTA="$("$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
[ "$PORTA" = "8000" ] && { echo "porta 8000 recusada" >&2; exit 1; }

# A API não lê o arquivo de configuração local (limites, segredos, banco): tudo o que ela usa vem daqui
export ONECHECK_SEM_DOTENV=1
export APP_ENV=development
export DATABASE_URL="sqlite:///$TMP/api.db"
export UPLOAD_DIR="$TMP/uploads"
export JWT_SECRET="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(48))')"
export SEED_SECRET="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(32))')"
export PUBLIC_BASE_URL="http://127.0.0.1:$PORTA"
export CORS_ORIGINS=""
export DOCS_ENABLED=false
export SEED_ALLOW_DESTRUCTIVE=false

"$PY" scripts/seed.py > "$TMP/seed.txt"
"$PY" - "$TMP/seed.txt" "$TMP/overrides.json" "$PORTA" <<'PY'
import json, re, secrets, sys, os
seed, saida, porta = sys.argv[1], sys.argv[2], sys.argv[3]
t = open(seed, encoding="utf-8").read()
def achar(padrao, o_que):
    m = re.search(padrao, t)
    if not m:
        sys.exit(f"saída do seed sem {o_que}: o formato de scripts/seed.py mudou?")
    return m.group(1)
def senha(email):
    return achar(re.escape(email) + r" / (\S+)", f"a senha de {email}")
json.dump({
    "base_url": f"http://127.0.0.1:{porta}/api/v1",
    "senha_admin": senha("admin@onecheck.local"),
    "senha_gestor": senha("gestor@onecheck.local"),
    "senha_vistoriador": senha("vistoriador@onecheck.local"),
    "mfa_secret": achar(r"MFA secret[^:]*: (\S+)", "o MFA secret"),
    "senha_teste": "Colecao." + secrets.token_urlsafe(9) + "#7",
    "seed_secret": os.environ["SEED_SECRET"],
}, open(saida, "w", encoding="utf-8"))
PY
rm -f "$TMP/seed.txt"

"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORTA" > "$TMP/api.log" 2>&1 &
API_PID=$!
for _ in $(seq 1 50); do
  curl -fs "http://127.0.0.1:$PORTA/api/v1/health" > /dev/null 2>&1 && break
  sleep 0.2
done
curl -fs "http://127.0.0.1:$PORTA/api/v1/health" > /dev/null || { echo "a API não subiu:" >&2; tail -20 "$TMP/api.log" >&2; exit 1; }

PULAR="$PULAR" node docs/insomnia/executar.mjs "$RAIZ/docs/insomnia/onecheck-api.insomnia.json" "$TMP/overrides.json" "$RAIZ/docs/insomnia/fixtures"
