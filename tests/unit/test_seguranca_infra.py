"""
Segurança — SEC-008, SEC-009 e SEC-016: container, CI e arquivos versionados

Cenários originais:
  - SEC-008: o container rodava como root, com gcc e headers de compilação na
    imagem final; o CI usava actions por tag mutável (@v4) e o GITHUB_TOKEN com
    as permissões padrão.
  - SEC-009: onecheck.db (com hashes de senha e segredo TOTP) versionado num
    repositório público, apesar do *.db no .gitignore.
  - SEC-016: cópias antigas e vulneráveis de auth.py e routers/ na raiz, que a
    aplicação não carrega, mas confundem a leitura e os scanners.

Regras verificadas por leitura estática dos arquivos de deploy e do índice do git.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
SHA = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")


def _dockerfile() -> str:
    """Instruções do Dockerfile, sem as linhas de comentário."""
    linhas = (RAIZ / "Dockerfile").read_text().splitlines()
    return "\n".join(l for l in linhas if not l.lstrip().startswith("#"))


def _workflows() -> list[dict]:
    return [yaml.safe_load(p.read_text()) for p in sorted((RAIZ / ".github" / "workflows").glob("*.yml"))]


def _versionados() -> list[str]:
    if not shutil.which("git") or not (RAIZ / ".git").exists():
        pytest.skip("fora de um repositório git")
    r = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True)
    return r.stdout.splitlines()


class TestContainer:
    def test_roda_sem_root(self):
        usuarios = re.findall(r"^USER\s+(\S+)", _dockerfile(), re.M)
        assert usuarios, "Dockerfile sem USER"
        assert usuarios[-1] not in ("root", "0")

    def test_sem_ferramentas_de_compilacao(self):
        assert not re.search(r"\b(gcc|build-essential|-dev)\b", _dockerfile())

    def test_so_instala_pacotes_binarios_com_hash(self):
        instalacao = [l for l in _dockerfile().splitlines() if "pip install" in l]
        assert instalacao and all("--require-hashes" in l and "--only-binary" in l for l in instalacao)


class TestCI:
    def test_actions_fixadas_por_sha(self):
        usos = [passo["uses"] for wf in _workflows() for job in wf["jobs"].values()
                for passo in job.get("steps", []) if "uses" in passo]
        assert usos
        assert [u for u in usos if not SHA.match(u)] == []

    def test_token_so_leitura(self):
        for wf in _workflows():
            assert wf.get("permissions") == {"contents": "read"}
            for job in wf["jobs"].values():
                assert job.get("permissions", {"contents": "read"}) == {"contents": "read"}


class TestArquivosVersionados:
    def test_nenhum_banco_versionado(self):
        assert [f for f in _versionados() if f.endswith((".db", ".sqlite", ".sqlite3"))] == []

    def test_sem_copias_antigas_na_raiz(self):
        assert [f for f in _versionados() if f == "auth.py" or f.startswith("routers/")] == []
        assert not (RAIZ / "auth.py").exists() and not (RAIZ / "routers").exists()

    def test_sem_bytecode_versionado(self):
        assert [f for f in _versionados() if f.endswith(".pyc") or "__pycache__/" in f] == []
