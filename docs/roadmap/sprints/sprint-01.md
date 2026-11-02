# Sprint 01 (retroativa)

- **Período:** 2026-06-03 → 2026-06-16 · **Status:** closed
- **Sprint Goal:** Primeira versão da API no ar, com testes de integração e CI
- **Comprometido:** 14 pts

> Sprint reconstruída na adoção (02/11/2026) a partir das datas dos commits. Não houve planejamento
> formal na época: o "comprometido" é o que foi entregue, e as estimativas dos itens SEC foram feitas
> depois.

## Itens
| ID | Título | Est. | Seg. | Status |
|---|---|---|---|---|
| TK-007 | Primeira versão da API em FastAPI | 8 | low | done |
| TK-008 | Infraestrutura de testes, testes de integração e CI | 5 | low | done |
| TK-009 | README inicial do projeto | 1 | none | done |

## Sprint Review (retroativa)
- **Incremento:** API FastAPI com as rotas iniciais de todos os módulos, Dockerfile, testes de integração por router e CI no GitHub Actions.
- **Goal atingido?** sim.
- **Evidências:** commits `ab390a3` a `ccdcd1e` (Gabriel Henrique); PR #1 com os testes (`1d4291f` a `b76aa5a`); README `25381a2`.
- **Checagem de segurança:** não houve. Os `__pycache__` e o banco SQLite versionados aqui só foram removidos na Sprint 11 (SEC-009, SEC-016).

## Depois desta sprint
As Sprints 2 a 6 (17/06 a 25/08) não têm nenhum commit.
