#!/usr/bin/env python3
"""Confere a Definition of Done de um item do backlog contra os fatos do git e do GitHub.

Uso: python3 scripts/dod_check.py <ID> [--antes-do-merge]

Sem --antes-do-merge (padrão, depois do merge), confere:
  1. o item existe, está done e tem evidências e PR registrados;
  2. cada PR do item foi mesclado na dev, com todos os checks do CI em SUCCESS;
  3. a branch de pelo menos um PR leva o ID do item (tipo/ID-descricao);
  4. se o PR mexe em app/, o diff também mexe em tests/;
  5. se o PR altera ou remove um teste que já existia, o registro de execução traz o relatório
     com cada arquivo e a aprovação do usuário;
  6. o registro de execução docs/roadmap/execucao/<ID>.md existe com as seções obrigatórias,
     incluindo o resultado da security-audit;
  7. a issue do item está fechada;
  8. a sprint do item tem uma linha de acompanhamento citando o ID;
  9. o backlog valida sem erros.

Com --antes-do-merge, confere o PR aberto da branch atual (itens 3 a 6) antes de pedir o merge.
Sai com 1 se alguma verificação falhar.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
SECOES = ["## Entrega", "## Testes", "## Segurança", "## Testes existentes alterados", "## Documentação"]
resultados: list[tuple[bool, str]] = []


def ok(cond: bool, msg: str) -> bool:
    resultados.append((bool(cond), msg))
    return bool(cond)


def sh(*args: str) -> str:
    r = subprocess.run(args, cwd=RAIZ, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def gh_json(*args: str):
    return json.loads(sh("gh", *args))


def item_do_backlog(iid: str) -> dict | None:
    itens = yaml.safe_load((RAIZ / "docs/roadmap/backlog.yaml").read_text())["items"]
    return next((i for i in itens if i["id"] == iid), None)


def testes_alterados(pr: dict) -> list[str]:
    """Arquivos de teste do PR que já existiam antes dele (alterados ou removidos)."""
    base = pr.get("mergeCommit", {}) or {}
    ref = f"{base['oid']}^1" if base.get("oid") else f"origin/{pr['baseRefName']}"
    alterados = []
    for f in pr["files"]:
        caminho = f["path"]
        if not caminho.startswith("tests/") or not caminho.endswith(".py"):
            continue
        existia = subprocess.run(
            ["git", "cat-file", "-e", f"{ref}:{caminho}"], cwd=RAIZ, capture_output=True
        ).returncode == 0
        if existia and f.get("deletions", 0) > 0:
            alterados.append(caminho)
    return alterados


def conferir_pr(iid: str, numero: str, registro: str, depois_do_merge: bool) -> None:
    campos = "number,state,baseRefName,headRefName,mergeCommit,statusCheckRollup,files"
    pr = gh_json("pr", "view", numero, "--json", campos)
    rotulo = f"PR #{pr['number']}"
    if depois_do_merge:
        ok(pr["state"] == "MERGED" and pr["baseRefName"] == "dev", f"{rotulo} mesclado na dev")
    else:
        ok(pr["baseRefName"] == "dev", f"{rotulo} aponta para a dev")
    checks = pr.get("statusCheckRollup") or []
    ruins = [c.get("name") for c in checks if c.get("conclusion") != "SUCCESS"]
    ok(checks and not ruins, f"{rotulo}: CI verde" + (f" (pendente ou falho: {', '.join(ruins)})" if ruins else ""))
    ok(iid.lower() in pr["headRefName"].lower(), f"{rotulo}: branch '{pr['headRefName']}' leva o ID")

    arquivos = [f["path"] for f in pr["files"]]
    if any(a.startswith("app/") for a in arquivos):
        ok(any(a.startswith("tests/") for a in arquivos), f"{rotulo}: muda app/ e traz testes")

    alterados = testes_alterados(pr)
    if alterados:
        secao = registro.split("## Testes existentes alterados", 1)[-1].split("\n## ", 1)[0]
        faltando = [a for a in alterados if a not in secao]
        ok(not faltando, f"{rotulo}: relatório cita cada teste existente alterado"
           + (f" (faltam: {', '.join(faltando)})" if faltando else ""))
        ok(re.search(r"Aprovado por:\s*\S+.*\d{4}-\d{2}-\d{2}", secao),
           f"{rotulo}: alteração de testes existentes aprovada pelo usuário (linha 'Aprovado por: <nome> em AAAA-MM-DD')")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    iid = args[0].upper()
    depois = "--antes-do-merge" not in sys.argv

    item = item_do_backlog(iid)
    if not ok(item, f"{iid} existe no backlog"):
        return relatorio(iid)

    arq = RAIZ / f"docs/roadmap/execucao/{iid}.md"
    registro = arq.read_text() if arq.exists() else ""
    if ok(registro, f"registro de execução {arq.relative_to(RAIZ)}"):
        for s in SECOES:
            corpo = registro.split(s, 1)[-1].split("\n## ", 1)[0].strip() if s in registro else ""
            ok(corpo and "<!--" not in corpo[:4], f"registro: seção '{s[3:]}' preenchida")
        seg = registro.split("## Segurança", 1)[-1].split("\n## ", 1)[0]
        rodou = re.search(r"security-audit", seg, re.I) and not re.search(r"n[ãa]o foi rodad|pendente", seg, re.I)
        ok(rodou, "registro: security-audit rodada e com resultado (sem 'não foi rodada' ou 'pendente')")

    if depois:
        prs = [str(p).lstrip("#") for p in (item.get("links", {}) or {}).get("prs", []) or []]
        ok(item.get("status") == "done", f"{iid} está done (status: {item.get('status')})")
        ok(item.get("evidence"), f"{iid} tem evidências registradas")
        ok(prs, f"{iid} tem PR registrado em links.prs")
    else:
        branch = sh("git", "rev-parse", "--abbrev-ref", "HEAD").strip()
        abertos = gh_json("pr", "list", "--head", branch, "--state", "open", "--json", "number")
        prs = [str(p["number"]) for p in abertos]
        ok(prs, f"PR aberto para a branch {branch}")

    for numero in prs:
        try:
            conferir_pr(iid, numero, registro, depois)
        except RuntimeError as e:
            ok(False, f"PR #{numero}: {e}")

    if depois:
        issue = (item.get("links", {}) or {}).get("gh_issue")
        if ok(issue, f"{iid} ligado a uma issue"):
            estado = gh_json("issue", "view", str(issue), "--json", "state")["state"]
            ok(estado == "CLOSED", f"issue #{issue} fechada (estado: {estado})")
        sprint = item.get("sprint")
        if sprint:
            md = RAIZ / f"docs/roadmap/sprints/sprint-{int(sprint):02d}.md"
            acomp = md.read_text().split("## Acompanhamento", 1)[-1].split("\n## ", 1)[0] if md.exists() else ""
            ok(iid in acomp, f"acompanhamento da Sprint {sprint} cita {iid}")

    validar = subprocess.run(
        ["python3", str(Path.home() / ".claude/skills/_roadmap-shared/scripts/backlog.py"), "--root", str(RAIZ), "validate"],
        capture_output=True, text=True,
    )
    ok(validar.returncode == 0, "backlog valida sem erros")
    return relatorio(iid)


def relatorio(iid: str) -> int:
    falhas = [m for passou, m in resultados if not passou]
    print(f"DoD de {iid}: {len(resultados) - len(falhas)}/{len(resultados)} verificações")
    for passou, msg in resultados:
        print(f"  {'✓' if passou else '✗'} {msg}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
