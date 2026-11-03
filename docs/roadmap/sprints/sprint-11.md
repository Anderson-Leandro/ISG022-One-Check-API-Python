# Sprint 11 (retroativa)

- **Período:** 2026-10-21 → 2026-11-03 · **Status:** closed (fechada em 2026-11-02)
- **Sprint Goal:** Corrigir as pendências e os 16 achados da auditoria completa; adotar a gestão ágil
- **Comprometido:** 64 pts

> Sprint reconstruída na adoção (02/11/2026) a partir das datas dos commits. Não houve planejamento
> formal na época: o "comprometido" é o que foi entregue, e as estimativas dos itens SEC foram feitas
> depois.

## Itens
| ID | Título | Est. | Seg. | Status |
|---|---|---|---|---|
| SEC-021 | [N1, N2] Bypass de MFA com token de verificação e reset do banco via /admin/seed | 3 | high | done |
| SEC-022 | [N3, N4, N5] Autorização de checklists, escalada do gestor e desativação de MFA | 5 | high | done |
| SEC-023 | [Itens 1, 2, 6] Setup de MFA pendente, listagem de usuários e BOLA em problemas | 3 | high | done |
| SEC-024 | [N6, N7, N8] Limite de tentativas, validação de uploads e segredos sem valor padrão | 5 | high | done |
| SEC-001 | Seed automático cria admin com senha e segredo MFA públicos | 3 | high | done |
| SEC-002 | Pillow 11.1.0 com CVEs críticas e Image.open aceita qualquer formato do upload | 2 | high | done |
| SEC-003 | DoS anônimo: multipart processado antes da autenticação, sem limite de corpo e com dependências vulneráveis | 2 | high | done |
| SEC-004 | Leitura por ID ignora o vínculo do vistoriador (contratos, agendamentos, imóveis) | 3 | medium | done |
| SEC-005 | Troca de senha e reset de MFA não revogam as sessões existentes | 3 | medium | done |
| SEC-006 | Outras dependências com CVEs e sem lockfile (dependências transitivas não verificadas) | 2 | medium | done |
| SEC-007 | Hardening HTTP: CORS * com credenciais, /docs público e sem cabeçalhos de segurança | 3 | low | done |
| SEC-008 | Container roda como root e CI usa actions por tag mutável sem permissions | 2 | low | done |
| SEC-009 | Banco SQLite versionado em repositório público | 1 | low | done |
| SEC-010 | Trilha de auditoria incompleta (sem IP, sem o que mudou nas alterações de usuário) | 5 | low | done |
| SEC-011 | Política de senha fraca | 2 | low | done |
| SEC-012 | Regras de negócio sem validação no servidor e dashboard global | 3 | low | done |
| SEC-013 | Enumeração de e-mails pelo tempo de resposta do login | 1 | low | done |
| SEC-014 | CPF em texto puro, sem validação e devolvido em toda resposta de usuário | 5 | low | done |
| SEC-015 | Admin escolhe e conhece o segredo TOTP de outro usuário | 3 | low | done |
| SEC-016 | Cópias antigas e vulneráveis do código na raiz do repositório | 1 | low | done |
| TK-001 | Manter threat model e baseline alinhados ao backlog | 2 | low | done |
| TK-013 | Docker Compose, .dockerignore e .env.example sem segredos | 2 | low | done |
| TK-014 | Adoção da gestão ágil: roadmap, backlog, riscos, ADRs e auditoria diff | 3 | low | done |

## Acompanhamento
| Data | Andamento | Impedimentos | Decisões (→ ADR?) |
|---|---|---|---|
| 2026-10-25 | Validação do PENDENCIAS_API.md; correções N1–N8 e itens 1, 2 e 6; auditoria completa (16 achados); SEC-001 a SEC-005 | — | — |
| 2026-10-26 | SEC-006 a SEC-009 e SEC-016 | — | lockfile com hashes; actions por SHA |
| 2026-10-30 | SEC-010 a SEC-013 | — | — |
| 2026-11-01 | SEC-014, SEC-015; compose e `.env.example` (TK-013) | — | nome do projeto no compose: `api-python` |
| 2026-11-02 | Adoção da gestão ágil e auditoria diff (TK-014); sprints retroativas | — | riscos R-012 e R-013 aceitos (confirmar) |

## Sprint Review (2026-11-02)
- **Incremento demonstrável:** as pendências do PENDENCIAS_API.md que eram falhas de segurança (N1–N8, itens 1, 2 e 6) e os 16 achados da auditoria de 25/10 corrigidos, cada um com teste de cenário negado e relatório `correcao-*.md`; compose sem segredos; gestão ágil adotada (roadmap, backlog, riscos, ADRs).
- **Goal atingido?** **sim.** Os 23 itens (64 pts) estão na `main`:
  - SEC-001 a SEC-010, SEC-013, SEC-016, SEC-021 a SEC-024 e TK-001 pelo PR #10 (`c1718d6`, 30/10);
  - SEC-011, SEC-012, SEC-014, SEC-015, TK-013 e TK-014 pelo PR #11 (`d633d9f`, 02/11).
- **Evidências:** commits `0e164b8` a `29045fa`; PRs #10 e #11; 824 testes, 95% de cobertura; relatórios `docs/security/correcao-*.md`; `docs/security/relatorio-2026-11-02.md`.
- **Checagem de segurança:** auditoria diff de 02/11 (base `f081c60`, gitleaks incluído) com 2 achados baixos (SEC-017, SEC-018) e 2 informativos (SEC-019, SEC-020), já planejados para a Sprint 13. Nenhum padrão de segredo no commit `29045fa`.
- **Ponto de atenção da DoD:** os PRs #10 e #11 foram abertos e mergeados pelo autor, sem revisão de outra pessoa. O acordo de trabalho de time, que exige essa revisão, foi definido em 02/11 e passa a valer na Sprint 12. Levado para a retrospectiva. **Atualização (02/11):** o time decidiu depois que o PR não exige aprovação de outra pessoa; o merge pelo próprio autor passa a ser permitido.
- **Feedback do PO (Gabriel Henrique Santana):** <!-- a registrar -->

## Retrospectiva (2026-11-02)
Proposta a partir dos dados da sprint; ajuste com o time se algo não refletir a percepção de todos.

| Funcionou bem | Melhorar | Ação (vira item no backlog) |
|---|---|---|
| Correção guiada por teste: cada achado ganhou um teste de cenário negado que falhava antes da correção, e os 11 relatórios `correcao-*.md` deixaram claro o antes e o depois | PRs #10 e #11 foram mergeados pelo próprio autor, sem revisão | **TK-017**: proteger a `main` com PR, 1 aprovação e CI obrigatório (Sprint 12) |
| Commits pequenos por grupo de achados, citando os IDs: rastrear o que foi corrigido onde foi direto | Quatro commits ficaram só na `dev` até o último dia; o goal quase saiu parcial por falta de integração, não de trabalho | Abrir o PR para a `main` ao terminar cada item ou grupo de itens, não só no fim da sprint (combinar com o time e, se aprovado, incluir no acordo de trabalho) |
| Auditoria (completa no início, diff no fim) deu uma lista objetiva do que fazer e confirmou que nada novo e grave entrou | Planejamento só foi formalizado no fim da sprint; o trabalho de 25/10 a 01/11 não tinha backlog nem goal prévio | A partir da Sprint 12, planejar no primeiro dia com `/sprint-manager plan` e registrar o acompanhamento com `track` |

**Atualização (02/11):** depois da retro, o time decidiu que o PR não exige aprovação de outra pessoa. O TK-017 foi ajustado para exigir só o PR e o CI verde.

**Ações da retrospectiva anterior:** não houve retrospectiva antes desta.

## Métricas
- **Velocity:** 64 pts entregues de 64 comprometidos (23 itens).
- **Itens que voltaram ao backlog:** nenhum.
- **Observação:** a sprint foi reconstruída depois do trabalho feito. O "comprometido" é igual ao entregue, e as estimativas dos itens SEC foram dadas depois; por isso o número não serve de base para a capacidade das próximas sprints.
