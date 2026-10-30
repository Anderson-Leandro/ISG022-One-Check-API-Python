# Correção dos itens 1, 2 e 6

- **Data:** 2026-10-25 · **Branch:** `dev` (sobre `8e4d12d`, alterações ainda não commitadas)
- **Origem:** [validação do PENDENCIAS_API.md](validacao-pendencias-2026-10-25.md), seção 1 (itens 1 e 2) e seção 2 (item 6).
- **Resultado:** **568 testes passam** (534 anteriores + 34 novos) em SQLite e em PostgreSQL 16. Os 34 testes novos foram escritos antes da correção: no código anterior, **24 falhavam**, e os 10 que passavam são caminhos legítimos que precisam continuar funcionando.

| Item | Falha | Antes | Depois |
|---|---|---|---|
| 1 | Setup de MFA sobrescrevia o autenticador ativo | Abrir "Reconfigurar autenticador" sem concluir trancava o usuário; com só o access token, dava para trocar o autenticador da vítima | O setup grava só o segredo pendente; trocar um autenticador ativo exige o código dele |
| 2 | Qualquer perfil listava todos os usuários | Locatário, vistoriador e visualizador recebiam nome, e-mail, CPF e MFA de todos (e `?role=admin`) | Listagem só para admin e gestor, como as demais rotas do recurso |
| 6 | BOLA em `/problemas/{id}` | Vistoriador e visualizador liam qualquer problema e suas atualizações pelo ID | Uma regra única para lista, criação e leitura por ID |

---

## Item 1 — Setup de MFA sobrescrevia o autenticador ativo

**Causa:** `GET /auth/mfa/setup` gravava o segredo novo direto em `mfa_secret`. O autenticador do celular deixava de valer no mesmo instante, antes de qualquer confirmação. Isso explica o incidente de 2026-10-24 com o admin de seed. Havia ainda um segundo problema: `POST /auth/mfa/activate` e `POST /usuarios/me/mfa/enable` trocavam o autenticador sem pedir prova de posse do atual. Assim, um access token roubado bastava para o atacante cadastrar o próprio autenticador e manter o acesso.

**Pilares:** Disponibilidade, Autenticidade · **STRIDE:** Denial of service, Spoofing · **CWE-308 / CWE-620** · **Princípios violados:** fail secure, semântica de GET sem efeito colateral.

| Arquivo | Mudança |
|---|---|
| `app/routers/auth_router.py` | O setup grava o segredo em `mfa_secret_pendente` (coluna criada em N1). Novo `POST /auth/mfa/setup`; o `GET` continua funcionando, marcado `deprecated` no OpenAPI. |
| `app/routers/auth_router.py` | `/auth/mfa/activate` confere o código contra o segredo **pendente** e só então o promove a `mfa_secret`, limpando o pendente. Sem setup pendente → `fail("Configuração MFA não encontrada")`. |
| `app/auth.py` | Novo `mfa_troca_error(user, codigo_atual)`: se o usuário já tem MFA ativo (`mfa_enabled` + segredo), exige o código TOTP do autenticador atual. |
| `app/schemas.py` | `MfaActivateRequest` e `MfaEnableRequest` ganham `codigo_atual` (opcional; obrigatório só na troca). |
| `app/routers/usuarios.py` | `POST /usuarios/me/mfa/enable` aplica a mesma regra de troca. |

Quem perdeu o celular não consegue mostrar o código atual. Nesse caso, o caminho é o reset feito por outro admin (N5), que força nova configuração no próximo login.

**Testes** — `tests/integration/test_seguranca_mfa_setup.py` (14):
- **Setup não sobrescreve:** `GET` e `POST` preservam `mfa_secret` e gravam o pendente; depois de um setup abandonado, o login com o autenticador antigo continua funcionando.
- **Troca via `/auth/mfa/activate`:** sem `codigo_atual`, com `codigo_atual` errado ou com código novo errado → falha, e o segredo ativo não muda; troca legítima promove o pendente; activate sem setup falha; o pendente não é reaproveitado.
- **Troca via `/usuarios/me/mfa/enable`:** sem `codigo_atual` ou com código errado → falha; com código correto → troca.
- **Primeira configuração:** sem MFA ativo, não exige `codigo_atual` (nas duas rotas).

---

## Item 2 — Qualquer perfil listava todos os usuários

**Causa:** `GET /usuarios` usava só `get_current_user`, enquanto as demais rotas do recurso usam `require_roles("admin", "gestor")`. `serialize_usuario` devolve CPF, e-mail e o estado do MFA.

**Pilares:** Confidencialidade, LGPD (minimização, art. 6º III) · **STRIDE:** Information disclosure · **OWASP API1/API3 · CWE-862 / CWE-200** · **Princípio violado:** menor privilégio.

| Arquivo | Mudança |
|---|---|
| `app/routers/usuarios.py` | `list_usuarios` passa a exigir `require_roles("admin", "gestor")`. |

**Testes** — `tests/integration/test_seguranca_listagem_usuarios.py` (8):
- locatário, vistoriador e visualizador → 403, com e sem `?role=admin`, e nenhum e-mail na resposta;
- admin e gestor → listagem com o filtro de perfil funcionando.

---

## Item 6 — BOLA no acesso a problemas por ID

**Causa:** havia duas regras de autorização para o mesmo recurso.
- `contratos._assert_pode_problema` (lista e criação) liberava admin, gestor e o locatário dono.
- `problemas._assert_pode_acessar_problema` (leitura por ID e atualizações) só restringia o locatário.

Quem não podia listar abria os problemas pelo ID.

**Pilar:** Confidencialidade · **STRIDE:** Information disclosure · **OWASP API1 · CWE-639** · **Princípio violado:** mediação completa.

| Arquivo | Mudança |
|---|---|
| `app/deps.py` | Novo `assert_acesso_problemas(contrato, user)`: **uma** regra para listar, registrar e ler problemas (admin, gestor ou o locatário dono do contrato). |
| `app/routers/contratos.py` | `_assert_pode_problema` removido; lista e criação usam o helper comum. |
| `app/routers/problemas.py` | `GET /problemas/{id}` e `GET /problemas/{id}/atualizacoes` usam o helper comum. |

Mantive a regra que já valia na listagem, então vistoriador e visualizador ficam sem acesso. O relatório de validação sugeria uma alternativa: liberar o vistoriador nos contratos em que ele tem checklist. Isso é decisão de negócio e, se aprovado, muda só o helper.

**Testes** — `tests/integration/test_seguranca_problemas_bola.py` (12):
- vistoriador e visualizador → 403 por ID e nas atualizações, sem o conteúdo do problema na resposta;
- **consistência:** para os cinco perfis, a lista, a leitura por ID e as atualizações dão a mesma resposta;
- admin, gestor e locatário dono continuam lendo o problema e as atualizações.

---

## Testes antigos ajustados (comportamento alterado de propósito)
| Teste | Antes | Agora |
|---|---|---|
| `test_usuarios.py::TestListUsuarios::test_lista_usuarios_autenticado` → `test_lista_usuarios_gestor` | Locatário listava os usuários | Gestor lista os usuários |

## Impacto no front e na API
| Mudança | O que o front precisa fazer |
|---|---|
| Novo `POST /auth/mfa/setup`; o `GET` está obsoleto | Trocar para `POST` (o `GET` ainda funciona, mas vai sair) |
| `POST /auth/mfa/activate` e `POST /usuarios/me/mfa/enable` exigem `codigo_atual` quando o usuário já tem MFA ativo | Na tela "Reconfigurar autenticador", pedir o código do autenticador **atual** além do código do novo |
| O segredo do setup só vale depois do activate | Nada: se o usuário sair no meio, o autenticador antigo continua valendo |
| `GET /usuarios` só para admin e gestor | Não chamar a listagem em telas de locatário, vistoriador ou visualizador |
| `GET /problemas/{id}` e `/atualizacoes` negam vistoriador e visualizador (403), como a lista | Esconder links para problemas nesses perfis |

## Riscos residuais
- Continua aberto o risco já registrado: em `POST /usuarios/{id}/mfa/setup` + `enable`, o admin escolhe e fica conhecendo o segredo TOTP de outro usuário.
- `GET /usuarios` para o gestor ainda devolve CPF. Se o gestor só precisa escolher locatários, um payload mínimo (`id`, `nome`) reduz a exposição. Isso se resolve com `response_model` (item 10).
- `codigo_atual` é mais um alvo de força bruta enquanto não houver rate limit (**N6**).
- Pendentes da fila: **N6**, **N7** e **N8**, além dos itens 4, 5 e 9.
