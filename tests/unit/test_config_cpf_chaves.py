"""
SEC-031 — CPF_CHAVES fora de desenvolvimento (como o JWT_SECRET, N8)

Fora de APP_ENV=development/test, a API não sobe sem uma chave do CPF de 32+ caracteres, nem com a chave
pública de desenvolvimento. Em desenvolvimento, sem valor, vale a chave pública fixa (o banco local
continua legível entre reinícios). Cada caso roda num processo novo porque app.config é lido na importação.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FORTE = "x" * 48


def _importa(**env) -> subprocess.CompletedProcess:
    base = {k: v for k, v in os.environ.items() if k not in ("APP_ENV", "JWT_SECRET", "SEED_SECRET", "CPF_CHAVES")}
    base.update({"APP_ENV": "", "JWT_SECRET": FORTE, "SEED_SECRET": "", "CPF_CHAVES": ""})
    base.update(env)
    return subprocess.run(
        [sys.executable, "-c", "from app import config; print(len(config.CPF_CHAVES))"],
        cwd=RAIZ,
        env=base,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize(
    "valor",
    ["", "curta", "onecheck-chave-de-desenvolvimento-do-cpf-publica", f"{FORTE},curta"],
)
def test_producao_sem_chave_forte_nao_inicia(valor):
    r = _importa(CPF_CHAVES=valor)
    assert r.returncode != 0
    assert "CPF_CHAVES" in r.stderr


def test_producao_com_chaves_fortes_inicia():
    r = _importa(CPF_CHAVES=f"{FORTE}, {'y' * 40}")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "2"


def test_desenvolvimento_sem_chave_usa_a_publica():
    r = _importa(APP_ENV="development", CPF_CHAVES="")
    assert r.returncode == 0, r.stderr
    assert "chave pública de desenvolvimento" in r.stderr
