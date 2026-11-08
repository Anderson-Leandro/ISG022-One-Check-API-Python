---
name: sprint-executor
description: Executa os itens da sprint ativa um a um, seguindo o processo do projeto - branch própria a partir da dev, testes na cópia sem .env, security-audit diff, relatório de testes existentes alterados, PR, merge com CI verde, item e issue como concluídos, acompanhamento da sprint e conferência da DoD por scripts/dod_check.py. Use quando o usuário pedir para executar, implementar ou tocar a sprint, o próximo item, ou um item específico (ex. /sprint-executor SEC-032).
argument-hint: "[ID do item | proximo | status]"
---

# Sprint Executor

Executa a sprint item a item **sem pular etapas**. Todo item termina com `python3 scripts/dod_check.py <ID>`
verde. Se o script não passar, o item não está pronto.

- `BL` = `python3 ~/.claude/skills/_roadmap-shared/scripts/backlog.py --root .`
- `SP` = `python3 ~/.claude/skills/_roadmap-shared/scripts/sprint.py --root .`
- `GH` = `python3 ~/.claude/skills/board-sync/scripts/github_sync.py --root .`
- `TESTES` = rodar o pytest numa cópia do projeto no scratchpad, sem `.env`, `.venv`, `.git`, `uploads`,
  `*.db`, `__pycache__`, `MUDANCAS_API_PARA_FRONT.md` e `PENDENCIAS_API.md`:
  `rsync -a --delete --exclude .env ... ./ <scratchpad>/proj/` e `python -m pytest -q -p no:cacheprovider`
  com um venv do scratchpad (`pip install -r requirements-test.txt`).

Argumento: `$ARGUMENTS`. Vazio ou `proximo` → próximo item; um ID → esse item; `status` → só mostra a fila.

## Modo e autorização

Leia a linha **Modo de execução** em `CLAUDE.md`:
- `confirmar cada item` (atual): execute **um** item e pare no fim para o usuário conferir.
- `contínuo`: siga para o próximo item até um ponto de parada.

Neste fluxo o usuário já autorizou, de forma permanente: criar branch, commitar, abrir PR, **fazer o merge
depois do CI verde** e aplicar o board-sync do item (sempre com o dry-run mostrado antes, na mesma resposta).
Fora deste fluxo, valem as regras normais de pedir confirmação.

## Pontos de parada (sempre, em qualquer modo)

Pare, explique e espere o usuário quando:
1. **um teste existente precisa ser alterado ou removido** (protocolo abaixo); nunca commite antes da aprovação;
2. o item **só o usuário pode fazer** (acesso ao Render ou a outro serviço externo, credenciais, decisões de PO
   em spikes): prepare a análise e as opções, e pare;
3. a security-audit tiver achado **alto ou crítico** novo;
4. o CI falhar **duas vezes** no mesmo PR, ou um teste falhar e a causa não for clara;
5. o escopo crescer além dos critérios de aceite, ou a sprint for estourar a data (proponha o que sai);
6. qualquer ação fora das regras do `CLAUDE.md` (produção, `.env`, reescrever histórico).

## Fluxo por item

### 1. Escolher
- `SP report` e `BL list`: o próximo item `in_sprint`/`ready` da sprint ativa pelo `rank`, com `depends_on`
  concluídos. Pule os de ponto de parada 2 e registre por quê.
- `BL dor`: o item precisa passar na DoR; se não passar, refine com `/product-backlog refine` e confirme a
  estimativa com o usuário.

### 2. Preparar
- `git switch dev && git pull --ff-only`, depois `git switch -c <tipo>/<ID>-<descricao-curta>`
  (`tipo`: feat, fix, test, refactor, docs, chore, security).
- `BL update <ID> --json '{"status": "in_progress"}'`, depois `GH push --ids <ID>` (dry-run e `--apply`).
- Copie `docs/roadmap/execucao/_modelo.md` para `docs/roadmap/execucao/<ID>.md`.

### 3. Implementar
- Leia o código envolvido antes de mudar. Siga os critérios de aceite, nada além.
- Escreva primeiro o teste do cenário negado ou do critério, veja-o falhar, depois implemente.
- Rode `TESTES` (suíte completa). A cobertura não pode cair abaixo da anterior.

### 4. Testes existentes (protocolo obrigatório)
Antes de qualquer commit, liste os testes que já existiam e foram alterados ou removidos:
`git diff --name-status origin/dev -- tests/` (arquivos `M` ou `D`) e o diff de cada um. Acrescentar asserções
num teste existente sem tirar nenhuma não conta como alteração.
- **Nenhum**: escreva "Nenhum." na seção do registro.
- **Algum**: pare antes do commit. Preencha a tabela da seção "Testes existentes alterados" do registro
  (arquivo :: teste, antes, depois, por que precisa mudar, se o comportamento atual quebra) e mostre ao usuário.
  Diga com clareza quando uma alteração **enfraquece** um teste. Só continue depois da aprovação, e escreva
  `Aprovado por: <nome> em AAAA-MM-DD` no registro.

### 5. Revisar
- `/security-audit diff dev`: registre os achados na seção "Segurança". Médio ou baixo novo → item no
  backlog fora da sprint. Alto ou crítico → ponto de parada 3.
- `/code-review` no diff quando o item muda código; corrija o que for defeito real.

### 6. Documentar
- README, ADR (decisão nova → `docs/adr/NNNN-*.md`), collection do Insomnia (`python3 docs/insomnia/gerar_collection.py`
  e rodar contra a API local na cópia, porta livre, nunca a 8000 do usuário), riscos.
- Mudança que afeta o front → `MUDANCAS_API_PARA_FRONT.md` (local, nunca no git).
- Preencha as seções "Entrega", "Testes" e "Documentação" do registro.

### 7. Publicar
- `python3 scripts/dod_check.py <ID> --antes-do-merge` precisa passar nas verificações do PR.
- Commit em Conventional Commits, terminando com a linha `Co-Authored-By` combinada no projeto.
- `git push -u origin <branch>` e `gh pr create --base dev` com: o que muda, critérios atendidos, testes,
  segurança, testes existentes alterados (copie a tabela) e `Refs #<issue>`. Termine com a linha de atribuição
  do projeto.
- `gh pr checks <n> --watch`. Verde → `gh pr merge <n> --merge`. Falhou → corrija; segunda falha → parada 4.

### 8. Fechar
- `git switch dev && git pull --ff-only` e uma branch `chore/<ID>-concluido` para os registros.
- `BL update <ID> --json '{"status": "done", "prs_add": ["#<n>"], "evidence": [...]}'`.
- `GH push --ids <ID>` (dry-run e `--apply`): fecha a issue.
- Uma linha na tabela "Acompanhamento" do `docs/roadmap/sprints/sprint-NN.md`.
- `python3 scripts/dod_check.py <ID>`: precisa sair verde. Commit, PR, CI verde e merge desses registros.

### 9. Relatar
Resumo curto ao usuário: o que foi entregue, testes, segurança, testes existentes alterados (e aprovação),
PRs, o resultado do `dod_check` e o burndown (`SP report`). No modo `confirmar cada item`, pare aqui.

## Fim da sprint
Quando não houver mais itens executáveis, liste os que ficaram (com o motivo) e sugira `/sprint-manager review`.
O DEBT-007 (release) só entra depois de todos os outros itens de código.
