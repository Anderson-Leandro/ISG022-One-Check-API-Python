# OneCheck API — instruções para o Claude

API FastAPI da OneCheck (vistorias de imóveis). Gestão ágil em `docs/roadmap/` (fonte da verdade), espelhada
nas Issues do GitHub. Convenções da API no `README.md`; decisões em `docs/adr/`.

## Modo de execução da sprint
A execução segue a skill global `/sprint-executor` (`~/.claude/skills/sprint-executor/`), com os comandos do bloco
`executor:` de `docs/roadmap/project.yaml` e as regras deste projeto em `docs/roadmap/executor.md`. O modo vem do
argumento e vale só para aquela execução:
- `/sprint-executor [ID]` (padrão, `confirmar cada item`): um item por vez, até o PR aberto com o CI verde.
  **O merge é do usuário.**
- `/sprint-executor [ID] --continuo` (`contínuo`): item a item sem parar, com o merge feito depois do CI verde,
  até um ponto de parada.

## Regras permanentes
- **Branch por mudança:** toda mudança numa branch `tipo/ID-descricao` a partir da `dev`, integrada por PR
  (sem aprovação obrigatória de outra pessoa). Nunca commit ou push direto na `dev` ou na `main`.
- **Commit, PR e merge:** só quando o usuário pedir, ou dentro do fluxo do `sprint-executor` (merge só com
  `--continuo`). Não reescrever histórico (sem `rebase` de branch publicada, `push --force` ou `reset` de commits
  publicados).
- **Segredos:** nunca ler, imprimir ou copiar o `.env`. Ao citar um segredo, só os 4 primeiros caracteres + `****`.
- **Produção:** nada roda contra a API ou o banco do Render. Containers e volumes do docker compose do usuário
  (porta 8000) não são tocados sem confirmação.
- **Notas locais:** `MUDANCAS_DE_CONTRATO.md` e `PENDENCIAS_API.md` nunca entram no git.
- **Testes:** rodam numa cópia do projeto no scratchpad, sem `.env`, com
  `bash scripts/testes_na_copia.sh <scratchpad>/testes` (TK-022). Teste existente alterado ou removido exige
  relatório (arquivo, antes, depois, motivo, se quebra o comportamento atual) e aprovação do usuário antes do
  commit.
- **Board:** board-sync sempre em dry-run primeiro.
- **Atribuição:** commits terminam com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; PRs com
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## Barreiras automáticas
`.claude/hooks/guarda.py` (hook PreToolUse em `.claude/settings.json`) bloqueia: leitura do `.env`, commit ou
push direto na `dev`/`main` e `git add` das notas locais. Um comando que só cita `.env` também é bloqueado:
reescreva sem citar o arquivo.

No GitHub, o ruleset `.github/rulesets/protecao-branches.json` (TK-017) recusa push direto, force-push e
exclusão na `main` e na `dev`, e exige os checks `test` e `dependencias` para o merge.

## Conferência
`python3 scripts/dod_check.py <ID>` confere a Definition of Done de um item (PR mesclado com CI verde, branch
com o ID, testes, registro em `docs/roadmap/execucao/<ID>.md`, relatório de testes alterados aprovado, issue
fechada, acompanhamento da sprint, backlog válido).
