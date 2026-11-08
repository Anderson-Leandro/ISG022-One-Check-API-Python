---
name: sprint-executor
description: Executa os itens da sprint ativa um a um, seguindo o processo do projeto - branch própria a partir da dev, testes na cópia sem .env, security-audit diff, relatório de testes existentes alterados, PR, merge com CI verde, item e issue como concluídos, acompanhamento da sprint e conferência da DoD por scripts/dod_check.py. Use quando o usuário pedir para executar, implementar ou tocar a sprint, o próximo item, ou um item específico (ex. /sprint-executor SEC-032).
argument-hint: "[ID do item | proximo | status] [--continuo]"
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
A flag `--continuo` (também aceite `--contínuo` ou `continuo`) pode vir sozinha ou junto com um ID
(`/sprint-executor --continuo`, `/sprint-executor SEC-034 --continuo`) e liga o modo `contínuo` só nesta execução.

## Modo e autorização

O modo vem do argumento, não de arquivo: vale só para a execução atual e nunca é gravado.
- **Sem a flag → `confirmar cada item` (padrão):** execute **um** item até o **PR aberto com o CI verde** e pare.
  **O merge é do usuário.** O item fica em `review`; o fechamento (passo 8) acontece no início da execução
  seguinte, depois de conferir que o usuário mesclou.
- **Com `--continuo` → `contínuo`:** faça o merge depois do CI verde, feche o item (o PR de fechamento também é
  mesclado por você) e siga para o próximo, até um ponto de parada ou o fim dos itens executáveis. No início,
  diga em uma linha que o modo contínuo está ligado.

Neste fluxo o usuário já autorizou, de forma permanente: criar branch, commitar, abrir PR, aplicar o board-sync
do item (sempre com o dry-run mostrado antes, na mesma resposta) e, **só com `--continuo`**, fazer o merge dos
PRs abertos nesta execução depois do CI verde. Sem a flag, nunca rode `gh pr merge`. PRs que ficaram aguardando
o usuário em execuções anteriores continuam com ele, mesmo no modo contínuo: liste-os e não os mescle. Fora deste
fluxo, valem as regras normais de pedir confirmação.

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

### 0. Fechar o que o usuário mesclou
- Para cada item da sprint em `review`: veja o PR em `links.prs` (`gh pr view <n> --json state`).
  - `MERGED` → faça o passo 8 (Fechar) desse item antes de escolher o próximo.
  - Ainda aberto → não comece outro item que dependa dele; avise que o PR aguarda o merge.
- Os PRs de fechamento (`chore/<ID>-concluido`) também ficam para o usuário mesclar.

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
- Commit em Conventional Commits, terminando com a linha `Co-Authored-By` combinada no projeto.
- `git push -u origin <branch>` e `gh pr create --base dev` com: o que muda, critérios atendidos, testes,
  segurança, testes existentes alterados (copie a tabela) e `Refs #<issue>`. Termine com a linha de atribuição
  do projeto.
- `gh pr checks <n> --watch`. Falhou → corrija; segunda falha → parada 4.
- Com o CI verde, `python3 scripts/dod_check.py <ID> --antes-do-merge` precisa passar. Depois:
  - modo `contínuo`: `gh pr merge <n> --merge` e siga para o passo 8;
  - modo `confirmar cada item`: **não faça o merge.** Na mesma branch, `BL update <ID> --json '{"status": "review",
    "prs_add": ["#<n>"]}'`, `GH push --ids <ID>` (dry-run e `--apply`), commit e push no mesmo PR; espere o CI
    verde de novo e vá para o passo 9.

### 8. Fechar
- `git switch dev && git pull --ff-only` e uma branch `chore/<ID>-concluido` para os registros.
- `BL update <ID> --json '{"status": "done", "prs_add": ["#<n>"], "evidence": [...]}'`.
- `GH push --ids <ID>` (dry-run e `--apply`): fecha a issue.
- Uma linha na tabela "Acompanhamento" do `docs/roadmap/sprints/sprint-NN.md`.
- `python3 scripts/dod_check.py <ID>`: precisa sair verde. Commit, PR e CI verde desses registros; o merge segue
  o modo (`contínuo`: você faz; `confirmar cada item`: o usuário faz).

### 9. Relatar
Resumo curto ao usuário: o que foi entregue, testes, segurança, testes existentes alterados (e aprovação),
PRs, o resultado do `dod_check` e o burndown (`SP report`). No modo `confirmar cada item`, pare aqui e diga
quais PRs aguardam o merge do usuário (o do item e, se houver, o de fechamento do item anterior).

## Fim da sprint
Quando não houver mais itens executáveis, liste os que ficaram (com o motivo) e sugira `/sprint-manager review`.
O DEBT-007 (release) só entra depois de todos os outros itens de código.
