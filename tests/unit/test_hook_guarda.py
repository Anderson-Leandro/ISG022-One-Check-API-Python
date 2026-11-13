"""
Hook do projeto (.claude/hooks/guarda.py)

Barreira do Claude Code contra: ler o .env, commit ou push direto na dev/main e versionar as
notas locais. Os casos marcados com (regressão) falhavam na primeira versão, que procurava
palavras soltas no comando inteiro, inclusive dentro de mensagens de commit.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / ".claude/hooks/guarda.py"
_spec = importlib.util.spec_from_file_location("guarda", HOOK)
guarda = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guarda)


def _rodar(ferramenta: str, entrada: dict) -> int:
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": ferramenta, "tool_input": entrada}),
        capture_output=True,
        text=True,
    )
    return r.returncode


def _bash(cmd: str, branch: str, monkeypatch) -> bool:
    """True se o comando é bloqueado, com a branch atual simulada."""
    monkeypatch.setattr(guarda, "branch_atual", lambda: branch)
    with pytest.raises(SystemExit) as fim:
        guarda.checar_bash(cmd)
        raise SystemExit(0)
    return fim.value.code == 2


# ── Push ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "cmd",
    [
        "git push origin dev",
        "git push origin main",
        "git push -u origin HEAD:main",
        "git push origin +dev",
        "git push origin refs/heads/main",
        "git push origin chore/x:dev",
        "git push --all origin",
        "git -C /repo push origin dev",
        "git status && git push origin dev",
        "git push origin dev\necho push concluido",  # (regressão) falso negativo
    ],
)
def test_push_para_branch_protegida_e_bloqueado(cmd, monkeypatch):
    assert _bash(cmd, "chore/x", monkeypatch)


@pytest.mark.parametrize(
    "cmd",
    [
        "git push -u origin chore/sprint-executor",
        "git push origin test/SEC-032-negacao-checklists 2>&1 | grep -v remote",
        "git push origin feat/dev-tools",
        "gh pr create --base dev --title x",
        "git switch dev && git pull --ff-only",
        "git commit -F - <<'EOF'\nchore: commit ou push direto na dev e main\nEOF\ngit push -u origin chore/x",  # (regressão)
        "git switch -c fix/hook-guarda-push dev",  # (regressão) nome de branch com push
    ],
)
def test_push_da_branch_do_item_passa(cmd, monkeypatch):
    assert not _bash(cmd, "chore/x", monkeypatch)


def test_push_sem_refspec_na_branch_protegida_e_bloqueado(monkeypatch):
    assert _bash("git push", "dev", monkeypatch)
    assert _bash("git push -u origin", "main", monkeypatch)


def test_push_sem_refspec_na_branch_do_item_passa(monkeypatch):
    assert not _bash("git push", "chore/x", monkeypatch)


# ── Commit ──────────────────────────────────────────────────────────────────────


def test_commit_na_branch_protegida_e_bloqueado(monkeypatch):
    assert _bash("git commit -m x", "dev", monkeypatch)
    assert _bash("git add . && git commit -F msg.txt", "main", monkeypatch)


def test_commit_na_branch_do_item_passa(monkeypatch):
    assert not _bash("git commit -m 'merge na dev'", "chore/x", monkeypatch)


def test_texto_com_commit_fora_do_git_passa(monkeypatch):
    assert not _bash("echo 'git commit na dev'", "dev", monkeypatch)


# ── Notas locais ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "cmd",
    [
        "git add MUDANCAS_DE_CONTRATO.md",
        "git add -f PENDENCIAS_API.md",
        "git add docs ./MUDANCAS_DE_CONTRATO.md",
    ],
)
def test_add_das_notas_locais_e_bloqueado(cmd, monkeypatch):
    assert _bash(cmd, "chore/x", monkeypatch)


def test_add_de_outros_arquivos_passa(monkeypatch):
    assert not _bash("git add docs tests", "chore/x", monkeypatch)


# ── .env ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cmd", ["cat .env", "grep JWT .env", "source ./.env"])
def test_comando_que_cita_o_env_e_bloqueado(cmd, monkeypatch):
    assert _bash(cmd, "chore/x", monkeypatch)


@pytest.mark.parametrize(
    "cmd",
    [
        "cat .env.example",
        "rsync -a --exclude .env --exclude .venv ./ /tmp/copia/",
        "git commit -F - <<EOF\nsem citar o .env\nEOF",
    ],
)
def test_env_example_exclusao_e_heredoc_passam(cmd, monkeypatch):
    assert not _bash(cmd, "chore/x", monkeypatch)


def test_ferramentas_de_arquivo_nao_abrem_o_env():
    assert _rodar("Read", {"file_path": "/repo/.env"}) == 2
    assert _rodar("Edit", {"file_path": "/repo/.env"}) == 2
    assert _rodar("Read", {"file_path": "/repo/.env.example"}) == 0
    assert _rodar("Read", {"file_path": "/repo/README.md"}) == 0


def test_entrada_invalida_nao_bloqueia():
    r = subprocess.run([sys.executable, str(HOOK)], input="não é json", capture_output=True, text=True)
    assert r.returncode == 0
