# Mapa de funcionalidades — linha de base (2026-11-02)

Gerado por `feature_map.py` na adoção do projeto (`project-kickoff adopt`), sobre o commit `d0b5f35`. Serve de linha de base: rode o script de novo nas reviews e compare.

```bash
python3 ~/.claude/skills/_roadmap-shared/scripts/feature_map.py --root .
```

> **Leitura da coluna "testadas"/"Testada":** o script procura o caminho literal da rota nos testes. Como os testes montam as URLs com f-string (`f"{BASE}/{id}/itens"`), ele marcou 37 rotas como **não** testadas. Conferi uma a uma pelos sufixos (`/itens`, `/fotos`, `/submeter`, `/encerrar`, `/comodos`, `/atualizacoes`, `/mfa/...`): **todas aparecem nos testes**. A cobertura real por módulo está na matriz abaixo.

## Matriz (código × testes × git × docs)

| Funcionalidade | Rotas | Proteção | Cobertura (linhas) | Git (commits, período) | Docs/pendências | Situação | Itens |
|---|---|---|---|---|---|---|---|
| Autenticação, MFA e sessões (`/auth`) | 12 | 5 públicas justificadas (login, MFA com temp token, refresh), 6 auth, 1 admin | `auth_router.py` 97%, `auth.py` 100% | 10, jun–out/2026 | README "Login com MFA", correções N1, itens 1, SEC-005/013/015 | implementada + testada | US-001, US-002, SEC-021, SEC-023, SEC-005, SEC-013 |
| Usuários (`/usuarios`) | 15 | 6 auth (`/me`), 9 admin/gestor | 99% | 10, jun–nov/2026 | N4, item 2, SEC-011/014/015 | implementada + testada | US-003, SEC-011, SEC-014, SEC-015 |
| Imóveis, endereço e cômodos | 13 | 4 auth (por dono), 9 admin/gestor | 95%; geocoding 82% | 7, jun–out/2026 | SEC-004 | implementada + testada | US-004, US-012, DEBT-010 |
| Contratos e agendamentos | 15 | 6 auth (por dono), 9 admin/gestor | contratos 93%, agendamentos **84%** | 13 + 2 | PENDENCIAS 5, 11, 12 | implementada + testada | US-005, US-006, US-013, SPK-004, US-015 |
| Checklists, fotos, aceite e PDF | 13 | 12 auth (por dono/perfil), 1 admin/gestor | 92%; PDF 98% | 10, jun–out/2026 | N3, PENDENCIAS 8 | implementada + testada | US-007, US-008, US-009, US-014, SEC-022 |
| Problemas e notificações | 6 | auth com `assert_acesso_problemas`; status e atualizações admin/gestor | 91% | 4 + contratos | item 6, SEC-012, PENDENCIAS 7, 9 | implementada + testada | US-010, SEC-012, DEBT-001 |
| Dashboard e logs | 2 | dashboard auth (recorte por perfil), logs só admin (SEC-018) | 91% | 5 | SEC-012; auditoria 2026-11-02 | implementada + testada; 2 achados abertos | US-011, SEC-018, SEC-020 |
| Admin (seed) | 5 | `require_seed_access` (SEED_SECRET + admin) | 95% | 4 | N2, SEC-001 | implementada + testada | SEC-001, SEC-021 |
| Health e uploads | 2 + `/` | públicas por design | 100% | 4 | T-14 (fotos públicas) | implementada + testada | SPK-002, SEC-026 |

Todas as rotas `public` foram conferidas no handler: `/`, `/health`, login, `mfa/verify`, `mfa/setup-login`, `mfa/activate-login` (exigem `temp_token`), `refresh` (exige refresh token) e `/uploads/{arquivo}` (pública por decisão, T-14). Nenhuma rota de escrita depende só de `auth` sem regra de dono ou perfil.

---


Frameworks detectados: fastapi · rotas: 82 · modelos: 15
Proteção: public = nenhum indício de autenticação no handler (confirme!) · auth = exige login · auth* = protegido no router/classe · role = exige perfil. 'testada' = caminho citado nos testes.

## Funcionalidades (por módulo)

| Funcionalidade | Rotas | public | auth | role | testadas | commits | período |
|---|---|---|---|---|---|---|---|
| /admin | 5 | 0 | 5 | 0 | 5/5 | 4 | 2026-06-07 → 2026-10-25 |
| /agendamentos | 2 | 0 | 0 | 2 | 2/2 | 2 | 2026-09-07 → 2026-10-30 |
| /auth | 12 | 5 | 6 | 1 | 12/12 | 10 | 2026-06-03 → 2026-10-30 |
| /contratos | 13 | 0 | 6 | 7 | 3/13 | 13 | 2026-06-03 → 2026-10-30 |
| /imoveis | 13 | 0 | 4 | 9 | 5/13 | 7 | 2026-06-03 → 2026-10-30 |
| /usuarios | 15 | 0 | 6 | 9 | 11/15 | 10 | 2026-06-03 → 2026-11-01 |
| checklists | 13 | 0 | 12 | 1 | 2/13 | 10 | 2026-06-03 → 2026-10-30 |
| dashboard | 2 | 0 | 1 | 1 | 2/2 | 5 | 2026-06-03 → 2026-10-30 |
| health | 2 | 2 | 0 | 0 | 2/2 | 4 | 2026-06-03 → 2026-10-25 |
| main | 1 | 1 | 0 | 0 | 0/1 | 9 | 2026-06-03 → 2026-10-30 |
| problemas | 4 | 0 | 2 | 2 | 1/4 | 4 | 2026-09-07 → 2026-10-25 |

## Rotas

| Método | Caminho | Proteção | Perfis / guard | Testada | Local |
|---|---|---|---|---|---|
| GET | `/` | public |  | **não** | app/main.py:94 (root) |
| GET | `/admin/data/status` | auth | require_seed_access | sim | app/routers/admin.py:63 (data_status) |
| POST | `/admin/refresh-data` | auth | require_seed_access | sim | app/routers/admin.py:72 (refresh_data) |
| PUT | `/admin/refresh-data` | auth | require_seed_access | sim | app/routers/admin.py:73 (refresh_data) |
| PATCH | `/admin/refresh-data` | auth | require_seed_access | sim | app/routers/admin.py:74 (refresh_data) |
| POST | `/admin/seed` | auth | require_seed_access | sim | app/routers/admin.py:87 (seed_database) |
| PUT | `/agendamentos/{agendamento_id}` | role | admin, gestor | sim | app/routers/agendamentos.py:29 (update_agendamento) |
| DELETE | `/agendamentos/{agendamento_id}` | role | admin, gestor | sim | app/routers/agendamentos.py:65 (delete_agendamento) |
| POST | `/auth/login` | public |  | sim | app/routers/auth_router.py:49 (login) |
| POST | `/auth/mfa/verify` | public |  | sim | app/routers/auth_router.py:88 (mfa_verify) |
| GET | `/auth/mfa/setup-login` | public |  | sim | app/routers/auth_router.py:119 (setup_login) |
| POST | `/auth/mfa/activate-login` | public |  | sim | app/routers/auth_router.py:144 (activate_login) |
| POST | `/auth/mfa/setup` | auth |  | sim | app/routers/auth_router.py:183 (mfa_setup) |
| GET | `/auth/mfa/setup` | auth |  | sim | app/routers/auth_router.py:184 (mfa_setup) |
| POST | `/auth/mfa/activate` | auth |  | sim | app/routers/auth_router.py:195 (mfa_activate) |
| POST | `/auth/mfa/disable` | role | admin | sim | app/routers/auth_router.py:225 (mfa_disable) |
| POST | `/auth/mfa/habilitar` | auth |  | sim | app/routers/auth_router.py:247 (mfa_habilitar) |
| POST | `/auth/mfa/desabilitar` | auth |  | sim | app/routers/auth_router.py:259 (mfa_desabilitar) |
| POST | `/auth/refresh` | public |  | sim | app/routers/auth_router.py:286 (refresh) |
| POST | `/auth/logout` | auth |  | sim | app/routers/auth_router.py:298 (logout) |
| GET | `/itens-vistoria` | auth |  | sim | app/routers/checklists.py:78 (list_itens_vistoria) |
| GET | `/checklists/{checklist_id}` | auth |  | sim | app/routers/checklists.py:96 (get_checklist) |
| POST | `/checklists/{checklist_id}/itens` | auth |  | **não** | app/routers/checklists.py:110 (add_item) |
| PUT | `/checklists/{checklist_id}/itens/{item_id}` | auth |  | **não** | app/routers/checklists.py:173 (update_item) |
| POST | `/checklists/{checklist_id}/itens/{item_id}/fotos` | auth |  | **não** | app/routers/checklists.py:228 (upload_foto) |
| DELETE | `/checklists/{checklist_id}/itens/{item_id}/fotos/{foto_id}` | auth |  | **não** | app/routers/checklists.py:288 (delete_foto) |
| PATCH | `/checklists/{checklist_id}/submeter` | auth |  | **não** | app/routers/checklists.py:326 (submit_checklist) |
| PATCH | `/checklists/{checklist_id}/enviar-para-aceite` | role | admin, gestor | **não** | app/routers/checklists.py:356 (enviar_para_aceite) |
| PATCH | `/checklists/{checklist_id}/aceitar` | auth |  | **não** | app/routers/checklists.py:384 (aceitar_checklist) |
| PATCH | `/checklists/{checklist_id}/rejeitar` | auth |  | **não** | app/routers/checklists.py:413 (rejeitar_checklist) |
| GET | `/checklists/{checklist_id}/download` | auth |  | **não** | app/routers/checklists.py:445 (download_pdf) |
| GET | `/checklists/{checklist_id}/download-pdf` | auth |  | **não** | app/routers/checklists.py:446 (download_pdf) |
| GET | `/checklists/{checklist_id}/pdf` | auth |  | **não** | app/routers/checklists.py:447 (download_pdf) |
| GET | `/contratos` | auth |  | sim | app/routers/contratos.py:41 (list_contratos) |
| POST | `/contratos` | role | admin, gestor | sim | app/routers/contratos.py:68 (create_contrato) |
| GET | `/contratos/{contrato_id}` | auth |  | sim | app/routers/contratos.py:119 (get_contrato) |
| PATCH | `/contratos/{contrato_id}/encerrar` | role | admin, gestor | **não** | app/routers/contratos.py:133 (encerrar_contrato) |
| POST | `/contratos/{contrato_id}/encerrar` | role | admin, gestor | **não** | app/routers/contratos.py:134 (encerrar_contrato) |
| PATCH | `/contratos/{contrato_id}/cancelar` | role | admin, gestor | **não** | app/routers/contratos.py:158 (cancelar_contrato) |
| POST | `/contratos/{contrato_id}/cancelar` | role | admin, gestor | **não** | app/routers/contratos.py:159 (cancelar_contrato) |
| GET | `/contratos/{contrato_id}/agendamentos` | auth |  | **não** | app/routers/contratos.py:197 (list_agendamentos) |
| POST | `/contratos/{contrato_id}/agendamentos` | role | admin, gestor | **não** | app/routers/contratos.py:220 (create_agendamento) |
| GET | `/contratos/{contrato_id}/checklists` | auth |  | **não** | app/routers/contratos.py:259 (list_checklists) |
| POST | `/contratos/{contrato_id}/checklists` | role | admin, gestor | **não** | app/routers/contratos.py:278 (create_checklist) |
| POST | `/contratos/{contrato_id}/problemas` | auth |  | **não** | app/routers/contratos.py:334 (create_problema) |
| GET | `/contratos/{contrato_id}/problemas` | auth |  | **não** | app/routers/contratos.py:467 (list_problemas) |
| GET | `/dashboard` | auth |  | sim | app/routers/dashboard.py:31 (dashboard) |
| GET | `/logs` | role | admin | sim | app/routers/dashboard.py:75 (logs) |
| GET | `/health` | public |  | sim | app/routers/health.py:10 (health) |
| GET | `/uploads/{filename}` | public |  | sim | app/routers/health.py:15 (serve_upload) |
| GET | `/imoveis` | auth |  | sim | app/routers/imoveis.py:57 (list_imoveis) |
| POST | `/imoveis` | role | admin, gestor | sim | app/routers/imoveis.py:87 (create_imovel) |
| GET | `/imoveis/{imovel_id}` | auth |  | sim | app/routers/imoveis.py:119 (get_imovel) |
| PUT | `/imoveis/{imovel_id}` | role | admin, gestor | sim | app/routers/imoveis.py:137 (update_imovel) |
| DELETE | `/imoveis/{imovel_id}` | role | admin, gestor | sim | app/routers/imoveis.py:172 (delete_imovel) |
| GET | `/imoveis/{imovel_id}/endereco` | auth |  | **não** | app/routers/imoveis.py:194 (get_endereco) |
| POST | `/imoveis/{imovel_id}/endereco` | role | admin, gestor | **não** | app/routers/imoveis.py:211 (upsert_endereco) |
| PUT | `/imoveis/{imovel_id}/endereco` | role | admin, gestor | **não** | app/routers/imoveis.py:212 (upsert_endereco) |
| PATCH | `/imoveis/{imovel_id}/endereco` | role | admin, gestor | **não** | app/routers/imoveis.py:213 (upsert_endereco) |
| GET | `/imoveis/{imovel_id}/comodos` | auth |  | **não** | app/routers/imoveis.py:241 (list_comodos) |
| POST | `/imoveis/{imovel_id}/comodos` | role | admin, gestor | **não** | app/routers/imoveis.py:262 (create_comodo) |
| PUT | `/imoveis/{imovel_id}/comodos/{comodo_id}` | role | admin, gestor | **não** | app/routers/imoveis.py:285 (update_comodo) |
| DELETE | `/imoveis/{imovel_id}/comodos/{comodo_id}` | role | admin, gestor | **não** | app/routers/imoveis.py:316 (delete_comodo) |
| GET | `/problemas/{problema_id}` | auth |  | sim | app/routers/problemas.py:38 (get_problema_by_id) |
| PATCH | `/problemas/{problema_id}/status` | role | admin, gestor | **não** | app/routers/problemas.py:56 (atualizar_status_problema) |
| POST | `/problemas/{problema_id}/atualizacoes` | role | admin, gestor | **não** | app/routers/problemas.py:94 (criar_atualizacao) |
| GET | `/problemas/{problema_id}/atualizacoes` | auth |  | **não** | app/routers/problemas.py:172 (listar_atualizacoes) |
| GET | `/usuarios/me` | auth |  | sim | app/routers/usuarios.py:53 (me) |
| PATCH | `/usuarios/me` | auth |  | sim | app/routers/usuarios.py:58 (update_me) |
| PUT | `/usuarios/me/senha` | auth |  | sim | app/routers/usuarios.py:94 (alterar_senha_me) |
| POST | `/usuarios/me/mfa/setup` | auth |  | sim | app/routers/usuarios.py:116 (mfa_setup_me) |
| POST | `/usuarios/me/mfa/enable` | auth |  | sim | app/routers/usuarios.py:122 (mfa_enable_me) |
| DELETE | `/usuarios/me/mfa` | auth |  | sim | app/routers/usuarios.py:146 (mfa_disable_me) |
| GET | `/usuarios` | role | admin, gestor | sim | app/routers/usuarios.py:173 (list_usuarios) |
| GET | `/usuarios/{usuario_id}` | role | admin, gestor | sim | app/routers/usuarios.py:189 (get_usuario) |
| PUT | `/usuarios/{usuario_id}` | role | admin, gestor | sim | app/routers/usuarios.py:201 (update_usuario) |
| DELETE | `/usuarios/{usuario_id}` | role | admin, gestor | sim | app/routers/usuarios.py:255 (delete_usuario) |
| POST | `/usuarios/{usuario_id}/mfa/enable` | role | admin, gestor | **não** | app/routers/usuarios.py:278 (mfa_enable_usuario) |
| POST | `/usuarios/{usuario_id}/mfa/habilitar` | role | admin, gestor | **não** | app/routers/usuarios.py:279 (mfa_enable_usuario) |
| DELETE | `/usuarios/{usuario_id}/mfa` | role | admin, gestor | **não** | app/routers/usuarios.py:303 (mfa_reset_usuario) |
| POST | `/usuarios/{usuario_id}/mfa/desabilitar` | role | admin, gestor | **não** | app/routers/usuarios.py:304 (mfa_reset_usuario) |
| POST | `/usuarios` | role | admin, gestor | sim | app/routers/usuarios.py:322 (create_usuario) |

## Modelos de dados (candidatos a ativos)

| Modelo | Campos | Campos sensíveis | Local |
|---|---|---|---|
| Usuario | 12 | cpf, email, mfa_enabled, mfa_secret, mfa_secret_pendente, senha_hash, token_version | app/models.py:26 |
| RefreshToken | 5 | token_hash | app/models.py:47 |
| Imovel | 11 | - | app/models.py:59 |
| Endereco | 14 | cep, latitude, longitude | app/models.py:78 |
| ImovelComodo | 5 | - | app/models.py:99 |
| Contrato | 8 | - | app/models.py:111 |
| AgendamentoVistoria | 6 | - | app/models.py:128 |
| Checklist | 7 | - | app/models.py:141 |
| AceiteChecklist | 6 | - | app/models.py:157 |
| ChecklistItem | 6 | - | app/models.py:171 |
| ChecklistItemFoto | 4 | - | app/models.py:188 |
| ItemVistoria | 3 | - | app/models.py:199 |
| Problema | 9 | - | app/models.py:207 |
| AtualizacaoProblema | 6 | - | app/models.py:225 |
| LogOperacao | 9 | ip | app/models.py:239 |

## Pontos de atenção

- 8 rota(s) sem indício de autenticação: confirme quais são públicas por design (login, health, docs).
- 37 rota(s) sem teste aparente.
- 4 modelo(s) com campos sensíveis: entram no inventário de ativos (docs/risks/asset-inventory.md).
