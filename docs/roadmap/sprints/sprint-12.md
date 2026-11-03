# Sprint 12

- **Período:** 2026-11-04 → 2026-11-17
- **Sprint Goal:** Release v0.1.0, produção segura e escopo da F4 fechado
- **Capacidade:** 32 pts (definida pelo prazo final de 11/12; a média de 44 das sprints retroativas não serve de base) · **Comprometido:** 32 pts
- **Time:** sem ausências; sem feriado em dia útil (15/11 é domingo)

> **Sprint Goal** é o "porquê" da sprint: se algum item não couber, o goal ajuda a decidir o que
> cortar sem perder o valor da entrega.

## Itens comprometidos
| ID | Título | Est. | Seg. | Status final |
|---|---|---|---|---|
| TK-002 | Rotacionar as credenciais de demonstração em produção | 1 | high | in_sprint |
| TK-003 | Configurar CORS_ORIGINS e conferir SEED_SECRET no Render | 1 | medium | in_sprint |
| TK-017 | Proteger a branch main: merge só por PR e com CI verde | 1 | low | in_sprint |
| DEBT-007 | CHANGELOG e release v0.1.0 | 2 | none | in_sprint |
| DEBT-006 | Definir a licença do repositório público | 1 | none | in_sprint |
| DEBT-009 | ADRs retroativos das decisões principais | 3 | low | in_sprint |
| SPK-001 | Definir o alcance do perfil visualizador | 2 | medium | in_sprint |
| SPK-002 | Decidir sobre as fotos públicas em /uploads (T-14) | 2 | medium | in_sprint |
| SPK-004 | Fechar as regras de negócio em aberto do PENDENCIAS_API.md (itens 5, 7, 8 e 11) | 2 | low | in_sprint |
| SPK-003 | Decidir se o MFA vale para locatário e visualizador | 1 | low | in_sprint |
| US-015 | Excluir checklist, contrato e problema criados por engano | 5 | medium | in_sprint |
| US-017 | Histórico do imóvel | 3 | low | in_sprint |
| US-016 | Anexos e assinatura de contrato | 8 | medium | in_sprint |

## Ordem sugerida
1. TK-002 e TK-003 (produção; risco alto R-006): primeiro dia.
2. TK-017 e DEBT-007 (proteção da `main` e tag v0.1.0).
3. DEBT-006, DEBT-009 e os spikes SPK-001 a SPK-004 (decisões viram ADR).
4. US-015, US-017 e US-016. Se faltar tempo, US-016 é o primeiro a sair.

**Aviso do planejamento:** SPK-002 tem impacto de segurança médio sem critério de cenário negado. Por ser spike, o resultado é a decisão (ADR) sobre as fotos públicas, e não código.

## Acompanhamento
<!-- Uma linha por dia/sessão: data — o que avançou — impedimentos — decisões -->
| Data | Andamento | Impedimentos | Decisões (→ ADR?) |
|---|---|---|---|
| 2026-11-02 | Sprint planejada (13 itens, 32 pts) | — | capacidade de 32 pts pelo prazo |

## Sprint Review
- **Incremento demonstrável:**
- **Goal atingido?** sim / parcial / não — por quê:
- **Evidências** (PRs, testes, prints, relatórios):
- **Checagem de segurança** (`/security-audit diff`, segredos, riscos novos):
- **Feedback do cliente/PO:**

## Retrospectiva
| Funcionou bem | Melhorar | Ação (vira item no backlog) |
|---|---|---|

## Métricas
- Velocity: — pts (comprometido 32)
- Itens que voltaram ao backlog:
