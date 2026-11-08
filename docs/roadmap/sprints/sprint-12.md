# Sprint 12

- **Período:** 2026-11-04 → 2026-11-17
- **Sprint Goal:** Release v0.1.0, produção segura e escopo da F4 fechado
- **Capacidade:** 40 pts (era 32, pelo prazo final de 11/12; ampliada em 2026-11-07 para incluir os itens da avaliação dos testes) · **Comprometido:** 52 pts (DEBT-014 em 2026-11-07; os seis itens dos spikes em 2026-11-08; TK-002 e TK-003 foram para a Sprint 13 em 2026-11-08)
- **Time:** sem ausências; sem feriado em dia útil (15/11 é domingo)

> **Sprint Goal** é o "porquê" da sprint: se algum item não couber, o goal ajuda a decidir o que
> cortar sem perder o valor da entrega.

## Itens comprometidos
| ID | Título | Est. | Seg. | Status final |
|---|---|---|---|---|
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
| DEBT-015 | Remover o perfil visualizador e recusar perfis desconhecidos | 2 | medium | in_sprint |
| SEC-036 | Respeitar o MFA opcional ligado pelo próprio usuário | 1 | medium | in_sprint |
| US-018 | Locatário vê os agendamentos do próprio contrato | 1 | low | in_sprint |
| US-019 | Locatário comenta no próprio problema enquanto não estiver resolvido | 2 | medium | in_sprint |
| US-020 | Nova vistoria depois de uma rejeição, e fim do status pendente_revisao | 2 | low | in_sprint |
| DEBT-016 | Declarar no OpenAPI os tipos de agendamento (inicial e encerramento) | 1 | low | in_sprint |

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
| 2026-11-08 | SEC-032 concluído (#125): 17 testes de negação de acesso aos checklists por quem não é dono; as três mutações and→or que a suíte antiga deixava passar agora quebram o CI (889 testes, cobertura 96%). Restam 33 pts | — | só testes: o controle de acesso já estava correto |
| 2026-11-08 | SEC-033 concluído (#127): 15 testes das travas depois do envio para aceite (fotos, envio para aceite, cancelar e agendar em contrato não ativo); as cinco travas, antes nunca executadas, agora quebram o CI se forem desligadas (904 testes, cobertura 96%). Restam 31 pts | — | só testes: as travas já estavam corretas |
| 2026-11-08 | DEBT-011 concluído (#129): 103 testes de negação por perfil; as 97 combinações perfil proibido × rota restrita têm teste, e a lista das 32 rotas é conferida com a API (1007 testes, cobertura 96%). Restam 28 pts | o critério de GET /logs depende da decisão do SEC-018 (Sprint 13) | teste fixa o comportamento atual do gestor nos logs; muda junto com o SEC-018 |
| 2026-11-08 | DEBT-012 concluído (#131): 54 testes de negação existentes passam a conferir o banco inteiro (45) e a mensagem exata (25); um 403 devolvido depois de gravar agora quebra o CI. `sprint-executor` ganha a flag `--continuo` (#132). Restam 25 pts | — | alteração de testes existentes aprovada pelo usuário (só acréscimos e um teste renomeado); o modo contínuo passa a vir do argumento, não do CLAUDE.md |
| 2026-11-08 | DEBT-009 concluído (#134): ADR-0004 a ADR-0007 (sessão JWT, MFA TOTP, uploads em disco, Render com 1 worker). Restam 22 pts | R-017 (alto, a confirmar): disco efêmero no plano gratuito do Render pode apagar as fotos; depende do painel do Render | achados fora da sprint: SEC-035 (QR do MFA por serviço externo recebe o segredo) e TK-018 |
| 2026-11-08 | SEC-034 concluído (#138): token de primeiro acesso emitido antes da troca de senha recusado no setup do MFA, e teto de chaves do limitador testado com relógio controlado (1013 testes, cobertura 96%). Restam 20 pts | DEBT-006 (licença) aguarda a escolha do usuário | — |
| 2026-11-08 | US-015 concluído (#141): exclusão lógica de checklist, contrato e problema por admin e gestor, só antes de virarem evidência (ADR-0008; 1047 testes, cobertura 96%). Restam 15 pts | SPK-003 aguarda decisão do PO | decisões do PO: exclusão lógica, admin e gestor, regra estrita; a revisão de código acrescentou a exigência de problema aberto. BUG-001 fora da sprint |
| 2026-11-08 | US-017 concluído (#143): histórico do imóvel com contratos, vistorias e problemas em ordem cronológica, no recorte de cada perfil (1061 testes, cobertura 96%). Restam 12 pts | TK-002 e TK-003 (Render), DEBT-006 (licença) e SPK-001 a SPK-004 (decisões do PO) aguardam o usuário; DEBT-007 (release) entra por último | fim dos itens de código executáveis da sprint |
| 2026-11-08 | Decisões dos spikes SPK-001 a SPK-004 (ADR-0009 a ADR-0012): visualizador removido, fotos públicas como risco aceito (R-007), MFA opcional respeitado e quatro regras de negócio. Seis itens novos entram na sprint (DEBT-015, SEC-036, US-018, US-019, US-020, DEBT-016; +9 pts, comprometido passa de 45 para 54) | — | decisão do usuário: os ambientes de produção e de desenvolvimento serão zerados; o TK-002 passa a ser recriar o ambiente sem credenciais de demonstração, e o R-017 deixa de ter fotos reais em risco até o uso de verdade |
| 2026-11-08 | SPK-001, SPK-002, SPK-003 e SPK-004 concluídos (#145). Restam 13 pts: TK-002, TK-003, DEBT-006 e DEBT-007, mais os seis itens novos | TK-002 e TK-003 dependem do painel do Render; DEBT-006 da escolha da licença | — |
| 2026-11-08 | DEBT-015 concluído (#153): perfil visualizador removido; perfil fora da lista recusado em toda rota, no login e no refresh (1037 testes, cobertura 96%) | — | testes do visualizador removidos ou ajustados, com aprovação do usuário; DEBT-017 fora da sprint |
| 2026-11-08 | SEC-036 concluído (#155): o MFA ligado pelo locatário passa a valer no login, com configuração do autenticador quando ainda não houver (1047 testes, cobertura 96%) | — | dois testes unitários invertidos, com aprovação do usuário |
| 2026-11-08 | US-018 concluído (#157): o locatário lê os agendamentos do próprio contrato, sem a observação interna, e o dashboard conta os dele (1054 testes, cobertura 96%) | — | dois testes existentes ajustados, com aprovação do usuário |
| 2026-11-08 | US-019 concluído (#159): o locatário dono comenta no próprio problema enquanto não estiver resolvido ou fechado (1064 testes, cobertura 96%) | — | dois testes existentes ajustados, com aprovação do usuário |
| 2026-11-08 | US-020 concluído (#161): nova vistoria inicial depois de uma rejeição, com a rejeitada intacta; pendente_revisao fora do domínio (1072 testes, cobertura 96%) | — | trava por lista de status que bloqueiam (achado da revisão) |
| 2026-11-08 | DEBT-016 concluído (#163): tipos de agendamento declarados como enum no OpenAPI (1076 testes, cobertura 96%) | — | fim dos itens de código da sprint; restam TK-002, TK-003, DEBT-006 e DEBT-007 |
| 2026-11-08 | TK-002 e TK-003 (2 pts) passam para a Sprint 13, a pedido do usuário; comprometido de 54 para 52 pts. Restam 3 pts: DEBT-006 e DEBT-007 | o ambiente de produção será tratado depois pelo usuário | a parte "produção segura" do goal da Sprint 12 fica para a Sprint 13 |
| 2026-11-08 | DEBT-006 concluído (#168): licença MIT, titular Equipe One Check. Resta 1 item: DEBT-007 (release v0.1.0) | — | licença escolhida pelo usuário |

## Sprint Review
_Feita em 2026-11-08._

- **Incremento demonstrável:**
  - **Contrato da API:** erros de negócio com o status HTTP adequado (ADR-0003).
  - **Perfis e MFA:** o perfil visualizador foi removido, e um perfil fora da lista é recusado em toda rota, no login e no refresh (ADR-0009); o MFA ligado pelo locatário passa a valer no login (ADR-0011).
  - **Funcionalidades novas:**
    - exclusão lógica de contrato, checklist e problema (ADR-0008);
    - histórico do imóvel;
    - agendamentos visíveis para o locatário;
    - comentário do locatário no próprio problema;
    - nova vistoria depois de uma rejeição;
    - tipos de agendamento no OpenAPI.
  - **Suíte de testes:** de 836 para 1076 testes, com cobertura de 96%; cenários negados em todas as rotas restritas, travas de estado e negações que conferem o banco (SPK-005, SEC-032 a SEC-034, DEBT-011, DEBT-012).
  - **Processo:**
    - ruleset na `main` e na `dev` (TK-017);
    - `sprint-executor`, com `dod_check` e hook de barreiras;
    - ADR-0004 a ADR-0012;
    - licença MIT;
    - `CHANGELOG.md` da 0.1.0.
- **Goal atingido?** **Sim**, na avaliação do PO (2026-11-08):
  - o escopo da F4 fechou, com os quatro spikes decididos e os seis itens nascidos deles entregues;
  - a release v0.1.0 está pronta (CHANGELOG no #170, PR `dev → main` e tag em seguida);
  - a produção segura (TK-002, TK-003) foi para a Sprint 13 por decisão do usuário, porque o ambiente vai ser recriado.
- **Evidências:**
  - 23 itens com `scripts/dod_check.py` verde (o DEBT-007 fecha com a tag);
  - 50 PRs mesclados na `dev` desde 2026-11-04, com o CI verde;
  - registros em `docs/roadmap/execucao/` (o do SPK-005 foi escrito de forma retroativa nesta review);
  - collection do Insomnia rodada contra a API local (163 de 163, sem a pasta 00a).
- **Checagem de segurança:**
  - `/security-audit diff` da sprint inteira, contra `089d100` (2026-11-02): 111 arquivos e os 7 scanners sem falha. **Nenhum segredo nem achado novo.** Os resultados que aparecem já tinham sido avaliados: o arquivo de segredos local fora do índice, valores fictícios em testes, SHA-1 só para IDs da collection, o filtro de data dos logs (SEC-020), `subprocess` com argumentos fixos nos scripts de processo e o `HEALTHCHECK` do Dockerfile.
  - **Riscos e itens novos, fora da sprint:**
    - SEC-035 (o QR do MFA por serviço externo);
    - TK-018 / R-017 (disco efêmero no Render, alto e a confirmar);
    - BUG-001 (excluir cômodo referenciado);
    - DEBT-017 (regras de acesso negando por padrão).
  - R-007 foi aceito (ADR-0010).
- **Feedback do cliente/PO:** satisfeito com o incremento; seguir para a release e para a Sprint 13 sem ajustes.

## Retrospectiva
| Funcionou bem | Melhorar | Ação (vira item no backlog) |
|---|---|---|

## Métricas
- Velocity: — pts (comprometido 32)
- Itens que voltaram ao backlog:
