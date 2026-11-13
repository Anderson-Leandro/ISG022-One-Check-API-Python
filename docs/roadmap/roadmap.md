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
| 12 | 04/11 → 17/11 | fechada (08/11) | Release v0.1.0, produção segura e escopo da F4 fechado | 52 |
| 13 | 08/11 → 11/11 (planejada para 18/11 → 01/12) | fechada (11/11), 44/47 | Produção recriada com segurança, falhas abertas corrigidas e qualidade verificada no CI | 47 |
| 14 | 12/11 → 13/11 (planejada para 12/11 → 25/11) | fechada (13/11), 29/32 | Dados pessoais sob controle do titular, trilha de auditoria íntegra e erros da API num formato único | 32 |
| 15 | a partir de 14/11 → 11/12 (datas no planejamento) | prevista | Entrega: TK-018 e SEC-026 (fotos), TK-004, DEBT-019 (provado depois da release, porque o Dependabot lê a main), auditoria completa (TK-006), release candidata v0.9.0 (TK-015) e entrega final v1.0.0 (TK-016) | ~21 |

**Prazo final: 11/12/2026.** Todos os itens em aberto foram distribuídos nas Sprints 12 a 14 para caber nesse prazo, mesmo com carga acima do ritmo habitual; a velocity não foi usada como limite. Em 11/11, com a Sprint 13 fechada três semanas antes do previsto, o restante foi dividido em duas sprints (14 e 15), com o mesmo prazo final.

## Fases
| Fase | Foco | Sprints | Status | Evidências de saída |
|---|---|---|---|---|
| **F0 Fundação** | começar certo | 1, 11, 12 | concluída | README, CI (`tests.yml`) e testes na Sprint 1; `vision.md`, `working-agreement.md`, backlog com épicos e `.env.example` na 11; licença MIT (DEBT-006) e proteção da `main` e da `dev` (TK-017) na 12 |
| **F1 Requisitos e riscos** | o que construir e proteger | 7–8, 11 | concluída no kickoff | `initial-risks.md` (Sprint 7), `product-backlog.md` (8), `asset-inventory.md` e `risk-register.md` (11) |
| **F2 Arquitetura** | decidir antes de codar | 7, 11, 12 | concluída | `architecture-v1.md` (7), `threat-model.md` e ADR-0001/0002 (11); ADR-0003 a ADR-0012 (12), incluindo os retroativos do DEBT-009 |
| **F3 MVP + identidade e acesso** | fluxo de valor ponta a ponta | 1, 7 → 12 | concluída (08/11) | testes de cenário permitido e negado ✓, threat model revisado ✓, release v0.1.0 ✓ (tag `v0.1.0` na `main`, DEBT-007) |
| **F4 Funcionalidades + mitigações** | crescer com segurança | 7, 11 → 12 | concluída (08/11) | testes de segurança e relatórios `correcao-*.md` ✓ (Sprint 11); na Sprint 12, SPK-001 a SPK-004 decididos (ADR-0009 a 0012) e US-015, US-017 a US-020, SEC-036 e DEBT-015 entregues. US-016 (`could`) segue no backlog sem sprint |
| **F5 Qualidade e observabilidade** | confiar no que roda | 1, 11 → 12–13 | concluída (11/11) | 824 testes no CI, 95% de cobertura de linhas, scanners ✓. Na Sprint 12: avaliação da suíte (SPK-005) e as lacunas encontradas (SEC-032 a SEC-034, DEBT-011, DEBT-012); status HTTP dos erros de negócio (DEBT-014, ADR-0003). Na Sprint 13: lint (DEBT-004), Dependabot (DEBT-005), contrato OpenAPI (DEBT-001/002/003), DEBT-008 e DEBT-010 ✓; suíte com 1398 testes e cobertura de branches em 97%; scanners em cada item |
| **F6 Hardening e release** | preparar para produção | 11 → 13–15 | **em andamento** | compose sem segredos ✓ (Sprint 11); decisões SPK-001/002/003 ✓ (Sprint 12). Sprint 13: produção recriada (TK-002, TK-003) ✓, SEC-017 a SEC-020, SEC-027 e SEC-031 ✓. **Backup/restauração (TK-005) adiado: risco R-015 aceito até o primeiro dado real em produção; a F6 não fecha sem o backup ou uma nova decisão sobre o R-015.** Sprint 14: SEC-025, SEC-028 a SEC-030 ✓ (log append-only, direitos do titular, senhas fracas e vazadas). Sprint 15: TK-018, SEC-026, auditoria completa (TK-006) e v0.9.0 (TK-015) |
| **F7 Entrega e operação** | entregar e sustentar | 14 | a iniciar | TK-004, relatório final, roteiro de demo e v1.0.0 (TK-016) em 11/12 |

**Exceção à ordem das fases:** TK-002 e TK-003 são da F6 e estavam na Sprint 12 por causa do risco R-006. Foram para a Sprint 13 a pedido do usuário: o ambiente de produção não está em uso e será recriado.

## Marcos (releases)
| Marco | Conteúdo | Data prevista | Status |
|---|---|---|---|
| v0.1.0 | MVP completo, com as correções SEC-001 a SEC-016 e N1 a N8 e as entregas da Sprint 12 (`CHANGELOG.md`) | Sprint 12 | **lançado em 08/11/2026** (tag `v0.1.0` → `10cb306`, PR #172) |
| v0.9.0 | Release candidata: operação de produção (TK-002/003 ✓; TK-005 adiado, R-015 aceito), SEC-017/018 ✓, decisões de risco, auditoria completa | Sprint 15 (por volta de 07/12/2026) | planejado (TK-015) |
| v1.0.0 | Entrega final da disciplina, com relatório e demonstração | Sprint 15 (11/12/2026, prazo final) | planejado (TK-016) |

## Riscos ao roadmap
- **Produção no Render:** recriada e conferida na Sprint 13 (TK-002, TK-003, SEC-017). Continua sem backup (R-015 aceito), e o Postgres free tem prazo de expiração.
- **Front em outro repositório:** as mudanças de contrato da API (SEC-018, DEBT-001 a DEBT-003) precisam ser combinadas com o front.
- **Decisões de negócio** (SPK-001, SPK-002 e SPK-004) podem gerar itens novos.
- **Carga das Sprints 14 e 15 (32 e ~18 pts):** abaixo do ritmo das últimas sprints (53 pts). A Sprint 15 deixa folga para a auditoria, a release e o relatório final. Se faltar tempo, o primeiro candidato a sair é o SEC-026, que depende da decisão do TK-018 (painel do Render). O US-016 continua fora (`could`, precisa ser quebrado).
- **Plano gratuito do Render:** a instância hiberna e o limite de tentativas fica em memória (risco aceito R-012).

## Histórico de replanejamento
| Data | Mudança | Motivo |
|---|---|---|
| 2026-11-02 | Roadmap criado pela adoção (`project-kickoff adopt`) | Projeto existente, com auditoria diff no mesmo dia |
| 2026-11-02 | Sprints reconstruídas desde 03/06/2026 (Sprints 1 a 11) e pendências distribuídas nas Sprints 12 a 16 | Pedido do PO: calendário desde o início do projeto |
| 2026-11-02 | Sprints 15 e 16 removidas; todos os itens em aberto distribuídos nas Sprints 12 a 14, com a 14 encurtada para terminar em 11/12/2026 | Prazo final da entrega: 11/12/2026 |
| 2026-11-02 | Sprint 11 fechada com 64/64 pts; fase continua F3 (falta a v0.1.0). Retro gerou o TK-017, incluído na Sprint 12 | Fechamento da Sprint 11 |
| 2026-11-02 | PR deixa de exigir aprovação de outra pessoa; TK-017 passa a exigir só merge por PR e CI verde | Decisão do time |
| 2026-11-03 | SPK-005 (avaliação dos testes) entra na Sprint 12 no lugar do US-016, que volta ao backlog sem sprint | Avaliar a qualidade da suíte antes de continuar |
| 2026-11-07 | Itens da avaliação dos testes (SEC-032 a SEC-034, DEBT-011, DEBT-012; 13 pts) entram na Sprint 12, que vai a 40 pts | Decisão do time: fechar as lacunas de testes de negação antes de seguir |
| 2026-11-07 | DEBT-014 (status HTTP dos erros de negócio, 5 pts) entra na Sprint 12, que vai a 45 pts | Decisão do time (ADR-0003): o 200 com `sucesso:false` esconde abuso nos logs; fazer antes do DEBT-012 |
| 2026-11-08 | Decisões dos spikes SPK-001 a SPK-004 (ADR-0009 a ADR-0012); seis itens novos entram na Sprint 12, que vai a 54 pts | Decisões do PO |
| 2026-11-08 | TK-002 e TK-003 vão para a Sprint 13 (Sprint 12: 52 pts; Sprint 13: 38 pts) | Pedido do usuário: o ambiente de produção será recriado |
| 2026-11-08 | Sprint 12 fechada com 52/52 pts e a release v0.1.0 (tag na `main`). F0, F2, F3 e F4 concluídas; fase atual passa a F5. Retro gerou TK-019, TK-020 e DEBT-018 (backlog) | Fechamento da Sprint 12 |
| 2026-11-08 | Sprint 13 planejada: 47 pts (capacidade 50), com as ações da retro 12, SEC-035, BUG-001 e DEBT-017; goal "Produção recriada com segurança, falhas abertas corrigidas e qualidade verificada no CI" | Planejamento da Sprint 13 |
| 2026-11-10 | TK-005 (backup) adiado: risco R-015 aceito até o primeiro dado real em produção | Decisão do PO: produção só tem dados do seed |
| 2026-11-13 | Sprint 14 fechada com 29/32 pts; datas ajustadas para a execução (12/11 a 13/11). DEBT-019 movido para a Sprint 15 (só se prova depois da release, porque o Dependabot lê a main). Fase continua F6: faltam o backup (TK-005, R-015 aceito), a auditoria completa e a release. Retro gerou DEBT-023, TK-023 e duas regras no `sprint-executor` | Fechamento da Sprint 14 |
| 2026-11-11 | Sprint 14 replanejada para 12/11 a 25/11 (32 pts, sem itens que dependem do Render, por decisão do PO) e Sprint 15 criada (26/11 a 11/12) com TK-018, SEC-026, TK-004, TK-006, TK-015 e TK-016 | A Sprint 13 fechou três semanas antes do calendário |
| 2026-11-11 | Sprint 13 fechada com 44/47 pts; datas ajustadas para a execução (08/11 a 11/11). F5 concluída; fase atual passa a F6, que não fecha sem o backup (TK-005) ou outra decisão sobre o R-015. Retro gerou TK-021 e TK-022 (backlog) e uma regra no `sprint-executor` | Fechamento da Sprint 13 |
