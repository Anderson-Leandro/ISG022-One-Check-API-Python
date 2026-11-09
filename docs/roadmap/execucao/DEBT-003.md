# DEBT-003 — Consolidar as rotas duplicadas de MFA e remover GET /auth/mfa/setup

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 13 · **Issue:** #79 · **Branch:** `refactor/DEBT-003-rotas-mfa-canonicas` · **PR:** #201

## Entrega
Decisão do usuário (PO) em 2026-11-08, registrada no ADR-0013: as rotas se separam pelo ator, e os aliases saem em 2027-01-31.
- **Canônicas:**
  - o próprio MFA em `/auth/mfa/*` (`setup`, `activate`, `habilitar`, `desabilitar`), com o segredo pendente no servidor;
  - o MFA de outro usuário em `/usuarios/{id}/mfa` (`POST /enable` e `DELETE`).
- **Obsoletas até 2027-01-31:** `POST /usuarios/me/mfa/setup`, `POST /usuarios/me/mfa/enable`, `DELETE /usuarios/me/mfa`, `POST /usuarios/{id}/mfa/habilitar`, `POST /usuarios/{id}/mfa/desabilitar` e `POST /auth/mfa/disable`.
  - O comportamento não muda. No OpenAPI, `deprecated: true` com a data na descrição.
  - A tabela de `app/obsoletas.py` é a única fonte: ela marca o OpenAPI gerado e alimenta um middleware ASGI. Esse middleware põe `Deprecation` e `Sunset` em toda resposta das obsoletas, inclusive `401` e `403`, e também `Link rel="successor-version"`, com o mesmo id da requisição, codificado. O `Link` fica de fora quando a sucessora depende do corpo (`/auth/mfa/disable`). O CORS expõe os três cabeçalhos.
  - Um teste confere que as rotas marcadas no OpenAPI são exatamente as da tabela.
- **Removida:** `GET /auth/mfa/setup` responde `405` e não gera segredo.

| Critério de aceite | Prova |
|---|---|
| Cada operação de MFA tem uma rota canônica; os aliases estão marcados como deprecated, com data de remoção | `TestOpenapi` (cada alias com `deprecated` e `2027-01-31`; as canônicas sem) e `TestCabecalhos` (`Deprecation`, `Sunset` e `Link` nos aliases, mesmo sem login; nada nas canônicas; o alias continua funcionando); ADR-0013 |
| `GET /auth/mfa/setup` é removido depois de avisar o front | `TestGetSetupRemovido` (`405`, o segredo pendente não muda, só o POST no OpenAPI); aviso no `MUDANCAS_API_PARA_FRONT.md` (local), item 42 |

## Testes
- **Novos:** 42 testes em `tests/integration/test_rotas_mfa_canonicas.py`. Antes da mudança falhavam os do GET (que respondia 200), os do OpenAPI e os dos cabeçalhos. Entram também os cenários negados: o GET não grava, e uma rota parecida ou canônica não recebe aviso (`TestSucessora`).
- **Suíte completa:** 1221 passaram, 3 pulados, cobertura 96%. Rodada numa cópia sem o arquivo de segredos local.
- **Collection do Insomnia:** o caso "Admin não reseta o próprio MFA" passa para a rota canônica (`DELETE /usuarios/{id}/mfa`, `403`); 166/166 contra a API local da cópia.

## Segurança
- `/security-audit diff dev` em 2026-11-08: os 7 scanners com status `ok`. **Nenhum achado novo.** O SHA-1 do `gerar_collection.py` (id determinístico da collection), os valores fictícios do teste de credenciais do seed, o arquivo local fora do git e o DS026 do Dockerfile já existiam.
- Superfície de ataque mínima: uma rota por operação, com data para tirar as repetidas. Sai o `GET` que gravava estado, que também podia ser disparado por um link ou por um pré-carregamento do navegador (a autenticação é por header, o que já limitava o caso).
- As rotas obsoletas mantêm as mesmas regras de autorização até a remoção: nenhuma ganha nem perde permissão neste item.
- `/code-review` (medium), com 8 apontamentos:
  - **Corrigidos:**
    - o id do `Link` agora é codificado, para que uma URL montada não injete parâmetros no cabeçalho nem quebre a resposta com caracteres de controle;
    - `me` não conta como id;
    - cada linha da tabela diz se leva `Link`, sem depender do nome do marcador;
    - a tabela vira a única fonte do OpenAPI e dos cabeçalhos (antes o caminho se repetia nos decoradores), com um teste que a confere contra as rotas;
    - o método é comparado antes da expressão regular;
    - o ADR e o README explicam quando o `Link` fica de fora.
  - **Sem mudança:** o `Link` só leva a URL. O método da sucessora, que muda em duas rotas, está na descrição do OpenAPI e no README, porque o cabeçalho não tem campo para ele.

## Checklist antes da revisão
- [x] Campos que o perfil que ganha acesso passa a ver: nenhum perfil ganha acesso. Os cabeçalhos novos só dizem a data e a rota sucessora, que já estão no OpenAPI.
- [-] Status finais: não se aplica, nenhuma regra de status muda.
- [x] Autorização antes de ler o corpo: o middleware só acrescenta cabeçalhos na resposta e não lê o corpo. A autorização de cada rota não muda.
- [x] Login, refresh e tokens: o fluxo do login (`verify`, `setup-login`, `activate-login`) não muda. O `GET /auth/mfa/setup` removido usava o access token, e o `POST` continua igual.
- [x] Perfis proibidos barrados antes da busca por ID: as rotas não mudam de ordem de checagem; o aviso vale mesmo para o `401`, sem revelar nada além da sucessora.

## Testes existentes alterados
O `GET /auth/mfa/setup` deixa de existir, então 3 testes que o chamavam passam a usar o `POST /auth/mfa/setup`, que tem o mesmo comportamento. A remoção do GET está coberta pelo teste novo `test_get_responde_405_e_nao_gera_segredo`.

| Arquivo :: teste | Antes | Depois | Por que precisa mudar | O comportamento atual quebra? |
|---|---|---|---|---|
| `tests/integration/test_seguranca_mfa_setup.py` :: `TestSetupNaoSobrescreve::test_setup_preserva_segredo_ativo` | parametrizado com `get` e `post`: os dois preservam o segredo ativo e gravam o pendente | só o `post` (as mesmas asserções) | o caso `get` agora recebe `405`; o comportamento do GET é conferido no teste novo | Não. Só o GET, removido por decisão do item |
| `tests/integration/test_seguranca_mfa_setup.py` :: `TestSetupNaoSobrescreve::test_setup_abandonado_nao_tranca_o_usuario` | setup abandonado via `GET` | via `POST` | com o GET em `405`, o teste passaria sem testar nada: um setup que nunca aconteceu não tranca ninguém | Não |
| `tests/integration/test_auth_routes.py` :: `TestMfaExtended::test_mfa_setup_e_activate_autenticado` | setup via `GET` e activate | setup via `POST` e activate (as mesmas asserções) | o GET responde `405` | Não |

Nenhuma alteração enfraquece um teste: as asserções são as mesmas e passam a valer para a rota que continua existindo.

Aprovado por: Anderson em 2026-11-08

## Documentação
- `docs/adr/0013-rotas-canonicas-de-mfa.md` (novo).
- `README.md`: o mapa de rotas marca as obsoletas, com a data e a sucessora, e explica os cabeçalhos.
- Collection do Insomnia: o caso do reset do próprio MFA passa para a rota canônica.
- `MUDANCAS_API_PARA_FRONT.md` (local, fora do git): item 42; sai da seção "Ainda em aberto" a linha do `GET /auth/mfa/setup`.
