# DEBT-002 — response_model e nomes consistentes no OpenAPI

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 13 · **Issue:** #78 · **Branch:** `chore/DEBT-002-envelope-openapi` · **PR:** #212

## Entrega
- **`app/respostas.py` (novo):** os modelos das respostas, a partir dos serializadores: `Envelope[T]` (`sucesso`, `dados`, `paginacao`), `ErroResposta` (`sucesso`, `erro`, `erros`), `DetalheErro` e um modelo por recurso (usuário, imóvel, cômodo, contrato, agendamento, vistoria, problema, login e tokens).
- **21 rotas principais** declaram em `responses`, pela função `documentar`, o envelope de sucesso com o modelo de `dados` e os erros que cada uma devolve (400, 401, 403, 404, 409, 422 ou 429, conforme a rota): login, MFA e refresh; usuários; imóveis; contratos e seus agendamentos, vistorias e problemas; detalhe da vistoria e do problema.
- O `responses` só documenta. Usar `response_model` faria o FastAPI filtrar e validar a saída, então ficou de fora de propósito: as respostas da API não mudam.
- **Nomes** (o segundo critério):
  - **`role`/perfil:** a API usa só `role`, nas respostas, nos corpos e nos filtros. "Perfil" aparece apenas no texto das mensagens. O schema descreve os valores.
  - **`mfa_enabled`/`mfa_ativo`:** são campos diferentes, não divergentes, e passam a ter descrição no schema:
    - `mfa_enabled`: o MFA está ligado (exigido);
    - `mfa_configurado`: há um autenticador;
    - `mfa_ativo`: o login pede o código (os dois).
- **Achado:** os erros não seguem todos o mesmo formato. As regras de negócio usam o envelope, mas o `401` de token, o `403` de perfil (as dependências) e o `422` de corpo fora do schema respondem `{"detail": ...}`, no formato do FastAPI. O OpenAPI documenta os dois formatos (a união `ErroResposta | DetalheErro`, que o FastAPI publica como `anyOf`), em vez de prometer um só. Unificar muda o corpo desses erros e 35 asserções de testes existentes, então virou o **DEBT-020**, fora da sprint.

| Critério de aceite | Prova |
|---|---|
| As rotas principais declaram o envelope `{sucesso, dados, erro}` no OpenAPI | `test_rotas_principais_declaram_envelope_e_erros` (pelo menos 18 rotas com o envelope e os formatos de erro) e o teste de contrato: cada rota é chamada de verdade e a resposta é validada contra o modelo declarado, que recusa campo a mais (`test_usuarios`, `test_imoveis`, `test_contratos_e_filhos`, `test_login_e_refresh`, `test_login_com_mfa_tem_a_outra_forma`); os erros reais validados contra os dois formatos (`test_erros_seguem_um_dos_formatos_documentados`) |
| A divergência `role`/perfil e `mfa_ativo`/`mfa_enabled` está resolvida ou documentada | `test_campos_do_mfa_explicados_no_schema` (descrição de `role`, `mfa_enabled`, `mfa_configurado` e `mfa_ativo` no schema, que lista exatamente os campos do serializador) |

## Testes
- **Novos:** 17 testes em `tests/integration/test_openapi_respostas.py`, cobrindo também as criações (imóvel com endereço, contrato, vistoria e problema), o `mfa/verify` e as três formas do login. O teste de contrato avisa se um serializador ganhar ou perder um campo sem que o modelo acompanhe.
- **Suíte completa:** 1316 passaram, 4 pulados, cobertura 96%. Rodada numa cópia sem o arquivo de segredos local.
- **Collection do Insomnia:** não muda, porque nenhuma resposta muda.

## Segurança
- `/security-audit diff dev` em 2026-11-09: os 7 scanners com status `ok`. **Nenhum achado novo.** Os do gitleaks são o arquivo local fora do git e os valores fictícios do teste do seed; o DS026 do Dockerfile já existia.
- Documentação do contrato (OWASP API9:2023, inventário): o OpenAPI passa a mostrar o que cada rota devolve, inclusive os formatos de erro reais.
- O `/docs` e o `/openapi.json` continuam desligados em produção (`DOCS_ENABLED`): a documentação não amplia a superfície exposta.
- `/code-review` (medium), com 9 apontamentos:
  - **Corrigidos:**
    - o erro documentado juntava um `$ref` ao `anyOf` e, na prática, virava só o envelope: agora é a união de modelos, sem o wrapper do OpenAPI;
    - a criação de problema documentava um 200 vazio além do 201: agora declara `status_code=201`;
    - cada rota lista os próprios erros (inclusive 400, 409 e 429), sem 404 em listas e em `/me`;
    - as rotas e as formas de login que o teste de contrato não chamava;
    - `sucesso` obrigatório no schema.
  - **Sem mudança:**
    - o `ApiResponse` antigo de `app/schemas.py` continua, porque os testes existentes o usam;
    - o `DetalheErro` descreve o `detail` de forma genérica, até o DEBT-020 unificar os erros no envelope.

## Checklist antes da revisão
- [x] Campos que o perfil que ganha acesso passa a ver: ninguém ganha acesso; os modelos descrevem só o que já era devolvido, inclusive o CPF mascarado e a observação que o locatário não recebe.
- [-] Status finais: não se aplica.
- [-] Autorização antes de ler o corpo: não se aplica, nenhuma rota muda.
- [x] Login, refresh e tokens: as três formas da resposta do login (tokens, `mfa_required` e `mfa_setup_required`) e a do refresh estão no modelo e no teste de contrato.
- [-] Perfis proibidos barrados antes da busca por ID: não se aplica, nenhuma rota muda.

## Testes existentes alterados
Nenhum.

## Documentação
- O próprio OpenAPI (`/docs`, `/openapi.json`).
- Backlog: DEBT-020 (novo, fora da sprint).
