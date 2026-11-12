"""
DEBT-005 — Dependabot para pip e GitHub Actions (OWASP A06:2021)

O .github/dependabot.yml cobre os dois ecossistemas e abre os PRs contra a dev, para passarem pelo CI
que exige o requirements.lock com hash e coerente com o requirements.txt. As actions continuam fixadas
por SHA: o Dependabot troca o SHA e o comentário de versão juntos.
"""

import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = yaml.safe_load((RAIZ / ".github/dependabot.yml").read_text(encoding="utf-8"))


def _atualizacao(ecossistema):
    [u] = [u for u in CONFIG["updates"] if u["package-ecosystem"] == ecossistema]
    return u


def test_versao_2_com_pip_github_actions_e_docker():
    assert CONFIG["version"] == 2
    assert {u["package-ecosystem"] for u in CONFIG["updates"]} == {"pip", "github-actions", "docker"}


@pytest.mark.parametrize("ecossistema", ["pip", "github-actions", "docker"])
def test_prs_contra_a_dev_na_raiz_com_agenda(ecossistema):
    u = _atualizacao(ecossistema)
    assert u["target-branch"] == "dev"
    assert u["directory"] == "/"
    assert u["schedule"]["interval"] in {"daily", "weekly", "monthly"}


@pytest.mark.parametrize("ecossistema", ["pip", "github-actions", "docker"])
def test_cooldown_contra_versao_recem_publicada(ecossistema):
    assert _atualizacao(ecossistema)["cooldown"]["default-days"] >= 7


def test_pip_acha_o_requirements_que_o_lock_trava():
    """O Dependabot pip lê requirements.txt na raiz; o lock é regenerado a partir dele."""
    assert (RAIZ / "requirements.txt").exists()
    cabecalho = (RAIZ / "requirements.lock").read_text(encoding="utf-8").split("\n\n", 1)[0]
    assert "uv pip compile requirements.txt" in cabecalho and "--generate-hashes" in cabecalho


def test_ci_roda_nas_branches_do_dependabot_e_instala_pelo_lock_com_hash():
    """Os checks obrigatórios rodam em qualquer push, inclusive nas branches do Dependabot. Um PR que muda o
    requirements.txt sem regenerar o lock falha em test_lockfile_coerente_com_requirements."""
    ci = yaml.safe_load((RAIZ / ".github/workflows/tests.yml").read_text(encoding="utf-8"))
    gatilhos = ci.get("on", ci.get(True))
    assert "push" in gatilhos and not (gatilhos["push"] or {}).get("branches")
    instalacao = " ".join(p.get("run", "") for p in ci["jobs"]["test"]["steps"])
    assert "--require-hashes -r requirements.lock" in instalacao


def test_actions_fixadas_por_sha_com_comentario_de_versao():
    usos = re.findall(r"uses:\s*(\S+)(.*)", (RAIZ / ".github/workflows/tests.yml").read_text(encoding="utf-8"))
    assert usos
    for acao, resto in usos:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", acao), acao
        assert re.search(r"#\s*v\d", resto), acao


def test_docker_com_o_mesmo_prefixo_de_commit():
    # DEBT-021: os PRs do Dependabot para a imagem base seguem o padrão dos outros ecossistemas
    u = _atualizacao("docker")
    assert u["commit-message"]["prefix"] == "chore(deps)"
