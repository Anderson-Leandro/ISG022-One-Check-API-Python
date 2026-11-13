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
- **Mudanças de contrato:** `MUDANCAS_DE_CONTRATO.md` (local, nunca no git). A API e o front são desenvolvidos juntos, e o arquivo guarda o que mudou no contrato (rotas, corpos, respostas, erros e regras visíveis para quem consome a API) e o estado de cada mudança nos dois lados.
  - Em toda etapa que mude o contrato, acrescente a linha na seção 1 ("Pendentes"), com o ID do item da API e o estado de cada lado.
  - Quando a mudança fica pronta nos dois lados, marque-a como feita, com a data e os IDs dos dois itens, e mova-a para "Concluídas".
  - A cada release, as concluídas saem do arquivo: o histórico fica no git e no CHANGELOG de cada projeto.
- **Trabalho que muda os dois lados:** cada repositório tem o próprio item no próprio backlog, e os dois se referenciam pelo ID. Os arquivos versionados da API descrevem o contrato e citam o ID do item da outra ponta, sem detalhes de implementação dela.

## Fechamento
- O merge do item e o do PR de fechamento usam o título do PR com `(#n)` (DEBT-008); pela interface do GitHub, isso já sai assim (TK-021, `.github/repositorio.json`).
