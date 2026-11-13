# Regras do sprint-executor neste projeto

> **Por que isso importa:** o `/sprint-executor` é uma skill global, usada em vários projetos. Este arquivo guarda
> o que só vale aqui. A skill lê este arquivo junto com o bloco `executor:` do `project.yaml` e com o `CLAUDE.md`.

## Testes
- A suíte roda numa cópia do projeto sem o arquivo de segredos, com `bash scripts/testes_na_copia.sh <scratchpad>/testes [argumentos do pytest]` (TK-022). O script copia o projeto sem `.env`, `.venv`, `.git`, `uploads`, `*.db`, `__pycache__` e as notas locais, cria o venv só na primeira vez (ou quando os requisitos mudam) e roda o pytest. Se a limpeza do scratchpad apagar o diretório, o mesmo comando recria tudo; o `--so-copiar` só atualiza a cópia, sem criar o venv.
- Produção usa PostgreSQL e os testes locais, SQLite. Item que mexe em SQL próprio, triggers ou migrações roda também contra um PostgreSQL 16 temporário (container próprio, numa porta livre, removido no fim). Os containers do docker compose do usuário (`onecheck-api`, `onecheck-db`, portas 8000 e 5432) nunca são tocados.

## Produção e serviços externos
- Nada roda contra a API ou o banco do Render. Um teste em produção (como o do `X-Forwarded-For` no SEC-017) é pedido ao usuário, que o executa e devolve o resultado.
- O Dependabot só lê a configuração da branch padrão (`main`): o que depende dele só se prova depois da release.

## Documentação de cada item
- **Collection do Insomnia:** quando uma rota muda ou entra, atualize `docs/insomnia/gerar_collection.py`, gere com `python3 docs/insomnia/gerar_collection.py` e rode com `scripts/rodar_collection.sh` contra a API local da cópia (porta livre, nunca a 8000 do usuário). A pasta 00a (primeiro acesso) fica de fora da execução padrão, como documentado no TK-020.
- **Mudanças para o outro time:** `MUDANCAS_API_PARA_FRONT.md` (local, nunca no git). Atualize em toda etapa que mude algo visível para quem consome a API: o item novo entra na tabela da seção 1 com a marca **(novo)** e na seção "Novidades desde a última entrega". A cada nova entrega, o usuário avisa: a marca da última entrega muda de data e o `openapi.json` é exportado de novo.
- Fora desse arquivo, nada nos arquivos versionados fala do front (itens, achados, ADRs, README, registros, PRs).

## Fechamento
- O merge do item e o do PR de fechamento usam o título do PR com `(#n)` (DEBT-008); pela interface do GitHub, isso já sai assim (TK-021, `.github/repositorio.json`).
