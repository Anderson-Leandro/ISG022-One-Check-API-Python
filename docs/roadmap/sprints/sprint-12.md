# Sprint 12

- **Período:** 2026-11-04 → 2026-11-17
- **Sprint Goal:** Release v0.1.0, produção segura e escopo da F4 fechado
- **Capacidade:** 40 pts (era 32, pelo prazo final de 11/12; ampliada em 2026-11-07 para incluir os itens da avaliação dos testes) · **Comprometido:** 40 pts
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
| SPK-005 | Avaliar a qualidade e a cobertura real da suíte de testes | 3 | medium | in_sprint |
| SEC-032 | Testes de negação de acesso aos checklists por quem não é dono | 3 | high | in_sprint |
| SEC-033 | Testes das travas do checklist depois do envio para aceite | 2 | medium | in_sprint |
| SEC-034 | Testes de sessão revogada no setup de MFA e do teto de chaves do limitador | 2 | low | in_sprint |
| DEBT-011 | Testes de negação por perfil em todas as rotas restritas | 3 | medium | in_sprint |
| DEBT-012 | Testes de negação em escrita conferem o estado e o status exato | 3 | low | in_sprint |

## Ordem sugerida
1. TK-002 e TK-003 (produção; risco alto R-006): primeiro dia.
2. TK-017 e DEBT-007 (proteção da `main` e tag v0.1.0).
3. DEBT-006, DEBT-009 e os spikes SPK-001 a SPK-004 (decisões viram ADR).
4. SPK-005 (avaliação dos testes), antes de escrever código novo nas histórias.
5. SEC-032 (negação de acesso aos checklists), logo depois do SPK-005; em seguida SEC-033, DEBT-011, DEBT-012 e SEC-034.
6. US-015 e US-017.

**Aviso do planejamento:** SPK-002 tem impacto de segurança médio sem critério de cenário negado. Por ser spike, o resultado é a decisão (ADR) sobre as fotos públicas, e não código.

## Acompanhamento
<!-- Uma linha por dia/sessão: data — o que avançou — impedimentos — decisões -->
| Data | Andamento | Impedimentos | Decisões (→ ADR?) |
|---|---|---|---|
| 2026-11-02 | Sprint planejada (13 itens, 32 pts) | — | capacidade de 32 pts pelo prazo |
| 2026-11-03 | SPK-005 (avaliação dos testes, 3 pts) entra no lugar do US-016 (8 pts), que volta ao backlog sem sprint; comprometido passa a 27 pts | — | avaliar a suíte antes de continuar |
| 2026-11-02 | SPK-005 em andamento: relatório `docs/quality/avaliacao-testes-2026-11-02.md` (ramos 83,7%, matriz de autorização, mutação 96,6% nos módulos críticos). Novos itens SEC-032 a SEC-034, DEBT-011 e DEBT-012; DEBT-010 refinado | o mutmut não muta handlers com decorador | itens novos ficam fora da sprint (decidir no refinamento) |
| 2026-11-07 | SEC-032, SEC-033, SEC-034, DEBT-011 e DEBT-012 (13 pts) entram na sprint; comprometido passa de 27 para 40 pts | carga acima da capacidade de 32 | decisão do time: priorizar os testes de negação nesta sprint |
| 2026-11-07 | SPK-005 concluído (#109, #113). Collection do Insomnia para testes manuais (#110, 168 requisições). DEBT-013 registrado fora da sprint (#111, issue #112). DEBT-014 entra na sprint (5 pts, comprometido 45) e é concluído no mesmo dia: erros de negócio com status HTTP adequado (#115, #116; 836 testes, cobertura 95%). Restam 37 pts | TK-002 e TK-003 dependem de acesso ao Render (só o TL). | ADR-0003: status HTTP dos erros de negócio; 401 só sem sessão válida, reautenticação recusada responde 403 |
| 2026-11-07 | TK-017 concluído (#123): ruleset ativo em main e dev, com merge só por PR, checks `test` e `dependencias` obrigatórios, sem force-push e sem exceções; push direto recusado no teste (GH013). Primeiro item executado pelo `sprint-executor`. Restam 36 pts | — | escopo ampliado para a dev (aprovado pelo usuário); no modo confirmar cada item, o merge é do usuário |

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
