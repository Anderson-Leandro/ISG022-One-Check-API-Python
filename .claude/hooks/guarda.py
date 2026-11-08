#!/usr/bin/env python3
"""Hook PreToolUse do projeto: bloqueia o que nunca deve acontecer, mesmo no modo automático.

- ler o .env (segredos locais), pela ferramenta Read ou por comando de shell;
- commit ou push direto na dev ou na main (toda mudança vai por branch própria e PR);
- versionar MUDANCAS_API_PARA_FRONT.md ou PENDENCIAS_API.md (notas locais do time).

O comando é analisado como shell: o corpo dos heredocs (mensagens de commit, textos de PR) é
ignorado, e cada comando simples é checado pelo subcomando git de fato, não por palavras soltas.
Saída 2 bloqueia a ferramenta e devolve a mensagem de stderr ao Claude.
"""

import json
import re
import shlex
import subprocess
import sys

PROTEGIDAS = {"dev", "main"}
LOCAIS = ("MUDANCAS_API_PARA_FRONT.md", "PENDENCIAS_API.md")
# .env sozinho, sem sufixo (.env.example e .envrc passam)
ENV = re.compile(r"(?<![\w.-])\.env(?![\w.-])")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)", re.S)
SEPARADORES = re.compile(r"&&|\|\||[;|\n]")
# opções globais do git que consomem o argumento seguinte
OPCOES_COM_VALOR = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def bloquear(motivo: str) -> None:
    print(f"Bloqueado pelo hook do projeto (.claude/hooks/guarda.py): {motivo}", file=sys.stderr)
    sys.exit(2)


def branch_atual() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except Exception:
        return ""


def sem_heredocs(cmd: str) -> str:
    return HEREDOC.sub("<<heredoc", cmd)


def tokens(trecho: str) -> list[str]:
    try:
        return shlex.split(trecho, comments=True)
    except ValueError:
        return trecho.split()


def subcomando_git(tks: list[str]) -> tuple[str, list[str]] | None:
    """('push', [args]) se o trecho for um comando git; ignora VAR=x, sudo, env e opções globais."""
    i = 0
    while i < len(tks) and (re.fullmatch(r"\w+=.*", tks[i]) or tks[i] in ("sudo", "env", "command", "exec")):
        i += 1
    if i >= len(tks) or tks[i].rsplit("/", 1)[-1] != "git":
        return None
    i += 1
    while i < len(tks) and tks[i].startswith("-"):
        i += 2 if tks[i] in OPCOES_COM_VALOR else 1
    if i >= len(tks):
        return None
    return tks[i], tks[i + 1 :]


def destino(refspec: str) -> str:
    ref = refspec.lstrip("+")
    ref = ref.split(":", 1)[1] if ":" in ref else ref
    return re.sub(r"^refs/heads/", "", ref)


def checar_push(args: list[str]) -> None:
    if any(a in ("--all", "--mirror") for a in args):
        bloquear("push de todas as branches (--all/--mirror). Publique só a branch do item.")
    posicionais, pular = [], False
    for a in args:
        if pular:
            pular = False
            continue
        if a in ("-o", "--push-option", "--repo", "--receive-pack", "--exec"):
            pular = True
            continue
        if not a.startswith("-"):
            posicionais.append(a)
    refspecs = posicionais[1:]  # o primeiro é o remoto
    alvos = {destino(r) for r in refspecs} if refspecs else {branch_atual()}
    if alvos & PROTEGIDAS:
        bloquear("push direto para a dev ou a main. Publique a branch do item e abra um PR.")


def checar_bash(cmd: str) -> None:
    cmd = sem_heredocs(cmd)

    # Excluir o .env de uma cópia (rsync/tar --exclude .env) não é leitura
    sem_exclusoes = re.sub(r"--exclude[= ]['\"]?\.env['\"]?", "", cmd)
    if ENV.search(sem_exclusoes):
        bloquear("o comando cita o arquivo .env, que guarda segredos locais e não deve ser lido.")

    for trecho in SEPARADORES.split(cmd):
        git = subcomando_git(tokens(trecho.strip()))
        if not git:
            continue
        sub, args = git
        if sub == "commit" and branch_atual() in PROTEGIDAS:
            bloquear(f"commit direto na branch '{branch_atual()}'. Crie uma branch tipo/ID-descricao a partir da dev.")
        elif sub == "push":
            checar_push(args)
        elif sub == "add" and any(a.rsplit("/", 1)[-1] in LOCAIS for a in args):
            bloquear("MUDANCAS_API_PARA_FRONT.md e PENDENCIAS_API.md são notas locais e não entram no git.")


def main() -> None:
    try:
        dados = json.load(sys.stdin)
    except Exception:
        return
    ferramenta = dados.get("tool_name", "")
    entrada = dados.get("tool_input", {}) or {}
    if ferramenta in ("Read", "Edit", "Write", "Grep"):
        caminho = entrada.get("file_path") or entrada.get("path") or ""
        if ENV.search(caminho.rsplit("/", 1)[-1]):
            bloquear("o arquivo .env guarda segredos locais e não deve ser lido nem alterado.")
    elif ferramenta == "Bash":
        checar_bash(entrada.get("command", ""))


if __name__ == "__main__":
    main()
