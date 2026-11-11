# Sprint 14

- **Período:** 2026-11-12 → 2026-11-25
- **Sprint Goal:** Dados pessoais sob controle do titular, trilha de auditoria íntegra e erros da API num formato único
- **Capacidade:** 53,3 pts, a média das Sprints 11 a 13 (64, 52 e 44) · **Comprometido:** 32 pts (60%)
- **Fora da sprint, por decisão do PO:** o TK-018 (fotos no disco do Render) fica fora, porque depende do painel do Render. Ele vai para a Sprint 15 com o SEC-026, TK-004, TK-006, TK-015 e TK-016. TK-005 (R-015 aceito) e US-016 (`could`, precisa ser quebrado) continuam no backlog.

> **Sprint Goal** é o "porquê" da sprint: se algum item não couber, o goal ajuda a decidir o que
> cortar sem perder o valor da entrega.

## Itens comprometidos
| ID | Título | Est. | Seg. | Status final |
|---|---|---|---|---|
| TK-021 | Merge pela interface do GitHub já com o título do PR (#n) | 1 | low | in_sprint |
| TK-022 | Script versionado que roda a suíte numa cópia sem o arquivo de segredos, do zero | 2 | low | in_sprint |
| SEC-025 | Log de auditoria append-only | 5 | medium | in_sprint |
| SEC-028 | Direitos do titular (LGPD): exportar e anonimizar os próprios dados | 5 | medium | in_sprint |
| DEBT-020 | Erros de autenticação, perfil e validação no mesmo envelope {sucesso, erro, erros} | 5 | low | in_sprint |
| SEC-029 | Forçar a troca das senhas fracas cadastradas antes da política | 3 | low | in_sprint |
| SEC-030 | Recusar senhas que aparecem em vazamentos conhecidos | 3 | low | in_sprint |
| DEBT-013 | Mensagem de erro específica para token de verificação usado no setup-login e no activate-login | 2 | low | in_sprint |
| BUG-002 | Foto enviada fica órfã no disco quando o pedido é recusado depois do upload | 2 | low | in_sprint |
| DEBT-019 | Lock que o Dependabot regenera sozinho, com as transitivas | 3 | low | in_sprint |
| DEBT-021 | Imagem base do Dockerfile fixada por digest e coberta pelo Dependabot | 1 | low | in_sprint |

## Ordem sugerida
1. **TK-021**: com ele, os merges pela interface do GitHub já saem com o título do PR (#n).
2. **TK-022**: a suíte numa cópia sem o arquivo de segredos, por script. Os itens seguintes já o usam.
3. **DEBT-020**: o envelope único para os erros. Vem antes do DEBT-013, que também muda erros, e dos itens de segurança, para os testes novos já lerem o formato final.
4. **SEC-025, SEC-028, SEC-029, SEC-030**: o goal (integridade da trilha e dados do titular).
5. **DEBT-013, BUG-002, DEBT-019, DEBT-021**: os demais, por rank.

## Acompanhamento
<!-- Uma linha por dia/sessão: data — o que avançou — impedimentos — decisões -->
| Data | Andamento | Impedimentos | Decisões (→ ADR?) |
|---|---|---|---|
| 2026-11-11 | Sprint planejada: 11 itens, 32 pts, capacidade 53,3 | — | duas sprints até o prazo de 11/12; o TK-018 sai da 14 (depende do Render); nenhuma ausência no período |

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
