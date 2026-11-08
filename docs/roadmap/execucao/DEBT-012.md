# DEBT-012 — Testes de negação em escrita conferem o estado e o status exato

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 12 · **Issue:** #108 · **Branch:** `test/DEBT-012-negacao-confere-estado` · **PR:** #131

## Entrega
Só testes, sem mudança no código. Um helper novo em `tests/conftest.py`, `foto_do_banco(db)`, guarda todas as linhas de todas as tabelas, para conferir que uma requisição negada não gravou nada. 54 testes existentes em 12 arquivos ganharam asserções; nenhuma asserção foi removida.

| Critério de aceite | Prova |
|---|---|
| Os testes de negação em escrita releem o banco e conferem que nada mudou | 45 testes de negação em POST, PUT, PATCH ou DELETE tiram a foto do banco antes da chamada negada e comparam depois. A lista saiu de uma varredura da árvore sintática dos testes (a avaliação não versionou a lista dela). Ficaram de fora 5 que não são negação de escrita em recurso (login e refresh recusados, o JSON normal do limite de corpo, o ataque de bypass do MFA, que já confere os tokens) |
| Os testes de negação de checklists e contratos conferem o status exato (403) e a mensagem | Os 25 testes de negação de `test_checklists.py` e `test_contratos.py` que conferiam só o status agora conferem também a mensagem exata (`Token ausente`, `Vistoriador não autorizado neste checklist` e as outras). Todos já usavam o status exato (`== 401` ou `== 403`) |
| `test_outro_vistoriador_nao_pode_submeter` é renomeado (é o gestor) e o caso de um segundo vistoriador ganha teste próprio | Renomeado para `test_gestor_nao_pode_submeter`. O caso do segundo vistoriador já tem teste próprio desde o SEC-032: `test_seguranca_checklist_dono.py::TestOutroVistoriadorNaoAlteraChecklist::test_nao_submete`, citado no comentário do teste renomeado |

## Testes
- **Suíte completa:** 1007 passaram, 3 pulados, cobertura 96% (igual à anterior). Rodada numa cópia sem o arquivo de segredos local. Nenhum teste novo; o número é o mesmo.
- **Mutação conferida** numa cópia, com a rota gravando antes de negar ("um 403 devolvido depois de gravar", o caso da avaliação):

| Mutação | Testes antigos (`origin/dev`) | Testes deste item |
|---|---|---|
| `submit_checklist` grava `pendente_aceite` antes de checar o vistoriador | o teste de negação passa (mutante sobrevive na negação) | `test_gestor_nao_pode_submeter` falha |
| `create_problema` grava um problema antes de checar o acesso | 6 passaram (mutante sobrevive) | `test_locatario_nao_pode_registrar_em_contrato_alheio` falha |

## Segurança
- `/security-audit diff dev` em 2026-11-08: os 7 scanners com status `ok`. **Nenhum achado novo**. Os 4 resultados que aparecem (arquivo de segredos local fora do índice, valores fictícios em outro teste, `HEALTHCHECK` no Dockerfile) são anteriores, ficam fora do diff e já tinham sido avaliados no relatório de 2026-11-07.
- Fecha a lacuna da avaliação SPK-005, seção 4 (CWE-284): uma negação que grave antes de responder 403 agora quebra o CI.

## Testes existentes alterados
O item, por definição, mexe em testes existentes. Em todos, as mudanças **reforçam** o teste: nenhuma asserção foi removida ou afrouxada. As únicas linhas removidas são assinaturas (que ganharam a fixture `db`), imports (que ganharam `foto_do_banco`) e o nome e o comentário do teste renomeado.

| Arquivo :: teste | Antes | Depois | Por que precisa mudar | O comportamento atual quebra? |
|---|---|---|---|---|
| `tests/integration/test_checklists.py::TestSubmeterChecklist::test_outro_vistoriador_nao_pode_submeter` | nome dizia "outro vistoriador", mas usa o token do gestor; conferia só o 403 | `test_gestor_nao_pode_submeter`: 403, a mensagem `Vistoriador não autorizado neste checklist` e o banco igual | o nome enganava (critério do item); o caso do segundo vistoriador está no SEC-032 | Não: a regra testada é a mesma; o teste ficou mais forte |
| 44 testes de negação em escrita (lista abaixo, marcados "banco") | conferiam o status (e às vezes a mensagem) | também conferem que todas as tabelas ficaram iguais | um 403 devolvido depois de gravar passava (avaliação SPK-005, seção 4) | Não: só acrescenta asserção |
| 24 testes de negação de checklists e contratos (lista abaixo, marcados "msg") | conferiam só o status | também conferem a mensagem exata | critério do item: status exato e mensagem | Não: só acrescenta asserção |

Testes alterados, por arquivo (54 no total; "banco" = confere o banco, "msg" = confere a mensagem):
- `tests/integration/test_agendamentos.py` (1): `TestAtualizarEExcluirAgendamento::test_vistoriador_nao_pode_excluir_nem_atualizar` (banco)
- `tests/integration/test_auth_routes.py` (2): `TestLogout::test_logout_sem_autenticacao_retorna_401` e `test_logout_token_invalido_retorna_401` (banco)
- `tests/integration/test_checklists.py` (15): `test_sem_autenticacao_retorna_401` de `TestListItensVistoria` e `TestGetChecklist` (msg); de `TestAddItem`, `TestUpdateItem`, `TestUploadFoto`, `TestDeleteFoto`, `TestSubmeterChecklist`, `TestAceitarChecklist` e `TestRejeitarChecklist` (banco+msg); `TestAddItem::test_locatario_nao_pode_adicionar_item`, `TestSubmeterChecklist::test_gestor_nao_pode_submeter`, `TestAceitarChecklist::test_vistoriador_nao_pode_aceitar`, `TestRejeitarChecklist::test_vistoriador_nao_pode_rejeitar` (banco+msg); `TestDownloadPdf::test_locatario_alheio_recebe_403` e `test_vistoriador_nao_tem_acesso_ao_pdf_e_recebe_403` (msg)
- `tests/integration/test_contratos.py` (10): `test_sem_autenticacao_retorna_401` de `TestListContratos`, `TestListAgendamentos`, `TestListChecklists` e `TestListProblemas` (msg) e de `TestCreateContrato`, `TestCreateChecklist` e `TestCreateProblema` (banco+msg); `TestCreateProblema::test_locatario_nao_pode_registrar_em_contrato_alheio` (banco+msg); `TestGetContrato::test_locatario_nao_acessa_contrato_alheio` (msg); `TestCicloVidaContrato::test_locatario_nao_pode_encerrar_contrato` (banco+msg)
- `tests/integration/test_dashboard.py` (4): `test_sem_secret_retorna_403` e `test_secret_errado_retorna_403` de `TestAdminSeed` e `TestAdminRefreshData` (banco)
- `tests/integration/test_imoveis.py` (3): `test_sem_autenticacao_retorna_401` de `TestCreateImovel`, `TestUpdateImovel` e `TestUpsertEndereco` (banco)
- `tests/integration/test_problemas.py` (4): `TestCriarProblema::test_locatario_alheio_recebe_403`, `TestAtualizarStatusProblema::test_locatario_nao_pode_alterar_status_e_recebe_403`, `TestAtualizacoesProblema::test_locatario_nao_pode_adicionar_atualizacao` e `test_vistoriador_nao_pode_adicionar_atualizacao` (banco)
- `tests/integration/test_seguranca_admin_seed.py` (3): `TestSeedSemAutenticacao::test_refresh_data_sem_token_admin_e_negado`, `TestSeedDestrutivo::test_refresh_data_bloqueado_sem_flag_mesmo_com_admin` e `test_mode_refresh_data_no_seed_tambem_bloqueado` (banco)
- `tests/integration/test_seguranca_checklist_autorizacao.py` (1): `TestSeparacaoDeDeveresNoAceite::test_quem_vistoriou_nao_rejeita` (banco)
- `tests/integration/test_seguranca_gestao_usuarios.py` (1): `TestGestorNaoEscala::test_gestor_nao_altera_outro_gestor` (banco)
- `tests/integration/test_seguranca_limite_corpo.py` (1): `TestAnonimo::test_multipart_anonimo_nao_e_interpretado` (banco)
- `tests/integration/test_usuarios.py` (9): `test_sem_autenticacao_retorna_401` de `TestUpdateMe`, `TestMfaSetupMe`, `TestMfaEnableMe`, `TestMfaDisableMe` e `TestCreateUsuario`; `TestUpdateUsuario::test_vistoriador_nao_pode_atualizar`, `TestCreateUsuario::test_locatario_nao_pode_criar_usuario`, `TestMfaAdminRoutes::test_locatario_nao_pode_resetar_mfa_de_outro`, `TestDeleteUsuario::test_locatario_nao_pode_desativar_usuario` (banco)

Aprovado por: Anderson em 2026-11-08

## Documentação
- Nada no README da API, em ADR ou na collection do Insomnia: o comportamento da API não mudou.
