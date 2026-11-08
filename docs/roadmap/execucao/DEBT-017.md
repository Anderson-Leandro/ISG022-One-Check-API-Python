# DEBT-017 — Regras de acesso negam por padrão os perfis que não citam

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 13 · **Issue:** #165 · **Branch:** `refactor/DEBT-017-acesso-nega-por-padrao` · **PR:** #<n>

## Entrega
- `app/deps.py` ganha `PERFIS_GESTAO` (a mesma lista de `PRIVILEGED_ROLES`) e `negar_perfil_desconhecido`, que responde 403 a qualquer perfil fora de `ROLES`. A lista de perfis continua sendo uma só, a de `app.auth`.
- A regra é chamada no início de cada ponto que liberava por padrão:
  - `assert_acesso_contrato`, `assert_acesso_imovel` e o recorte do dashboard (`_contratos_visiveis`);
  - as listagens de contratos e de imóveis e os checklists do contrato;
  - o histórico do imóvel e o PDF do laudo.
- `assert_acesso_problemas` e as checagens de checklist já liberavam admin e gestor explicitamente e negavam o resto; ficaram como estavam.

| Critério de aceite | Prova |
|---|---|
| Cada regra de `app/deps.py` e dos recortes de listagem libera admin e gestor explicitamente e nega perfil não citado | `negar_perfil_desconhecido` no início de cada regra; `test_admin_e_gestor_continuam_liberados` |
| Teste que chama as regras diretamente com perfil fora de `ROLES` e confere a negação | `TestRegrasChamadasDiretamente` (contrato, imóvel, problemas, dashboard) e `test_rota_de_leitura_nega_perfil_desconhecido` (10 rotas de leitura, com o `get_current_user` contornado de propósito) |
| Os testes de autorização existentes passam sem alteração | suíte completa verde; nenhum arquivo de teste existente mudou |

## Testes
- **Novos:** 21 testes em `tests/integration/test_seguranca_acesso_nega_por_padrao.py`; antes da mudança, 12 falhavam: os 12 caminhos que liberavam o perfil desconhecido.
- **Suíte completa:** 1117 passaram, 3 pulados, cobertura 96%. Rodada numa cópia sem o arquivo de segredos local.
- **Mutação:** com `negar_perfil_desconhecido` desligada, os 12 voltam a falhar.

## Segurança
- `/security-audit diff dev` em 2026-11-08: os 7 scanners com status `ok`. **Nenhum achado novo**; o B110 do filtro de data dos logs é o SEC-020, nesta sprint.
- Fail secure em profundidade (CWE-636, OWASP API5:2023). A checagem de perfil no `get_current_user`, no login e no refresh (ADR-0009) passa a ter uma segunda camada nas próprias regras.

- `/code-review` (medium): nenhum defeito.
  - **Aplicado:**
    - a lista única de perfis do `app.auth`;
    - a checagem antes da busca do registro, que fecha o 404 contra 403 (5 testes de ID inexistente);
    - os imports quebrados em várias linhas.
  - **Sem mudança:** a repetição da chamada nas regras, que é o padrão escolhido e está coberto pelos testes de cada rota.

## Testes existentes alterados
Nenhum.

## Documentação
- O ADR-0009 já descreve a regra; o código cita o DEBT-017 onde a regra central é definida.
- Nada no README nem na collection: o comportamento para os quatro perfis não mudou.
