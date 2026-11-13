#!/usr/bin/env bash
# Roda a suíte numa cópia do projeto sem o arquivo de segredos (TK-022).
#
# - copia o projeto para <dir>/proj sem o arquivo de segredos e variantes (salvo o .env.example), as notas
#   locais, o venv, o .git, uploads, bancos SQLite e caches. A cópia acompanha a origem (rsync --delete), e um
#   arquivo excluído que já estivesse na cópia também sai (--delete-excluded);
# - instala como o CI: requirements.lock com --require-hashes, depois requirements-test.txt. O venv em
#   <dir>/venv é reaproveitado e só é recriado do zero quando um desses arquivos muda ou ele está quebrado;
# - roda o pytest na cópia com ONECHECK_SEM_DOTENV=1 e os argumentos dados (padrão: a suíte completa, com a
#   cobertura do pytest.ini).
#
# Uso: bash scripts/testes_na_copia.sh <dir> [argumentos do pytest]
#      bash scripts/testes_na_copia.sh --so-copiar <dir>     (só atualiza a cópia)
# <dir> fica fora do projeto, por exemplo no scratchpad. Variáveis: ORIGEM (padrão: a raiz do projeto)
# e PYTHON (padrão: python3, usado só para criar o venv).
set -euo pipefail

SO_COPIAR=""
ARGS=()
for a in "$@"; do
  if [ "$a" = "--so-copiar" ]; then SO_COPIAR=1; else ARGS+=("$a"); fi
done
set -- "${ARGS[@]+"${ARGS[@]}"}"
if [ -z "${1:-}" ]; then
  echo "uso: bash scripts/testes_na_copia.sh [--so-copiar] <dir> [argumentos do pytest]" >&2
  exit 2
fi
DESTINO="$(realpath -m "$1")"
shift
ORIGEM="$(realpath "${ORIGEM:-$(dirname "$0")/..}")"
PY="${PYTHON:-python3}"

# O destino não pode ficar dentro do projeto, nem conter o projeto: o rsync --delete apagaria a origem
case "$DESTINO/" in
  "$ORIGEM"/*)
    echo "o destino ($DESTINO) não pode ficar dentro do projeto ($ORIGEM)" >&2
    exit 2
    ;;
esac
case "$ORIGEM/" in
  "$DESTINO"/*)
    echo "o destino ($DESTINO) não pode conter o projeto ($ORIGEM)" >&2
    exit 2
    ;;
esac

mkdir -p "$DESTINO/proj"
rsync -a --delete --delete-excluded \
  --include ".env.example" --exclude ".env" --exclude ".env.*" --exclude "*.env" --exclude ".envrc" \
  --exclude "MUDANCAS_DE_CONTRATO.md" --exclude "PENDENCIAS_API.md" \
  --exclude ".venv" --exclude ".git" --exclude "uploads" \
  --exclude "*.db" --exclude "*.db-journal" --exclude "*.sqlite" --exclude "*.sqlite3" \
  --exclude "__pycache__" --exclude ".pytest_cache" --exclude ".ruff_cache" \
  --exclude ".coverage" --exclude "coverage.xml" --exclude "htmlcov" \
  "$ORIGEM/" "$DESTINO/proj/"
[ -n "$SO_COPIAR" ] && exit 0

VENV="$DESTINO/venv"
REQUISITOS="$(cat "$DESTINO/proj/requirements.lock" "$DESTINO/proj/requirements-test.txt" | sha256sum | cut -d' ' -f1)"
if [ "$(cat "$VENV/.requisitos" 2>/dev/null || true)" != "$REQUISITOS" ] || ! "$VENV/bin/python" -c "" 2>/dev/null; then
  # do zero: um pacote que saiu dos requisitos não fica para trás, e um venv quebrado não é reaproveitado
  rm -rf "$VENV"
  "$PY" -m venv "$VENV"
  "$VENV/bin/python" -m pip install -q --require-hashes -r "$DESTINO/proj/requirements.lock"
  "$VENV/bin/python" -m pip install -q -r "$DESTINO/proj/requirements-test.txt"
  echo "$REQUISITOS" > "$VENV/.requisitos"
fi

cd "$DESTINO/proj"
ONECHECK_SEM_DOTENV=1 exec "$VENV/bin/python" -m pytest -q -p no:cacheprovider "$@"
