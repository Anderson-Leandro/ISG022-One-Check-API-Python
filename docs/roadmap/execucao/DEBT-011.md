# DEBT-011 — Testes de negação por perfil em todas as rotas restritas

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 12 · **Issue:** #107 · **Branch:** `test/DEBT-011-negacao-por-perfil` · **PR:** #129

## Entrega
Só testes, sem mudança no código. Arquivo novo: `tests/integration/test_seguranca_negacao_por_perfil.py`, com 103 testes.

| Critério de aceite | Prova |
|---|---|
| Teste parametrizado que, para cada rota com `require_roles`, confere 403 para cada perfil fora da lista, sem gravar nada | `test_perfil_proibido_recebe_403` (97 casos): IDs de objetos reais no caminho, 403 com `"Permissão negada"` e o banco inteiro (todas as tabelas) igual ao de antes. `test_lista_confere_com_a_api` compara a lista escrita à mão (`ROTAS_RESTRITAS`) com as rotas que de fato usam `require_roles`: rota nova, perfil a mais ou dependência removida quebram o teste |
| Teste para `PATCH /imoveis/{id}/endereco`, `POST /contratos/{id}/encerrar` e `POST /contratos/{id}/cancelar` | `test_patch_endereco_pelo_gestor` e `test_post_encerrar_e_cancelar_pelo_gestor` (caminho permitido, com o banco conferido); a negação dessas rotas está nos 97 casos. As rotas duplicadas foram mantidas: removê-las mudaria o contrato da API, fora do escopo deste item |
| Teste de `GET /logs` com o gestor, alinhado à decisão do SEC-018 | `test_gestor_le_os_logs` fixa o comportamento atual (o gestor lê a trilha completa). O SEC-018 (Sprint 13) ainda não decidiu a regra; a docstring do teste avisa que ele muda junto com a decisão, com o relatório de teste alterado |
| A matriz de autorização refeita não mostra combinação perfil proibido sem `N` nas rotas restritas | As combinações saem da própria lista conferida com a API, então toda combinação proibida tem um caso; `test_combinacoes_cobertas` confere que são as 97 da matriz da avaliação SPK-005 |

## Testes
- **Novos:** 103 testes, todos passando.
- **Suíte completa:** 1007 passaram, 3 pulados, cobertura 96% (igual à anterior). Rodada numa cópia sem o arquivo de segredos local.
- **Mutação conferida** numa cópia do projeto:

| Mutação | Suíte atual (sem o arquivo novo) | Testes novos |
|---|---|---|
| `GET /logs` com `get_current_user` no lugar de `require_roles` | 1 falha | 4 falhas |
| `encerrar_contrato` (PATCH e POST) com `get_current_user` | 1 falha | 7 falhas |
| `upsert_endereco` passa a aceitar o vistoriador | 904 passaram (mutante sobrevive) | 4 falhas |
| `require_roles` desligado (`if False`) | 20 falhas | 98 falhas |

## Segurança
- `/security-audit diff dev` em 2026-11-08: os 7 scanners com status `ok`. **Nenhum achado novo**; o arquivo de testes passou limpo. Os 4 resultados que aparecem (arquivo de segredos local fora do índice, valores fictícios em outro teste, `HEALTHCHECK` no Dockerfile) são anteriores, ficam fora do diff e já tinham sido avaliados no relatório de 2026-11-07.
- Fecha a lacuna da avaliação SPK-005 (OWASP API5:2023, CWE-285): uma rota restrita que perca a dependência ou ganhe um perfil agora quebra o CI.

## Testes existentes alterados
Nenhum.

## Documentação
- Nada no README da API, em ADR ou na collection do Insomnia: o comportamento da API não mudou.
