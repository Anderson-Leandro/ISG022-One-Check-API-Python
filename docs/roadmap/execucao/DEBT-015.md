# DEBT-015 — Remover o perfil visualizador e recusar perfis desconhecidos

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 12 · **Issue:** #146 · **Branch:** `refactor/DEBT-015-remover-visualizador` · **PR:** #153

## Entrega
Decisão do SPK-001 (ADR-0009). Sem migração de contas: nenhuma conta com o perfil foi criada, e os ambientes serão zerados.
- `app/auth.py`: `ROLES` sem `visualizador`; criar ou alterar usuário com esse perfil responde 422 pela validação que já existia.
- `app/routers/checklists.py`: a exceção de leitura do visualizador sai de `_assert_pode_ver_checklist`.
- `app/models.py`: `Usuario.role` deixa de ter padrão (era `visualizador`).
- **Fail secure** para perfil fora de `ROLES`:
  - `app/deps.py`: `get_current_user` recusa a conta (401 `Perfil de acesso inválido`). Vale o perfil do banco, não o do token.
  - `app/auth.py`: o login responde "Credenciais inválidas", igual a senha errada, e o refresh não renova. Assim não há sessão nova para um perfil que não existe.

| Critério de aceite | Prova |
|---|---|
| Criar ou alterar usuário com `role: visualizador` → 422 | `TestCriarOuAlterarComVisualizador` (422, `erros.role`, banco igual) |
| Token ou conta com perfil fora de `ROLES` → 401 em qualquer rota autenticada | `TestPerfilForaDaListaNaoAcessaNada`: perfis `visualizador`, `admn` e vazio em `/usuarios/me`, `/contratos`, `/imoveis` e `/dashboard`, e um token que declara `admin` para uma conta com perfil inválido. `TestPerfilForaDaListaNaoAbreSessao`: login e refresh recusados |
| `Usuario` sem perfil padrão | `test_usuario_sem_perfil_nao_e_gravado` (`IntegrityError`) |
| Testes, README, segurança e Insomnia sem o visualizador como perfil ativo; testes alterados com relatório e aprovação | tabela abaixo; README, `vision.md`, `threat-model.md`, `architecture-v1.md` e a collection atualizados |

## Testes
- **Novos:** 25 testes em `tests/integration/test_seguranca_perfis_validos.py`; os 19 da primeira versão falhavam antes da mudança, e os 6 de login e refresh vieram da revisão de código.
- **Suíte completa:** 1037 passaram, 3 pulados, cobertura 96% (igual à anterior). Rodada numa cópia sem o arquivo de segredos local.
- **Mutação:** com a checagem de `get_current_user` desligada, 15 testes novos falham; sem a checagem do login, 3; sem a do refresh, 3.
- **Collection do Insomnia** contra a API local: **161 de 161** (sem a pasta 00a). O caso "Admin cria visualizador" virou "Perfil visualizador não existe mais → 422", e os 7 casos que usavam o token do visualizador saíram.

## Segurança
- `/security-audit diff dev` em 2026-11-08: os 7 scanners com status `ok`. **Nenhum achado novo.** Os alertas de SHA-1 em `docs/insomnia/gerar_collection.py` aparecem porque o arquivo está no diff; o hash só gera IDs da collection e já tinha sido avaliado no relatório de 2026-11-07.
- Menor privilégio por redução de superfície, e fail secure para perfis fora da lista (OWASP API5:2023, CWE-285, CWE-636).
- `/code-review` (medium), com 8 apontamentos:
  - **Corrigidos:**
    - o login e o refresh emitiam tokens para conta com perfil inválido;
    - faltava teste disso;
    - o caso novo da collection usava um e-mail fixo;
    - sobravam linhas em branco nos testes alterados.
  - **Registrado fora da sprint:** as regras de acesso liberam por padrão os perfis que não citam (DEBT-017). Hoje isso está coberto pelas três checagens acima.
  - **Sem mudança:**
    - o status 401 continua: com login e refresh recusando, não há ciclo de renovação;
    - o PUT numa conta com perfil inválido não é tratado, porque essas contas não existem.

## Testes existentes alterados
Todos os casos são a saída de um perfil que deixou de existir. Nenhuma regra dos perfis que continuam fica sem teste.

| Arquivo :: teste | Antes | Depois | Por que precisa mudar | O comportamento atual quebra? |
|---|---|---|---|---|
| `tests/conftest.py` :: fixtures `user_visualizador` e `token_visualizador` | criavam um visualizador | **removidas**; entra `user_locatario_2` (segunda conta comum) | o perfil não existe mais | Não |
| `tests/integration/test_auth_routes.py::TestLogin::test_login_visualizador_sem_mfa` | login de visualizador sem MFA devolve tokens | **removido** | o caso "perfil sem MFA recebe tokens" já é coberto por `test_login_sem_mfa_retorna_tokens` (locatário) | Não |
| `tests/integration/test_checklists.py::TestGetChecklist::test_visualizador_obtem_checklist` | visualizador lê checklist | **removido** | era a regra do perfil removido | Não |
| `tests/integration/test_seguranca_checklist_autorizacao.py::...::test_visualizador_nao_cria_checklist` | visualizador recebe 403 ao criar checklist | **removido** | idem; vistoriador e locatário continuam cobertos | Não |
| `tests/integration/test_seguranca_senha_regras.py::TestDashboardPorPerfil::test_visualizador_sem_problemas` | dashboard do visualizador | **removido** | idem | Não |
| `tests/integration/test_historico_imovel.py::test_visualizador_nao_ve_problemas` | histórico do visualizador sem problemas | **removido**, e a linha do docstring | idem; o vistoriador continua provando que problemas não aparecem para quem não os acessa | Não |
| `tests/integration/test_exclusao_registros.py::test_perfil_sem_permissao_recebe_403` | 3 rotas × vistoriador, locatário, visualizador | 3 rotas × vistoriador, locatário | o perfil saiu da parametrização | Não |
| `tests/integration/test_seguranca_problemas_bola.py` :: `test_sem_vinculo_recebe_403`, `test_mesma_decisao_em_todas_as_rotas` | incluíam `token_visualizador` | sem ele | idem | Não |
| `tests/integration/test_seguranca_listagem_usuarios.py::...::test_listagem_negada` | incluía `token_visualizador` | sem ele | idem | Não |
| `tests/integration/test_seguranca_acesso_vistoriador.py::TestPerfisComLeituraGeral::test_leitura_mantida` | admin, gestor, visualizador | admin, gestor (e o docstring) | idem | Não |
| `tests/integration/test_seguranca_negacao_por_perfil.py` :: `PERFIS`, `tokens`, `test_combinacoes_cobertas` | 5 perfis; `== 97 + 9` | 4 perfis; `== 34 * 2 + 3` (71) | as 35 combinações do visualizador saíram; a lista conferida com a API continua igual | Não; não enfraquece: toda combinação proibida restante tem caso |
| `tests/integration/test_seguranca_rate_limit.py::...::test_outra_conta_nao_e_afetada` | "outra conta" era o visualizador | é `user_locatario_2` | a fixture saiu; o teste prova a mesma coisa | Não |
| `tests/integration/test_seguranca_revogacao_sessoes.py` :: `test_put_usuario_com_credencial[perfil]`, `test_sessao_de_outro_usuario_nao_e_afetada` | troca de perfil para `visualizador`; outra conta era o visualizador | troca para `vistoriador`; outra conta é `user_locatario_2` | idem | Não |
| `tests/integration/test_usuarios.py::TestUpdateUsuario::test_admin_atualiza_role` | atualiza para `visualizador` | atualiza para `vistoriador` | idem | Não |
| `tests/integration/test_seguranca_gestao_usuarios.py` (docstring) | lista os 5 perfis aceitos | 4 perfis | idem | Não |

Aprovado por: Anderson em 2026-11-08

## Documentação
- `README.md`: lista de perfis, tabela de perfis e matriz de acesso sem o visualizador.
- `docs/roadmap/vision.md`, `docs/security/threat-model.md` e `docs/architecture/architecture-v1.md`: o perfil sai (a arquitetura registra a remoção).
- Collection do Insomnia: 172 requisições; `docs/insomnia/README.md` atualizado.
- `MUDANCAS_API_PARA_FRONT.md` (local, fora do git): item 33.
- Documentos históricos de auditoria continuam citando o perfil, como registro do que existia (ADR-0009).
