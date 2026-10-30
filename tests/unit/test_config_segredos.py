"""
Segurança — N8: segredos com valor padrão

Cenário original: sem JWT_SECRET, a API assinava tokens com o valor público
"onecheck-dev-secret-change-me". Qualquer deploy sem a variável aceitava tokens
forjados por quem lesse o repositório (inclusive com role admin).

Regras verificadas (fora de APP_ENV=development/test):
  - JWT_SECRET ausente, público ou com menos de 32 caracteres impede a inicialização
  - SEED_SECRET, quando definido, também precisa ter 32+ caracteres
Em desenvolvimento, sem JWT_SECRET a API gera um valor aleatório por processo.

Cada caso roda num processo novo porque app.config é lido na importação.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FORTE = "x" * 48
PUBLICOS = ["onecheck-dev-secret-change-me", "sua_chave_secreta_jwt_super_segura"]


def _importa_config(**env) -> subprocess.CompletedProcess:
    base = {k: v for k, v in os.environ.items() if k not in ("APP_ENV", "JWT_SECRET", "SEED_SECRET")}
    # Valores vazios explícitos: o load_dotenv não sobrescreve variáveis já definidas
    base.update({"APP_ENV": "", "JWT_SECRET": "", "SEED_SECRET": ""})
    base.update(env)
    return subprocess.run(
        [sys.executable, "-c", "from app import config; print(config.JWT_SECRET)"],
        cwd=RAIZ, env=base, capture_output=True, text=True, timeout=60,
    )


class TestProducao:
    def test_sem_jwt_secret_nao_inicia(self):
        r = _importa_config()
        assert r.returncode != 0
        assert "JWT_SECRET" in r.stderr

    @pytest.mark.parametrize("valor", PUBLICOS)
    def test_jwt_secret_publico_nao_inicia(self, valor):
        assert _importa_config(JWT_SECRET=valor).returncode != 0

    def test_jwt_secret_curto_nao_inicia(self):
        assert _importa_config(JWT_SECRET="curto-demais").returncode != 0

    def test_jwt_secret_forte_inicia(self):
        r = _importa_config(JWT_SECRET=FORTE)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == FORTE

    def test_app_env_production_explicito(self):
        assert _importa_config(APP_ENV="production").returncode != 0

    def test_seed_secret_curto_nao_inicia(self):
        r = _importa_config(JWT_SECRET=FORTE, SEED_SECRET="seed-curto")
        assert r.returncode != 0
        assert "SEED_SECRET" in r.stderr

    def test_seed_secret_forte_inicia(self):
        assert _importa_config(JWT_SECRET=FORTE, SEED_SECRET="s" * 40).returncode == 0


class TestDesenvolvimento:
    @pytest.mark.parametrize("app_env", ["development", "test"])
    def test_sem_jwt_secret_gera_valor_aleatorio(self, app_env):
        r1 = _importa_config(APP_ENV=app_env)
        r2 = _importa_config(APP_ENV=app_env)
        assert r1.returncode == 0, r1.stderr
        s1, s2 = r1.stdout.strip(), r2.stdout.strip()
        assert len(s1) >= 32 and s1 != s2
        assert s1 not in PUBLICOS

    def test_valor_publico_e_substituido(self):
        r = _importa_config(APP_ENV="development", JWT_SECRET=PUBLICOS[0])
        assert r.returncode == 0
        assert r.stdout.strip() != PUBLICOS[0]

    def test_valor_proprio_e_mantido(self):
        r = _importa_config(APP_ENV="development", JWT_SECRET="segredo-local")
        assert r.stdout.strip() == "segredo-local"
