# DEBT-016 — Declarar no OpenAPI os tipos de agendamento (inicial e encerramento)

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 12 · **Issue:** #151 · **Branch:** `chore/DEBT-016-enum-tipos-agendamento` · **PR:** #163

## Entrega
Decisão do SPK-004, item 11 (ADR-0012): os tipos continuam só `inicial` e `encerramento`. `app/schemas.py` ganha a constante `TIPOS_AGENDAMENTO` e o tipo `TipoAgendamento`, um `str` com `enum` no schema JSON, usado em `AgendamentoCreate.tipo` e `AgendamentoUpdate.tipo`. As duas rotas que validam o tipo usam a mesma constante, então o que o OpenAPI declara e o que a API aceita não se separam. O OpenAPI passa a listar os valores aceitos. A validação continua nas rotas, com a mesma resposta 422 e a mensagem de campo, então quem já trata o erro não percebe diferença.

| Critério de aceite | Prova |
|---|---|
| O schema de criação e de alteração declara `tipo` como enum no OpenAPI | `test_criacao_declara_o_enum` e `test_alteracao_declara_o_enum_e_aceita_nulo` (na alteração, o campo continua opcional) |
| Tipo fora do enum continua 422 com a mensagem de campo | `test_tipo_fora_do_enum_continua_422_com_mensagem_de_campo` (criar e alterar, `erros.tipo`; na alteração, o tipo gravado não muda) |
| Existe teste que confere o enum no OpenAPI | os dois primeiros acima |

## Testes
- **Novos:** 4 testes em `tests/integration/test_openapi_tipos_agendamento.py`; antes da mudança, os 2 do OpenAPI falhavam.
- **Suíte completa:** 1076 passaram, 3 pulados, cobertura 96%. Rodada numa cópia sem o arquivo de segredos local.
- **Collection do Insomnia:** não muda; o caso "Agendamento com tipo inválido → 422" continua igual.

## Segurança
- `/security-audit diff dev` em 2026-11-08: os 7 scanners com status `ok`. **Nenhum achado novo.**
- Documentação do contrato da API (OWASP API9:2023, inventário): os valores aceitos ficam explícitos para quem integra.
- `/code-review` (medium):
  - **Corrigido:** a constante única para o schema e as rotas;
  - **Corrigido:** a conferência de que a alteração recusada não grava.
  - **Sem mudança:**
    - o tipo do checklist, que aceita os mesmos dois valores, não ganhou enum, porque fica fora do critério deste item;
    - a validação continua nas rotas, para manter a mensagem de campo atual.

## Testes existentes alterados
Nenhum.

## Documentação
- O próprio OpenAPI (`/docs`, `/openapi.json`) passa a mostrar o enum.
- Nada no README: o mapa de rotas não detalha os campos.
