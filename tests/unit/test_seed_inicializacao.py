"""
Segurança — SEC-001: seed automático no start do container

Cenário original: start.sh rodava scripts/seed.py em todo start (Render e Docker)
e o seed criava contas com as senhas e o segredo TOTP publicados no repositório.

Regras verificadas:
  - start.sh só roda o seed em APP_ENV=development/dev/local
  - fora de desenvolvimento, scripts/seed.py não usa nenhuma credencial de demonstração

Cada caso roda num processo novo porque app.config é lido na importação.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PUBLICOS = ["admin123", "gestor123", "vistor123", "locat123", "JBSWY3DPEHPK3PXP"]


def _env(tmp_path, app_env: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "TEST_DATABASE_URL"}
    env.update({
        # Vazio explícito: o load_dotenv não sobrescreve variáveis já definidas
        "SEED_SECRET": "",
        "APP_ENV": app_env,
        "JWT_SECRET": "x" * 48,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'seed.db'}",
        "UPLOAD_DIR": str(tmp_path / "uploads"),
    })
    return env


def _seed(tmp_path, app_env: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/seed.py"], cwd=RAIZ, env=_env(tmp_path, app_env),
        capture_output=True, text=True, timeout=120,
    )


class TestScriptSeed:
    def test_producao_nao_usa_credenciais_publicas(self, tmp_path):
        r = _seed(tmp_path, "production")
        assert r.returncode == 0, r.stderr
        assert "admin@onecheck.local" in r.stdout
        for valor in PUBLICOS:
            assert valor not in r.stdout

    def test_segunda_execucao_nao_recria(self, tmp_path):
        _seed(tmp_path, "production")
        r = _seed(tmp_path, "production")
        assert "Seed ignorado" in r.stdout

    def test_desenvolvimento_mantem_credenciais_fixas(self, tmp_path):
        r = _seed(tmp_path, "development")
        assert r.returncode == 0, r.stderr
        assert "admin123" in r.stdout


class TestStartSh:
    @pytest.fixture
    def stubs(self, tmp_path):
        """python e uvicorn falsos que só registram a chamada."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        log = tmp_path / "chamadas.log"
        for nome in ("python", "uvicorn"):
            stub = bin_dir / nome
            stub.write_text(f'#!/usr/bin/env bash\necho "{nome} $*" >> "{log}"\n')
            stub.chmod(0o755)
        return bin_dir, log

    def _start(self, stubs, app_env: str | None) -> str:
        bin_dir, log = stubs
        env = {"PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": os.environ.get("HOME", "/tmp")}
        if app_env is not None:
            env["APP_ENV"] = app_env
        r = subprocess.run(["bash", "start.sh"], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, r.stderr
        return log.read_text()

    @pytest.mark.parametrize("app_env", [None, "production", "staging"])
    def test_fora_de_desenvolvimento_nao_roda_seed(self, stubs, app_env):
        chamadas = self._start(stubs, app_env)
        assert "seed.py" not in chamadas
        assert "uvicorn app.main:app" in chamadas

    @pytest.mark.parametrize("app_env", ["development", "Dev", "local"])
    def test_em_desenvolvimento_roda_seed(self, stubs, app_env):
        assert "python scripts/seed.py" in self._start(stubs, app_env)
