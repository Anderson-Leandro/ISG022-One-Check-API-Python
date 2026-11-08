#!/usr/bin/env python3
"""Hook PreToolUse do projeto: bloqueia o que nunca deve acontecer, mesmo no modo automático.

- ler o .env (segredos locais), pela ferramenta Read ou por comando de shell;
- commit ou push direto na dev ou na main (toda mudança vai por branch própria e PR);
- versionar MUDANCAS_API_PARA_FRONT.md ou PENDENCIAS_API.md (notas locais do time).

Saída 2 bloqueia a ferramenta e devolve a mensagem de stderr ao Claude.
"""
import json
import re
import subprocess
import sys

PROTEGIDAS = {"dev", "main"}
LOCAIS = ("MUDANCAS_API_PARA_FRONT.md", "PENDENCIAS_API.md")
# .env sozinho, sem sufixo (.env.example e .envrc passam)
ENV = re.compile(r"(?<![\w.-])\.env(?![\w.-])")


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


def checar_bash(cmd: str) -> None:
    # Excluir o .env de uma cópia (rsync/tar --exclude .env) não é leitura
    sem_exclusoes = re.sub(r"--exclude[= ]['\"]?\.env['\"]?", "", cmd)
    if ENV.search(sem_exclusoes):
        bloquear("o comando cita o arquivo .env, que guarda segredos locais e não deve ser lido.")

    if re.search(r"\bgit\b[^|;&]*\bcommit\b", cmd) and branch_atual() in PROTEGIDAS:
        bloquear(f"commit direto na branch '{branch_atual()}'. Crie uma branch tipo/ID-descricao a partir da dev.")

    push = re.search(r"\bgit\b[^|;&]*\bpush\b([^|;&]*)", cmd)
    if push:
        args = push.group(1)
        if re.search(r"(^|[\s:])(dev|main)(\s|$)", args) or (
            not re.search(r"\S", re.sub(r"-\S+", "", args).replace("origin", "")) and branch_atual() in PROTEGIDAS
        ):
            bloquear("push direto para a dev ou a main. Publique a branch do item e abra um PR.")

    if re.search(r"\bgit\b[^|;&]*\badd\b", cmd) and any(nome in cmd for nome in LOCAIS):
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
