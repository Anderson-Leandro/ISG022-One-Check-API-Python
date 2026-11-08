# ADR-0012: Regras de negócio pendentes: agendamentos, comentários, rejeição e tipos

- **Status:** aceito
- **Data:** 2026-11-08
- **Itens relacionados:** SPK-004, US-018, US-019, US-020, DEBT-016, ADR-0008, R-003

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
Quatro regras ficaram em aberto desde a conversão da API em PHP (itens 5, 7, 8 e 11 das pendências locais). As decisões abaixo foram tomadas pelo usuário (PO) em 2026-11-08.

## Decisões

### 1. O locatário vê os agendamentos do próprio contrato (item 5, US-018)
- **Antes:** `GET /contratos/{id}/agendamentos` respondia 403 para o locatário, que já via as vistorias e os problemas do mesmo contrato.
- **Opções:** liberar a leitura no contrato dele, ou manter o 403.
- **Decisão:** liberar **só a leitura e só no próprio contrato**. Criar, alterar e excluir continuam com admin e gestor. O locatário vê o tipo e a data; a `observacao`, nota interna da equipe, não vai na resposta para ele (ajuste feito na revisão de código do US-018). Saber a data da vistoria não expõe nada que ele já não veja.

### 2. O locatário comenta no próprio problema (item 7, US-019)
- **Antes:** só admin e gestor criavam atualizações.
- **Opções:** liberar ao locatário dono, com ou sem limite, ou manter.
- **Decisão:** o **locatário dono** do contrato cria atualizações **enquanto o problema não estiver `resolvido`** (depois, 409). Mudar o status continua com admin e gestor. Uma atualização também impede a exclusão do problema (ADR-0008).

### 3. Depois de uma rejeição, nova vistoria (item 8, US-020)
- **Antes:**
  - rejeitar uma vistoria era final;
  - criar outra vistoria **inicial** no mesmo contrato dava 409, e a exclusão (ADR-0008) não aceita vistoria rejeitada, então o contrato ficava travado;
  - o status `pendente_revisao` existia no domínio, mas nenhum fluxo o gravava.
- **Opções:**
  - a. ciclo de revisão: rejeitar leva a `pendente_revisao` e o vistoriador corrige o mesmo laudo;
  - b. a rejeitada continua final e intocável, e uma nova inicial pode ser criada;
  - c. deixar como está.
- **Decisão: opção b.**
  - a vistoria rejeitada é evidência e não muda (R-003);
  - uma nova vistoria inicial pode ser criada quando a inicial anterior foi rejeitada; em qualquer outro status, continua 409;
  - `pendente_revisao` sai do domínio, inclusive das contagens.

### 4. Tipos de agendamento (item 11, DEBT-016)
- **Antes:** a API aceita `inicial` e `encerramento`; o front antigo previa também `final` e `periodica`.
- **Opções:** manter os dois tipos, ou acrescentar `periodica`.
- **Decisão:** **manter só os dois** e declará-los como enum no OpenAPI, para quem integra ver os valores aceitos.

## Consequências
- **Positivas:** as quatro regras ficam escritas e testáveis; o contrato com vistoria rejeitada deixa de travar; o OpenAPI passa a documentar os tipos.
- **Negativas / custos:** quatro itens novos (6 pts) na Sprint 12.
- **Segurança:**
  - as duas liberações ao locatário valem só para o próprio contrato e trazem testes de cenário negado (OWASP API1:2023, CWE-639);
  - a opção b preserva o laudo rejeitado como evidência.
