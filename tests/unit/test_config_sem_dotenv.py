"""TK-020: ONECHECK_SEM_DOTENV=1 faz a API ignorar o arquivo de configuração local (execuções descartáveis)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
_SONDA = (
    "import dotenv\n"
    "chamadas = []\n"
    "dotenv.load_dotenv = lambda *a, **k: chamadas.append(1)\n"
    "import app.config\n"
    "print(len(chamadas))\n"
)


def _chamadas_ao_carregar(sem_dotenv: bool) -> int:
    env = {k: v for k, v in os.environ.items() if k != "ONECHECK_SEM_DOTENV"}
    env.update(APP_ENV="development")
    if sem_dotenv:
        env["ONECHECK_SEM_DOTENV"] = "1"
    r = subprocess.run([sys.executable, "-c", _SONDA], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return int(r.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize(("sem_dotenv", "esperado"), [(False, 1), (True, 0)])
def test_variavel_desliga_a_leitura_do_arquivo_local(sem_dotenv, esperado):
    assert _chamadas_ao_carregar(sem_dotenv) == esperado
