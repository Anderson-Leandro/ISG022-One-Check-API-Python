# DEBT-014 — Erros de negócio respondem com o status HTTP adequado em vez de 200

> Registro feito **depois** do merge, quando o `sprint-executor` foi criado. Na época, a alteração de testes
> existentes foi descrita ao usuário na resposta, mas sem este relatório nem aprovação formal antes do commit.

- **Sprint:** 12 · **Issue:** #114 · **Branches:** `chore/DEBT-014-status-http-erros`, `refactor/DEBT-014-status-http-erros` · **PRs:** #115, #116, #118 (correção dos testes de refresh)

## Entrega
- ADR-0003 (#115): o envelope continua e o status acompanha o resultado.
- `fail()` devolve `JSONResponse` com status de erro (padrão 400) e recusa status < 400; as 122 chamadas foram classificadas pela tabela do ADR (#116).
- Critérios de aceite: `fail()` nunca 2xx → `tests/unit/test_schemas.py`; guarda na suíte → `tests/conftest.py`; checklists alheios → 403 em `test_contratos.py`; 401 × 403 → `test_status_http_erros.py`; README e collection atualizados; item 30 no `MUDANCAS_API_PARA_FRONT.md`.

## Testes
- Novo: `tests/integration/test_status_http_erros.py` (uma amostra de cada linha da tabela, incluindo senha atual errada → 403 sem alterar a senha).
- Suíte completa: 836 passaram, 3 pulados, cobertura 95%, numa cópia sem `.env`. CI do #116 verde.
- Guarda conferida: voltar uma rota ao padrão antigo quebra a suíte apontando a rota.
- #118: 838 passaram, 3 pulados, cobertura 96%; CI verde.

## Segurança
- `/security-audit diff ed36a41` em 2026-11-07 ([relatório](../../security/relatorio-2026-11-07.md)): os 7 scanners com status `ok`; **0 crítico, 0 alto, 0 médio, 1 baixo, 3 info**.
- SEC-035 (baixo): o interceptor de 401 do front repete login e MFA recusados → item SEC-035 no backlog, fora da sprint (correção no `front-react`).
- SEC-036 a SEC-038 (info): SHA-1 só para IDs da collection; o hook é barreira de conveniência; 403 × 404 já distinguia pela mensagem. Registrados no relatório, sem item.
- A mudança não altera quem pode fazer o quê e melhora a detecção (A09:2021, CWE-393).

## Testes existentes alterados
| Arquivo :: teste | Antes | Depois | Por que precisa mudar | O comportamento atual quebra? |
|---|---|---|---|---|
| `tests/conftest.py` :: fixture `client` | `TestClient` | `ClienteComContratoDeErro` (falha se `sucesso:false` vier com 2xx) | Guarda do ADR-0003 em toda a suíte | Não: só torna os testes mais rígidos |
| `tests/integration/test_auth_routes.py` :: `test_login_resposta_http_200_mesmo_em_falha` → `test_login_falho_responde_401_com_envelope` | exigia 200 em login falho | exige 401 e o corpo exato | O teste fixava o padrão antigo, que o ADR-0003 troca | Muda de propósito: login recusado passa a 401 |
| `tests/integration/test_seguranca_rate_limit.py` :: `_esgota_conta` | cada login falho → 200 | → 401 | Mesmo motivo | Muda de propósito; o limite de tentativas continua testado igual |
| `tests/integration/test_seguranca_limite_corpo.py` :: `test_json_normal_continua_funcionando` | 200 | 401 e mensagem `Credenciais inválidas` | O teste prova que o JSON passa pelo limite de corpo; a resposta da rota mudou | Não: o limite de corpo continua igual |
| `tests/integration/test_seguranca_checklist_autorizacao.py` :: `test_vistoriador_inexistente_nao_gera_500` | 200 | 404 | Vistoriador inexistente é recurso não encontrado | Muda de propósito; continua sem 500 e sem gravar checklist |
| `tests/integration/test_problemas.py` :: `test_contrato_encerrado_retorna_422` → `_409` | 422 | 409, e confere que nada foi gravado | Conflito com o estado do contrato, como agendamentos e vistorias | Muda de propósito (único caso que já não era 200) |
| `tests/integration/test_dashboard.py` :: `test_seed_mode_refresh_data`, `test_refresh_retorna_resposta_json`, `test_put_e_patch_tambem_funcionam` | 200 e `"sucesso"` no corpo | `200 if sucesso else 409` (#116) | O refresh sem os usuários mínimos passou a 409 | **Ficou mais fraco:** aceitava os dois resultados. Corrigido no #118 (linha abaixo) |
| `tests/integration/test_dashboard.py` (#118) :: os 3 testes acima | `200 if sucesso else 409` | divididos em cenários explícitos: sem usuários mínimos → 409 e mensagem exata; depois do seed, com o admin autenticado → 200, `preservado = usuarios` e usuários mantidos; PUT e PATCH → 200 | Restaurar um teste que prova o resultado, em vez de aceitar qualquer um | Não: só testes; cobertura sobe de 95% para 96% |
| `tests/unit/test_schemas.py` :: 6 testes de `fail()` | liam o dicionário | leem o corpo do `JSONResponse` | `fail()` passou a devolver `JSONResponse` | Não: mesmas asserções sobre o corpo |

Aprovado por: Anderson Mendes Leandro em 2026-11-07 (relatório do #116 e correção do #118)

## Documentação
- README "Respostas" com a tabela nova; ADR-0003; collection do Insomnia regenerada (157/157 e 00a 11/11); `MUDANCAS_API_PARA_FRONT.md` item 30 (local).
