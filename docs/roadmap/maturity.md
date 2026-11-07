# Diagnóstico de Maturidade — OneCheck API

- **Data:** 2026-11-02 · **Pontuação:** 10/20 antes da adoção → 13/20 depois dela. A adoção acrescentou o backlog estruturado, os templates de PR e Issue e os ADRs. A auditoria de hoje foi em modo diff, e o diagnóstico só conta auditoria completa como recente (TK-006).
- Gerado pela skill `project-kickoff adopt` (base: `diagnose.py`). Cada lacuna virou um item `DEBT-`.

## Retrato atual
- **Stack:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 16 / SQLite, PyJWT, bcrypt, pyotp e Pillow (ADR-0002).
- **Tamanho:** 77 arquivos `.py`, 42 de testes, 82 rotas e 15 modelos.
- **Histórico:**
  - 52 commits, de 2026-06-03 a 2026-11-01, com 3 nomes de autor (Anderson e Anderson-Leandro são a mesma pessoa; Gabriel Henrique fez a primeira versão da API em junho, e os testes vieram no PR #1, da branch `gbhenri20/feature/testes`);
  - nenhuma tag;
  - 46% dos commits em Conventional Commits.
- **CI:** `.github/workflows/tests.yml` roda os testes em PostgreSQL, com `pip-audit`, `permissions: contents: read` e actions fixadas por SHA.
- **Testes:** 824, com 94,7% de cobertura de linhas e 83,7% de ramos; mutação de 96,6% em `auth`, `deps`, `rate_limit` e checklists. A avaliação de 2026-11-02 ([avaliacao-testes-2026-11-02.md](../quality/avaliacao-testes-2026-11-02.md)) achou lacunas nos testes de negação (SEC-032 a SEC-034, DEBT-011, DEBT-012).
- **Documentação:**
  - README completo;
  - arquitetura e threat model;
  - 11 relatórios de correção;
  - product backlog da disciplina.
- **Segurança:** os 16 achados da auditoria de 2026-10-25 e os itens N1–N8 estão corrigidos; a auditoria diff de 2026-11-02 está em aberto, com 2 achados baixos e 2 informativos.

## Checklist
| Área | Item | Situação | Item do backlog |
|---|---|---|---|
| docs | README com visão, execução e status | ✓ | — |
| docs | Licença definida | ✗ (repositório público sem `LICENSE`) | DEBT-006 |
| build | Manifesto de dependências | ✓ | — |
| build | Lockfile versionado | ✓ (`requirements.lock` com hashes) | — |
| qualidade | Testes automatizados | ✓ | — |
| qualidade | CI rodando testes/lint | ✓ testes · ✗ lint | DEBT-004 |
| qualidade | Lint/format configurado | ✗ | DEBT-004 |
| segurança | Atualização de dependências automatizada | ✗ (há `pip-audit` no CI, mas não Dependabot) | DEBT-005 |
| segurança | `.env` ignorado no git | ✓ (`.env` e `.env.*`, exceto `.env.example`) | — |
| segurança | Nenhum `.env` real versionado | ✓ (conferido também no histórico) | — |
| segurança | `.env.example` com valores fictícios | ✓ | — |
| segurança | Documentação de segurança / threat model | ✓ | — |
| segurança | Auditoria de segurança recente | parcial: diff de 2026-11-02 sobre a completa de 2026-10-25 | TK-006 (completa antes da v0.9.0); SEC-017 a SEC-020 |
| processo | Decisões registradas (ADRs) | parcial (ADR-0001 e 0002) | DEBT-009 |
| docs | Documentação de arquitetura | ✓ | — |
| processo | Templates de PR/Issue | ✓ (criados na adoção) | — |
| processo | Conventional Commits (≥ 70%) | ✗ (46%) | DEBT-008 |
| processo | Releases/tags | ✗ | DEBT-007 |
| docs | CHANGELOG | ✗ | DEBT-007 |
| processo | Backlog/roadmap estruturado | ✓ (criado na adoção) | — |

## Auditoria de segurança
- **Situação:** estava desatualizada, com 57 arquivos de código alterados desde `f081c60`. A última auditoria era a completa de 2026-10-25, com 16 achados, todos corrigidos.
- **Ação tomada:** `/security-audit diff f081c60` executada em 2026-11-02.
  - Relatório: [relatorio-2026-11-02.md](../security/relatorio-2026-11-02.md).
  - Achados: 0 críticos, altos ou médios; 2 baixos (SEC-017, SEC-018) e 2 informativos (SEC-019, SEC-020).

## Funcionalidades (código × git × testes × docs)
Detalhe completo em [feature-map.md](feature-map.md).

| Funcionalidade | Rotas/telas | Proteção (public/auth/role) | Testes | Git (commits, período) | Docs/pendências | Situação | Itens |
|---|---|---|---|---|---|---|---|
| Autenticação, MFA e sessões | 12 | 5/6/1 | 97–100% | 10, jun–out | README, N1, item 1 | implementada + testada | US-001, US-002 |
| Usuários | 15 | 0/6/9 | 99% | 10, jun–nov | N4, item 2 | implementada + testada | US-003 |
| Imóveis, endereço e cômodos | 13 | 0/4/9 | 95% | 7, jun–out | SEC-004 | implementada + testada | US-004, US-012 |
| Contratos e agendamentos | 15 | 0/6/9 | 93% / 84% | 15, jun–out | PENDENCIAS 5, 11, 12 | implementada; agendamentos com ramos sem teste | US-005, US-006, US-013, DEBT-010 |
| Checklists, fotos, aceite e PDF | 13 | 0/12/1 | 92% | 10, jun–out | N3, PENDENCIAS 8 | implementada + testada | US-007 a US-009, US-014 |
| Problemas e notificações | 6 | 0/4/2 | 91% | 4, set–out | item 6, PENDENCIAS 7, 9 | implementada + testada | US-010, DEBT-001 |
| Dashboard e logs | 2 | 0/1/1 | 91% | 5, jun–out | SEC-012 | implementada + testada; achados abertos | US-011, SEC-018, SEC-020 |
| Admin (seed) | 5 | 0/5/0 | 95% | 4, jun–out | N2, SEC-001 | implementada + testada | SEC-021 |
| Health e uploads | 3 | 3/0/0 | 100% | 4 | T-14 | públicas por design | SPK-002 |

### Pontos de segurança a confirmar
| Rota / local | Indício | Item |
|---|---|---|
| `render.yaml:18` (`FORWARDED_ALLOW_IPS=*`) | o uvicorn usa o primeiro IP do `X-Forwarded-For`; falta saber se o proxy do Render sobrescreve o cabeçalho | SEC-017 |
| `GET /logs` (`app/routers/dashboard.py:85`) | o gestor vê IP e acessos de todas as contas | SEC-018 |
| `GET /uploads/{arquivo}` | foto sem login, por decisão (T-14) | SPK-002 |
| perfil visualizador | leitura global (premissa do threat model) | SPK-001 |

## O que já foi feito (reconstruído do histórico)
| Épico | Entregas (commits/PRs) |
|---|---|
| EP-001 Identidade e Acesso | `5c7decd` (auth e MFA, paridade com a API PHP), `c6a7cae` (usuários); N1, N4, N5, itens 1 e 2; SEC-005, 011, 013, 014 e 015 |
| EP-002 Carteira Imobiliária | `f68c812` (geocoding, criação atômica, cômodos); SEC-004 |
| EP-003 Contratos e Agendamentos | `ee20607`, `52734f5`; PRs #2 e #3 |
| EP-004 Vistorias e Laudos | `c02f652`, `eeb6436`; PRs #4 e #5; N3; SEC-002 |
| EP-005 Ocorrências e Comunicação | `3d227e4`; PR #6; item 6; SEC-012 |
| EP-006 Auditoria, Segurança e Conformidade | `69d7dcb` (logs); `fbaf99e` (baseline e riscos); `6d3692a` (auditoria); SEC-001 a SEC-016 (`f009847` a `cf39ab8`) |
| EP-007 Fundação e Qualidade | testes de integração de jun/2026 (`149e0f8` a `b76aa5a`); README (`e85e0df`); product backlog (`db09944`) |
| EP-008 Operação e Deploy | `7719993` (container sem root, CI por SHA); `d0b5f35` (compose, `.dockerignore`, `.env.example`) |

## Pendências importadas
| Origem | Itens criados |
|---|---|
| `docs/security/findings-2026-10-25.json` | SEC-001 a SEC-016 (done, com o commit da correção) |
| `docs/security/findings-2026-11-02.json` | SEC-017 a SEC-020 (backlog) |
| `docs/security/validacao-pendencias-2026-10-25.md` (N1–N8) e `PENDENCIAS_API.md` (itens 1, 2, 6) | SEC-021 a SEC-024 (done) |
| `PENDENCIAS_API.md`, itens ainda em aberto | SPK-004 (itens 5, 7, 8 e 11), DEBT-001 (9), DEBT-002 (10), US-015, US-016, US-017 e DEBT-003 (12). Já resolvidos: item 3 (N3), item 4 (SEC-012) e item 6 (o vistoriador recebe 403 na listagem e por ID); o item 8 está em parte resolvido, porque o envio para aceite já exige item preenchido |
| `docs/product-backlog.md` | US-001 a US-014 (mesmos IDs, done); DOC-001 → TK-001. Os antigos SEC-001 a SEC-005 ficaram assim: 001 → SEC-004 e SEC-023; 002 → US-007 e SEC-022; 003 → SEC-010 (feito) e SEC-025 (append-only); 004 → SEC-024; 005 → SEC-026 |
| Riscos residuais dos relatórios de correção | TK-002, TK-003, TK-004, SEC-027 a SEC-031, SPK-001 a SPK-003 |
| Lacunas de maturidade | DEBT-004 a DEBT-010, TK-005, TK-006 |
| TODO/FIXME no código | nenhum |

## Fase do roadmap
O projeto foi posicionado em **F3** porque é a primeira fase com uma evidência de saída faltando: a **release v0.1.0**. Não há nenhuma tag no repositório (DEBT-007).
- **F0 a F2:** passaram a ter todas as evidências com a adoção. Na F2 ficam pendentes os ADRs retroativos (DEBT-009), mas o diagrama, o threat model e o ADR da stack existem.
- **F3:** já tem os testes de cenário permitido e negado e o threat model revisado.
- **F4 e F5:** estão praticamente cumpridas: testes de segurança, relatórios antes/depois, CI e relatório de scanner.

Com o DEBT-007 fechado (2 pontos), o projeto passa para a **F6**. As lacunas de lá são backup e restauração (TK-005), a rotação das credenciais de produção (TK-002), as decisões de risco (SPK-001 e SPK-002) e os achados SEC-017 e SEC-018.
