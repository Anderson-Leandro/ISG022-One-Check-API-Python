# Roadmap — OneCheck API

> **Por que isso importa:** o roadmap mostra a ordem lógica de evolução. Cada fase termina com
> evidências verificáveis; segurança entra desde a F0, não no final.
> Fase atual: **F3** · Sprint de 14 dias · Atualizado em 2026-11-02

O projeto foi adotado com código pronto. As sprints foram reconstruídas desde o primeiro commit (03/06/2026), com 14 dias cada; o calendário completo está em [sprints.yaml](sprints.yaml) e os registros em [sprints/](sprints/). O motivo de a fase atual ser F3 está em [maturity.md](maturity.md#fase-do-roadmap).

## Calendário de sprints
| Sprint | Período | Status | Goal | Pontos |
|---|---|---|---|---|
| 1 | 03/06 → 16/06 | fechada (retroativa) | Primeira versão da API no ar, com testes de integração e CI | 14 |
| 2–6 | 17/06 → 25/08 | fechadas, sem commits | — | — |
| 7 | 26/08 → 08/09 | fechada (retroativa) | MVP completo: paridade com a API PHP e todos os módulos | 67 |
| 8 | 09/09 → 22/09 | fechada (retroativa) | Product backlog da disciplina registrado | 2 |
| 9–10 | 23/09 → 20/10 | fechadas, sem commits | — | — |
| 11 | 21/10 → 03/11 | fechada (retroativa) | Corrigir as pendências e os 16 achados da auditoria; adotar a gestão ágil | 64 |
| **12** | 04/11 → 17/11 | **ativa** | Release v0.1.0, produção segura e escopo da F4 fechado | 32 |
| 13 | 18/11 → 01/12 | planejada | Qualidade contínua e hardening | 36 |
| 14 | 02/12 → 11/12 (10 dias) | planejada | Conformidade, release candidata v0.9.0 e entrega final v1.0.0 | 31 |

**Prazo final: 11/12/2026.** Todos os itens em aberto foram distribuídos nas Sprints 12 a 14 para caber nesse prazo, mesmo com carga acima do ritmo habitual; a velocity não foi usada como limite.

## Fases
| Fase | Foco | Sprints | Status | Evidências de saída |
|---|---|---|---|---|
| **F0 Fundação** | começar certo | 1 (+ 12: licença) | concluída no kickoff | README, CI (`tests.yml`) e testes na Sprint 1; `vision.md`, `working-agreement.md`, backlog com épicos e `.env.example` na 11. Faltam: licença (DEBT-006) e proteção da `main` (TK-017, ação da retro 11), na Sprint 12 |
| **F1 Requisitos e riscos** | o que construir e proteger | 7–8, 11 | concluída no kickoff | `initial-risks.md` (Sprint 7), `product-backlog.md` (8), `asset-inventory.md` e `risk-register.md` (11) |
| **F2 Arquitetura** | decidir antes de codar | 7, 11 (+ 12: ADRs) | concluída (ADRs incompletos) | `architecture-v1.md` (7), `threat-model.md` e ADR-0001/0002 (11). ADRs retroativos: DEBT-009, Sprint 12 |
| **F3 MVP + identidade e acesso** | fluxo de valor ponta a ponta | 1, 7 → 12 | **em andamento** | testes de cenário permitido e negado ✓, threat model revisado ✓, **release v0.1.0 ✗ (DEBT-007, Sprint 12)** |
| **F4 Funcionalidades + mitigações** | crescer com segurança | 7, 11 → 12 | quase concluída | testes de segurança e relatórios `correcao-*.md` ✓ (Sprint 11). Na Sprint 12: SPK-004 e US-015 a US-017 |
| **F5 Qualidade e observabilidade** | confiar no que roda | 1, 11 → 13 | parcial | 824 testes no CI, 95% de cobertura, scanners ✓. Na Sprint 13: lint (DEBT-004), Dependabot (DEBT-005), contrato OpenAPI (DEBT-001/002/003), DEBT-008 e DEBT-010 |
| **F6 Hardening e release** | preparar para produção | 11 → 12–14 | a iniciar | compose sem segredos ✓ (Sprint 11). Sprint 12: TK-002, TK-003 e decisões SPK-001/002/003. Sprint 13: SEC-017 a SEC-020, SEC-027, SEC-031 e backup (TK-005). Sprint 14: SEC-025, SEC-026, SEC-028 a SEC-030, auditoria completa (TK-006) e v0.9.0 (TK-015) |
| **F7 Entrega e operação** | entregar e sustentar | 14 | a iniciar | TK-004, relatório final, roteiro de demo e v1.0.0 (TK-016) em 11/12 |

**Exceção à ordem das fases:** TK-002 e TK-003 são da F6, mas entram já na Sprint 12, porque o risco R-006 (contas do seed antigo com senha pública em produção) é alto.

## Marcos (releases)
| Marco | Conteúdo | Data prevista | Status |
|---|---|---|---|
| v0.1.0 | MVP completo, com as correções SEC-001 a SEC-016 e N1 a N8 (estado atual da `dev`) | Sprint 12 (até 17/11/2026) | planejado (DEBT-007) |
| v0.9.0 | Release candidata: operação de produção (TK-002/003/005), SEC-017/018, decisões de risco, auditoria completa | Sprint 14 (por volta de 07/12/2026) | planejado (TK-015) |
| v1.0.0 | Entrega final da disciplina, com relatório e demonstração | Sprint 14 (11/12/2026, prazo final) | planejado (TK-016) |

## Riscos ao roadmap
- **Produção no Render:** TK-002 e TK-003 dependem de acesso ao painel e ao banco de produção, e o SEC-017 depende de um teste lá.
- **Front em outro repositório:** as mudanças de contrato da API (SEC-018, DEBT-001 a DEBT-003) precisam ser combinadas com o front.
- **Decisões de negócio** (SPK-001, SPK-002 e SPK-004) podem gerar itens novos.
- **Carga das Sprints 12 a 14 (31 a 36 pts):** acima do ritmo habitual. Se faltar tempo, os primeiros candidatos a sair são US-016 e SEC-026 (`could`, exigem infraestrutura nova).
- **Plano gratuito do Render:** a instância hiberna e o limite de tentativas fica em memória (risco aceito R-012).

## Histórico de replanejamento
| Data | Mudança | Motivo |
|---|---|---|
| 2026-11-02 | Roadmap criado pela adoção (`project-kickoff adopt`) | Projeto existente, com auditoria diff no mesmo dia |
| 2026-11-02 | Sprints reconstruídas desde 03/06/2026 (Sprints 1 a 11) e pendências distribuídas nas Sprints 12 a 16 | Pedido do PO: calendário desde o início do projeto |
| 2026-11-02 | Sprints 15 e 16 removidas; todos os itens em aberto distribuídos nas Sprints 12 a 14, com a 14 encurtada para terminar em 11/12/2026 | Prazo final da entrega: 11/12/2026 |
| 2026-11-02 | Sprint 11 fechada com 64/64 pts; fase continua F3 (falta a v0.1.0). Retro gerou o TK-017, incluído na Sprint 12 | Fechamento da Sprint 11 |
| 2026-11-02 | PR deixa de exigir aprovação de outra pessoa; TK-017 passa a exigir só merge por PR e CI verde | Decisão do time |
