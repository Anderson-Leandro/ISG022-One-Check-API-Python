# Sprint 13

- **Período:** 2026-11-08 → 2026-11-11. O calendário planejado era 18/11 a 01/12, e foi ajustado no `close` para as datas da execução, por decisão do PO.
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
| 2026-11-08 | DEBT-017 concluído (#188): regras de acesso negam por padrão perfis fora de ROLES (1117 testes, cobertura 96%) | — | segunda camada além do get_current_user |
| 2026-11-08 | TK-019 concluído (#190): checklist de autorização e exposição no registro, preenchida antes da revisão de código e conferida pelo dod_check | — | ação da retro 12; registros antigos sem a seção não são cobrados |
| 2026-11-08 | TK-020 concluído (#192): executor da collection versionado e comando que roda tudo do zero (166/166) | — | ação da retro 12; a collection foi ajustada ao SEC-027 |
| 2026-11-08 | DEBT-018 concluído (PR #194): dod_check aceita release, intervalos de IDs e nome curto de teste; 38 testes novos |
| 2026-11-08 | DEBT-005 concluído (PR #197): Dependabot para pip e GitHub Actions contra a dev; o CI barra o PR sem o lock regenerado; DEBT-019 criado fora da sprint |
| 2026-11-08 | DEBT-004 concluído (PR #199): ruff no CI e base sem avisos; 58 arquivos de teste reformatados com aprovação |
| 2026-11-08 | DEBT-003 concluído (PR #201): rotas canônicas de MFA, aliases obsoletos até 2027-01-31 e GET /auth/mfa/setup removido |
| 2026-11-08 | DEBT-001 concluído (PR #203): corpos das rotas de problemas no OpenAPI; corpo que não é objeto dá 422 |
| 2026-11-08 | SEC-019 concluído (PR #205): login falho sem o texto digitado no log (id da conta ou HMAC); registros antigos limpos |
| 2026-11-08 | SEC-020 concluído (PR #207): filtro de data inválido em /logs responde 422; sai o B110 |
| 2026-11-08 | SEC-031 concluído (PR #209): CPF cifrado em repouso com a chave fora do banco e rotação por script; R-014 mitigado |
| 2026-11-08 | DEBT-002 concluído (PR #212): envelope e modelos de resposta no OpenAPI das rotas principais; DEBT-020 criado para unificar os erros |
| 2026-11-09 | DEBT-010 concluído (PR #215): cobertura de ramos total de 86,6% para 92,3%; BUG-002 criado fora da sprint |
| 2026-11-09 | DEBT-008 concluído (PR #217): merges no padrão Conventional Commits; diagnose.py mostra 90% sem os merges |
| 2026-11-10 | TK-002: produção recriada e carregada pelo seed atual; sem o alerta de credenciais públicas depois do reinício (PR #219) |
| 2026-11-10 | TK-003: CORS_ORIGINS restrito às origens autorizadas (origem de fora bloqueada) e SEED_SECRET vazio no Render (PR #221) |
| 2026-11-10 | SEC-017: IP forjado no X-Forwarded-For confirmado no Render e corrigido (IP pelo item do proxy, PROXY_SALTOS=3 conferido em produção; PRs #223 e #224) |
| 2026-11-10 | Decisão do PO: risco R-015 (sem backup do banco) aceito até o primeiro dado real em produção; TK-005 sai da sprint no close e volta ao backlog |

## Sprint Review
Feita em 2026-11-10.

- **Incremento demonstrável:**
  - **Produção:**
    - **Recriação:** banco recriado e carregado pelo seed, com senhas aleatórias (TK-002).
    - **Configuração:** `CORS_ORIGINS` restrito e `SEED_SECRET` vazio (TK-003).
    - **IP do cliente:** o IP forjado no `X-Forwarded-For` deixou de ser aceito, e o real foi conferido no Render, atrás de 3 proxies (SEC-017, ADR-0015).
  - **Falhas corrigidas:**
    - **MFA:** QR do MFA gerado pela própria API (SEC-035).
    - **Logs:** `GET /logs` só do admin (SEC-018). O login falho grava o HMAC do e-mail, e não o e-mail digitado (SEC-019). O filtro de data inválido responde `422` (SEC-020).
    - **CPF:** cifrado em repouso (SEC-031, ADR-0014).
    - **Outras correções:** SEC-027, BUG-001 e DEBT-017.
  - **Qualidade e CI:**
    - **Lint:** ruff no CI (DEBT-004).
    - **Respostas:** documentadas, com teste de contrato (DEBT-002).
    - **MFA:** uma rota canônica por operação (DEBT-003, ADR-0013).
    - **Processo:** merges no padrão Conventional Commits (DEBT-008) e checklist antes da revisão (TK-019). O `dod_check` deixou de falhar sem motivo (DEBT-018).
    - **Outros itens:** DEBT-001, DEBT-005, DEBT-010 e TK-020.
- **Goal atingido? Sim, com uma ressalva.** Produção recriada e conferida, as falhas abertas do escopo corrigidas e a qualidade verificada no CI. A ressalva é o backup do banco (TK-005): ficou adiado porque o PO aceitou o risco R-015 até o primeiro dado real em produção. Volta ao backlog no `close`.
- **Evidências:**
  - 44 PRs mesclados na `dev` (#180 a #226) e 115 commits desde o planejamento (`e91f9d3`);
  - `python3 scripts/dod_check.py` verde nos 21 itens `done`;
  - suíte com 1398 testes (1081 no começo da sprint) e cobertura de branches em 97%;
  - registros em `docs/roadmap/execucao/` e ADRs 0013, 0014 e 0015.
- **Checagem de segurança:**
  - **Scanners:** rodados no diff completo da sprint (`e91f9d3..dev`), os 7 com status `ok`. **Nenhum achado novo** e nenhuma dependência vulnerável.
  - **Apontamentos conferidos no código:**
    - os segredos do gitleaks são o arquivo local fora do git e os valores fictícios dos testes;
    - o SQL do `ALTER TABLE` é montado com uma constante;
    - `gAAAAA` é o prefixo do token Fernet;
    - o `MFA_SECRET_DEV` é o segredo público de desenvolvimento, usado para detectar as contas antigas;
    - o `logger` do `app/config.py` não registra o segredo.
  - **Riscos:** R-006 e R-008 mitigados, R-015 aceito.
  - **Próxima auditoria:** a completa, com relatório, fica para o TK-006 (Sprint 14), antes da release candidata.
- **Feedback do cliente/PO:** o incremento está de acordo. Nada muda de prioridade por enquanto. O PO concorda com o goal atingido, com a ressalva do risco aceito.

## Retrospectiva (2026-11-11)
Proposta a partir dos dados da sprint e confirmada pelo usuário, que escolheu as ações. As três ações da retro da Sprint 12 foram feitas nesta sprint: TK-019, TK-020 e DEBT-018.

| Funcionou bem | Melhorar | Ação (vira item no backlog) |
|---|---|---|
| `dod_check` e registro por item: os 21 itens foram conferidos pelo script, e a checklist antes da revisão (TK-019) foi usada em todos | Desde o DEBT-008, os merges feitos pela interface do GitHub (#223, #224 e #226) saíram com "Merge pull request #… from …", porque o padrão do repositório continua o antigo. O fechamento do SEC-017 não achou os commits | **TK-021**: merge pela interface já com o título do PR (#n), com a configuração conferida |
| A conferência em produção junto com o usuário: o SEC-017 foi confirmado com um único teste, e a contagem de proxies saiu de dados reais, registrada no ADR-0015 | O `PROXY_SALTOS=1` foi suposto, sem ver a cadeia real (Cloudflare, proxy do Render e rede interna). Foram 3 rodadas de deploy até chegar ao valor certo | Sem item: regra nova no passo 3 do `sprint-executor`. Item que depende da infraestrutura começa por um teste em produção, antes de fixar um valor |
| A revisão de código pegou defeitos reais antes do merge, como o `X-Forwarded-Proto` que deixaria os redirects em `http`, e o protocolo de testes alterados teve 4 aprovações explícitas, sem nenhum teste mais fraco | A limpeza do scratchpad apagou várias vezes o venv e os comandos de fechamento, e o ambiente de testes foi recriado à mão a cada vez | **TK-022**: script versionado que roda a suíte numa cópia sem o arquivo de segredos, do zero |
| Decisões de PO registradas no mesmo dia: R-015 aceito, com o gatilho de revisão, e as rotas de MFA no ADR-0013 | As datas da sprint no `sprints.yaml` (18/11 a 01/12) não batem com a execução (08/11 a 10/11), e o burndown saiu vazio | Sem item: as datas são corrigidas no `close` |

## Métricas
Sprint fechada em 2026-11-11.

- **Velocity:** 44 pts de 47 comprometidos (94%), em 21 itens. As três últimas sprints fecharam com 64, 52 e 44 pts, o que dá uma capacidade sugerida de 53,3 pts.
- **Itens que voltaram ao backlog:** TK-005 (3 pts, backup e restauração do Postgres). Volta como `ready` e sem sprint, porque o PO aceitou o risco R-015 até o primeiro dado real em produção.
- **Escopo:** nenhum item entrou durante a sprint. Os itens novos descobertos (DEBT-019, DEBT-020 e BUG-002) e as ações da retro (TK-021 e TK-022) ficaram fora dela.
- **Burndown:** 47 → 22 (08/11) → 8 (09/11) → 3 (10/11 e 11/11).
- **Qualidade:** suíte de 1081 para 1398 testes, cobertura de branches em 97%; 44 PRs mesclados, todos com o CI verde.
