"""TK-022: scripts/testes_na_copia.sh roda a suíte numa cópia do projeto sem o arquivo de segredos.

Regras verificadas:
  - a cópia não leva o arquivo de segredos (nem variantes), as notas locais, o venv, o .git, uploads,
    bancos SQLite e caches; leva o .env.example e o código
  - a cópia acompanha a origem (arquivo apagado na origem some da cópia), e um arquivo excluído que já
    estivesse na cópia também sai
  - um destino dentro do projeto, ou que contém o projeto, é recusado (o rsync --delete apagaria a origem)
  - diretório vazio: cria o venv, instala como o CI (lock com hashes, depois os de teste) e roda o pytest com
    ONECHECK_SEM_DOTENV=1 e os argumentos dados
  - venv existente é reaproveitado; lock alterado ou venv quebrado recria o venv do zero
Um python falso registra as chamadas: nenhum pacote é instalado de verdade.
"""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "testes_na_copia.sh"

FORA_DA_COPIA = [
    ".env",
    ".env.local",
    "MUDANCAS_API_PARA_FRONT.md",
    "PENDENCIAS_API.md",
    ".venv/bin/python",
    ".git/HEAD",
    "uploads/foto.jpg",
    "onecheck.db",
    "dados.sqlite3",
    "prod.env",
    ".envrc",
    "coverage.xml",
    "app/__pycache__/x.pyc",
]
NA_COPIA = ["app/x.py", "tests/test_x.py", ".env.example", "requirements.lock", "requirements-test.txt"]


@pytest.fixture
def origem(tmp_path):
    raiz = tmp_path / "origem"
    for rel in FORA_DA_COPIA + NA_COPIA:
        arq = raiz / rel
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text("SEGREDO=nao-pode-sair\n" if "env" in rel else f"conteudo de {rel}\n")
    return raiz


@pytest.fixture
def python_falso(tmp_path):
    """python3 falso: '-m venv X' cria X/bin/python, que só registra as chamadas em chamadas.log.

    O python do venv responde ao teste de saúde (-c) sem registrar, e anota se ONECHECK_SEM_DOTENV=1.
    """
    log = tmp_path / "chamadas.log"
    venv_python = tmp_path / "venv_python"
    venv_python.write_text(
        f'#!/usr/bin/env bash\n[ "$1" = "-c" ] && exit 0\necho "venv-python[$ONECHECK_SEM_DOTENV] $*" >> "{log}"\n'
    )
    venv_python.chmod(0o755)
    py = tmp_path / "python3_falso"
    py.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "python3 $*" >> "{log}"\n'
        'if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then\n'
        f'  mkdir -p "$3/bin" && cp "{venv_python}" "$3/bin/python"\n'
        "fi\n"
    )
    py.chmod(0o755)
    return py, log


def _rodar(origem, destino, *args, python=None):
    env = {**os.environ, "ORIGEM": str(origem)}
    if python:
        env["PYTHON"] = str(python)
    return subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=60)


def _chamadas(log: Path) -> list[str]:
    return log.read_text().splitlines() if log.exists() else []


class TestCopia:
    def test_copia_sem_segredos_nem_notas_locais(self, origem, tmp_path):
        destino = tmp_path / "trabalho"
        r = _rodar(origem, destino, "--so-copiar", str(destino))
        assert r.returncode == 0, r.stderr
        proj = destino / "proj"
        for rel in FORA_DA_COPIA:
            assert not (proj / rel).exists(), f"{rel} não podia ir para a cópia"
        for rel in NA_COPIA:
            assert (proj / rel).exists(), f"{rel} devia ir para a cópia"

    def test_arquivo_apagado_na_origem_some_da_copia(self, origem, tmp_path):
        destino = tmp_path / "trabalho"
        _rodar(origem, destino, "--so-copiar", str(destino))
        (origem / "app/x.py").unlink()
        _rodar(origem, destino, "--so-copiar", str(destino))
        assert not (destino / "proj/app/x.py").exists()

    def test_arquivo_excluido_ja_na_copia_e_removido(self, origem, tmp_path):
        destino = tmp_path / "trabalho"
        (destino / "proj").mkdir(parents=True)
        (destino / "proj/.env").write_text("SEGREDO=antigo\n")
        (destino / "proj/PENDENCIAS_API.md").write_text("nota\n")
        _rodar(origem, destino, "--so-copiar", str(destino))
        assert not (destino / "proj/.env").exists()
        assert not (destino / "proj/PENDENCIAS_API.md").exists()

    def test_so_copiar_depois_do_diretorio_tambem_vale(self, origem, tmp_path, python_falso):
        py, log = python_falso
        destino = tmp_path / "trabalho"
        r = _rodar(origem, destino, str(destino), "--so-copiar", python=py)
        assert r.returncode == 0, r.stderr
        assert (destino / "proj/app/x.py").exists()
        assert _chamadas(log) == []

    def test_destino_que_contem_o_projeto_e_recusado(self, tmp_path):
        projeto = tmp_path / "x" / "proj"
        (projeto / "app").mkdir(parents=True)
        (projeto / "app/x.py").write_text("codigo\n")
        vizinho = tmp_path / "x" / "outro.txt"
        vizinho.write_text("fica\n")
        r = _rodar(projeto, tmp_path / "x", "--so-copiar", str(tmp_path / "x"))
        assert r.returncode != 0
        assert (projeto / "app/x.py").exists() and vizinho.exists()

    def test_destino_dentro_do_projeto_e_recusado(self, origem):
        destino = origem / "copia"
        r = _rodar(origem, destino, "--so-copiar", str(destino))
        assert r.returncode != 0
        assert not destino.exists()

    def test_sem_destino_mostra_o_uso(self, origem):
        r = _rodar(origem, None)
        assert r.returncode != 0
        assert "uso" in r.stderr.lower()


class TestVenv:
    def test_diretorio_vazio_cria_o_venv_instala_e_roda_o_pytest(self, origem, tmp_path, python_falso):
        py, log = python_falso
        destino = tmp_path / "trabalho"
        r = _rodar(origem, destino, str(destino), "-k", "algo", python=py)
        assert r.returncode == 0, r.stderr
        chamadas = _chamadas(log)
        assert any(c.startswith("python3 -m venv") for c in chamadas)
        instalacoes = [c for c in chamadas if "-m pip install" in c]
        assert "--require-hashes" in instalacoes[0] and instalacoes[0].endswith("requirements.lock")
        assert instalacoes[1].endswith("requirements-test.txt")
        assert chamadas[-1] == "venv-python[1] -m pytest -q -p no:cacheprovider -k algo"

    def test_venv_existente_e_reaproveitado(self, origem, tmp_path, python_falso):
        py, log = python_falso
        destino = tmp_path / "trabalho"
        _rodar(origem, destino, str(destino), python=py)
        log.write_text("")
        _rodar(origem, destino, str(destino), python=py)
        chamadas = _chamadas(log)
        assert not any("venv" in c and c.startswith("python3") for c in chamadas)
        assert not any("pip install" in c for c in chamadas)
        assert chamadas == ["venv-python[1] -m pytest -q -p no:cacheprovider"]

    def test_lock_alterado_recria_o_venv(self, origem, tmp_path, python_falso):
        py, log = python_falso
        destino = tmp_path / "trabalho"
        _rodar(origem, destino, str(destino), python=py)
        log.write_text("")
        (origem / "requirements.lock").write_text("pacote-novo==1.0 --hash=sha256:abc\n")
        _rodar(origem, destino, str(destino), python=py)
        chamadas = _chamadas(log)
        assert any(c.startswith("python3 -m venv") for c in chamadas)
        assert any("pip install" in c for c in chamadas)

    def test_venv_quebrado_e_recriado(self, origem, tmp_path, python_falso):
        py, log = python_falso
        destino = tmp_path / "trabalho"
        _rodar(origem, destino, str(destino), python=py)
        (destino / "venv/bin/python").write_text("#!/usr/bin/env bash\nexit 1\n")
        log.write_text("")
        r = _rodar(origem, destino, str(destino), python=py)
        assert r.returncode == 0, r.stderr
        assert any(c.startswith("python3 -m venv") for c in _chamadas(log))
