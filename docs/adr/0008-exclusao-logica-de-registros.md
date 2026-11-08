# ADR-0008: Exclusão lógica de contrato, checklist e problema

- **Status:** aceito
- **Data:** 2026-11-08
- **Itens relacionados:** US-015, R-003, ADR-0006

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
Contratos, checklists e problemas criados por engano não tinham como sair da base: só dava para cancelar o contrato. A história US-015 pede que eles sumam das listagens **sem perder rastreabilidade**. Ao mesmo tempo, o laudo aceito é evidência (ativo A-07, risco R-003) e não pode desaparecer. Usuários e imóveis já usam exclusão lógica (campo `ativo`).

As decisões abaixo foram tomadas pelo usuário (PO) em 2026-11-08, na execução do US-015.

## Opções consideradas
1. **Exclusão lógica:** marcar quem e quando excluiu; o registro some das leituras e continua no banco.
   - Prós: auditável; pode ser restaurado direto no banco; nada some do backup.
   - Contras: toda leitura precisa ignorar os excluídos.
2. **Exclusão física com log:** apagar o registro e os filhos; o log guarda um resumo.
   - Prós: base mais limpa.
   - Contras: sem como recuperar; o resumo no log não substitui o registro.

Quem pode excluir: só o admin (texto da história) ou admin e gestor (como já acontece com imóveis e agendamentos).

O que bloqueia: a regra mínima dos critérios (recusar só checklist aceito ou contrato com laudo aceito, excluindo o resto em cascata) ou uma regra estrita (só o que ainda não virou evidência, sem cascata). Na revisão do código, a regra do problema passou a exigir também o status `aberto`: um problema que o gestor já moveu para em andamento ou resolvido está sendo tratado, mesmo sem atualizações.

## Decisão
- **Exclusão lógica (opção 1).** `contratos`, `checklists` e `problemas` ganham `excluido_em` e `excluido_por`. A exclusão grava `delete` na trilha de auditoria.
- **Admin e gestor excluem.** Os outros perfis recebem 403.
- **Regra estrita, sem cascata:**

  | Rota | Permitido quando | Caso contrário |
  |---|---|---|
  | `DELETE /checklists/{id}` | o checklist está em preenchimento | 409 |
  | `DELETE /contratos/{id}` | o contrato não tem checklist nem problema (exclua-os antes) | 409 |
  | `DELETE /problemas/{id}` | o problema está aberto e não tem atualizações | 409 |

  Excluir um contrato ativo devolve o imóvel para `disponivel`, como o cancelamento.
- **Filtro num lugar só.** `app/exclusao.py` registra um evento `do_orm_execute` que acrescenta "não excluído" a toda leitura do ORM: listagens, GET por ID (que passa a responder 404), contagens do dashboard, subconsultas e relacionamentos. Os agendamentos de um contrato excluído também somem. Uma rota nova não precisa lembrar do filtro.

## Consequências
- **Positivas:**
  - a base fica limpa para quem usa a API, e a auditoria continua completa;
  - um checklist enviado, aceito ou rejeitado nunca é excluído, então o laudo e as fotos ficam preservados.
- **Negativas / custos:**
  - não há rota para restaurar nem para listar os excluídos; isso é feito direto no banco;
  - as fotos de um checklist excluído continuam no disco (ADR-0006);
  - o filtro vale para leituras: uma consulta em SQL puro (`text()`) ou um `update()`/`delete()` em massa do ORM não passa por ele. Hoje só a migração usa `text()`, e a única alteração em massa nessas tabelas é o recarregamento destrutivo do seed (`app/seed_service.py`), que apaga tudo, inclusive os excluídos, como deve;
  - a checagem e a marcação não usam trava: um checklist criado no mesmo instante em que o contrato é excluído pode ficar sob um contrato excluído. Com um worker e o volume atual, o risco é aceito;
  - como em toda a API, a trilha é gravada num commit separado, logo depois da exclusão.
- **Segurança:**
  - o registro excluído some também para quem tinha acesso a ele; quem excluiu fica em `excluido_por` e na trilha (não-repúdio);
  - a negação por perfil das três rotas entra na lista conferida pelos testes de autorização (`test_seguranca_negacao_por_perfil.py`).
