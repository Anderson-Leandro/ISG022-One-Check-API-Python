# Sprint 13

- **Período:** 2026-11-18 → 2026-12-01
- **Sprint Goal:** Produção recriada com segurança, falhas abertas corrigidas e qualidade verificada no CI
- **Capacidade:** 50 pts, combinada com o usuário (a média do script era 39,3 por causa da Sprint 8, retroativa e com 2 pts; o ritmo das Sprints 11 e 12 foi de 64 e 52) · **Comprometido:** 47 pts (94%)

> **Sprint Goal** é o "porquê" da sprint: se algum item não couber, o goal ajuda a decidir o que
> cortar sem perder o valor da entrega.

## Itens comprometidos
| ID | Título | Est. | Seg. | Status final |
|---|---|---|---|---|
| TK-002 | Recriar o ambiente de produção sem credenciais de demonstração | 1 | high | in_sprint |
| TK-003 | Configurar CORS_ORIGINS e conferir SEED_SECRET no Render | 1 | medium | in_sprint |
| SEC-035 | QR do setup de MFA gerado por serviço externo recebe o segredo TOTP | 2 | medium | in_sprint |
| SEC-017 | IP de origem lido do primeiro item do X-Forwarded-For, controlado pelo cliente | 3 | low | in_sprint |
| SEC-018 | Gestor lê toda a trilha de auditoria, com IP e e-mails de todas as contas | 2 | low | in_sprint |
| TK-005 | Backup e restauração do Postgres | 3 | high | in_sprint |
| SEC-027 | Encerrar a sessão quando um refresh token já trocado for reutilizado | 3 | medium | in_sprint |
| BUG-001 | Excluir cômodo referenciado por checklist ou problema responde 500 | 1 | low | in_sprint |
| DEBT-017 | Regras de acesso negam por padrão os perfis que não citam | 2 | low | in_sprint |
| TK-019 | Checklist de autorização e exposição no registro de execução, antes da revisão de código | 1 | low | in_sprint |
| TK-020 | Versionar o executor da collection do Insomnia com um comando que roda tudo do zero | 2 | low | in_sprint |
| DEBT-018 | dod_check sem falhas indevidas: PR de release, intervalos de IDs e caminhos curtos | 1 | low | in_sprint |
| DEBT-005 | Dependabot para pip e GitHub Actions | 1 | medium | in_sprint |
| DEBT-004 | Lint e formatação (ruff) no CI | 2 | none | in_sprint |
| DEBT-003 | Consolidar as rotas duplicadas de MFA e remover GET /auth/mfa/setup | 3 | low | in_sprint |
| DEBT-001 | Modelos Pydantic nos corpos das rotas de problemas | 3 | low | in_sprint |
| SEC-019 | Login falho grava o texto digitado no campo e-mail | 1 | low | in_sprint |
| SEC-020 | Filtros de data inválidos em /logs são ignorados em silêncio | 1 | low | in_sprint |
| SEC-031 | Cifrar o CPF em repouso | 5 | low | in_sprint |
| DEBT-002 | response_model e nomes consistentes no OpenAPI | 5 | low | in_sprint |
| DEBT-010 | Cobrir os ramos não testados de agendamentos, geocoding e database | 3 | low | in_sprint |
| DEBT-008 | Conventional Commits em pelo menos 70% dos commits | 1 | none | in_sprint |


## Ordem sugerida
1. **Itens que dependem do usuário no Render:** TK-002 (recriar o ambiente), TK-003 (`CORS_ORIGINS` e `SEED_SECRET`), TK-005 (backup e restauração) e o teste do SEC-017 no proxy do Render. Combinar uma janela no painel no início da sprint.
2. **Processo, para valer no resto da sprint:** TK-019 (checklist antes da revisão), DEBT-018 (`dod_check`) e TK-020 (executor da collection).
3. **Segurança:** SEC-035, SEC-027, SEC-018, BUG-001, DEBT-017, SEC-019, SEC-020 e SEC-031.
4. **Qualidade e contrato da API:** DEBT-005, DEBT-004, DEBT-003, DEBT-001, DEBT-002, DEBT-010 e DEBT-008.

**Avisos do planejamento:**
- O DEBT-005 (Dependabot) tem impacto de segurança médio e nenhum critério de cenário negado. É configuração de ferramenta, não rota da API.
- O SEC-018 vai alterar `test_gestor_le_os_logs` (DEBT-011), que fixava o comportamento atual até essa decisão: relatório de teste alterado e aprovação.
- O comprometido (47) passa da média do script (39,3), dentro da capacidade combinada (50).

## Acompanhamento
<!-- Uma linha por dia/sessão: data — o que avançou — impedimentos — decisões -->
| Data | Andamento | Impedimentos | Decisões (→ ADR?) |
|---|---|---|---|
| 2026-11-08 | Sprint planejada: 22 itens, 47 pts, capacidade 50. Entram, além dos 38 pts já alocados, as ações da retro 12 (TK-019, TK-020, DEBT-018), SEC-035, BUG-001 e DEBT-017 | TK-002, TK-003, TK-005 e o teste do SEC-017 dependem do painel do Render | estimativas de SEC-035 (2), BUG-001 (1) e DEBT-017 (2) confirmadas pelo usuário; TK-018 (3) fica fora da sprint |
| 2026-11-08 | SEC-035 concluído (#180): QR do setup de MFA gerado pela própria API, sem enviar o segredo TOTP a terceiros (1081 testes, cobertura 96%) | — | dependência nova segno==1.6.6 (puro Python, BSD-3) |
| 2026-11-08 | SEC-018 concluído (#182): GET /logs só do admin; o gestor recebe 403 (1082 testes, cobertura 96%) | — | decisão do PO: só o admin (descartadas a visão reduzida e o risco aceito); testes ajustados com aprovação |
| 2026-11-08 | SEC-027 concluído (#184): reuso de refresh trocado encerra todas as sessões; rotação atômica (1090 testes, cobertura 96%) | — | R-011 mitigado; contrapartida (refresh repetido pelo próprio cliente) no ADR-0004 |
| 2026-11-08 | BUG-001 concluído (#186): cômodo em uso responde 409 em vez de 500, inclusive com referência em registro excluído (1096 testes, cobertura 96%) | — | rede de segurança do IntegrityError (achado da revisão) |

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
- Velocity: — pts (comprometido 47)
- Itens que voltaram ao backlog:
