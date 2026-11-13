# Sprint 14

- **Período:** 2026-11-12 → 2026-11-13. O calendário planejado ia até 25/11; ajustado no `close` para as datas da execução, por decisão do PO.
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
| DEBT-019 | Lock que o Dependabot regenera sozinho, com as transitivas | 3 | low | movido para a Sprint 15 (2026-11-13) |
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
| 2026-11-11 | Decisões do PO antes da execução, registradas nos itens | — | SEC-025: trigger no banco; SEC-028: autoatendimento com reautenticação; SEC-029: conferir no login; SEC-030: HIBP com k-anonymity, aceita se o serviço cair (→ ADRs do SEC-025 e do SEC-028) |
| 2026-11-11 | TK-021: merge pela interface do GitHub já com o título do PR (#n); configuração versionada e conferida pelo dod_check (PR #236) | — | — |
| 2026-11-11 | TK-022: script versionado que roda a suíte numa cópia sem o arquivo de segredos, do zero ou reaproveitando o venv (PR #238) | — | — |
| 2026-11-11 | DEBT-020: todo erro da API no envelope {sucesso, erro, erros}; testes que liam detail atualizados com aprovação (PR #240) | — | — |
| 2026-11-11 | SEC-025: log de auditoria append-only por trigger no banco; R-005 mitigado (PR #242) | — | — |
| 2026-11-11 | SEC-028: exportação e anonimização dos próprios dados (LGPD art. 18); R-016 mitigado; DEBT-022 criado (PR #244) | — | — |
| 2026-11-11 | BUG-002: pedido recusado não deixa foto órfã no disco; fotos antigas do checklist só saem depois do commit (PR #246) | — | — |
| 2026-11-11 | DEBT-013: mensagem própria para o token de verificação no primeiro acesso do MFA (PR #248) | — | — |
| 2026-11-11 | DEBT-021: imagem base do Dockerfile fixada por digest e coberta pelo Dependabot (PR #250) | — | — |
| 2026-11-12 | SEC-030: senha nova que aparece em vazamentos conhecidos recebe 422 (Have I Been Pwned, k-anonymity, fail open) (PR #252) | — | — |
| 2026-11-12 | SEC-029: senha antiga fora da política força a troca no login; prazo da consulta de senhas vazadas em 3 s (PR #254) | — | — |
| 2026-11-13 | DEBT-019 (3 pts) sai da sprint e fica previsto para a Sprint 15 | o Dependabot só lê a configuração da main: os critérios 1 e 2 só se provam com um PR real depois da release (TK-015) | decisão do PO: fazer e provar junto da release |

## Sprint Review
Feita em 2026-11-13.

- **Incremento demonstrável:**
  - **Dados do titular (LGPD):** exportação (`GET /usuarios/me/dados`) e anonimização da própria conta (`POST /usuarios/me/anonimizar`), com ADR-0017 (SEC-028). O login, a criação e a desativação de usuário deixam de gravar o e-mail no log.
  - **Trilha íntegra:** um trigger no banco recusa UPDATE e DELETE em `log_operacao`, salvo a retenção (SEC-025, ADR-0016). Testado também no PostgreSQL.
  - **Erros num formato único:** todo erro, inclusive 401, 403, 422 de schema e 500, vem em `{sucesso, erro, erros}`, e o OpenAPI só declara esse formato (DEBT-020).
  - **Senhas:** a senha antiga fraca obriga a troca no login (SEC-029). Senhas novas vazadas são recusadas pelo Have I Been Pwned, com k-anonymity, prazo de 3 s e fail open (SEC-030).
  - **Correções:** foto órfã no disco, inclusive na foto do checklist (BUG-002), e mensagem própria para o token de verificação no MFA (DEBT-013).
  - **Processo:**
    - merges pela interface do GitHub no padrão (TK-021): dos 22 merges da sprint, só o anterior a ele saiu fora do padrão;
    - suíte numa cópia do projeto por script (TK-022);
    - imagem do Docker fixada por digest (DEBT-021).
- **Goal atingido? Sim.** Os três resultados do goal estão entregues, cada um com os testes do critério e do cenário negado.
- **Evidências:**
  - `python3 scripts/dod_check.py` verde nos 10 itens `done`;
  - 55 commits e 22 PRs mesclados desde o planejamento (#236 a #256);
  - suíte de 1398 para 1521 testes, cobertura de branches em 97%;
  - collection do Insomnia com 169/169;
  - ADRs 0016 e 0017.
- **Checagem de segurança:**
  - **Scanners:** rodados no diff completo da sprint (`9f1c7e0..dev`), os 7 com status `ok`. **Nenhum achado novo** e nenhuma dependência vulnerável.
  - **Apontamentos conferidos no código:** o SQL dos triggers é montado só com nomes fixos; o `try/except` da liberação é proposital; o SHA-1 e a URL da consulta de senhas vazadas são o formato do serviço, com o prefixo conferido antes; as constantes de mensagem e a chave do teste de assinatura não são segredos.
  - **Riscos:** R-005 (não-repúdio) e R-016 (LGPD) mitigados.
- **Fora da sprint:** o DEBT-019 (3 pts) foi movido para a Sprint 15 por decisão do PO, porque só se prova depois da release (o Dependabot lê a `main`). O DEBT-022 (direitos do titular de uma conta desativada) foi criado na revisão do SEC-028.
- **Feedback do cliente/PO:** o incremento está de acordo. O goal foi atingido, e nada muda de prioridade.

## Retrospectiva (2026-11-13)
Proposta a partir dos dados da sprint e confirmada pelo usuário, que escolheu as ações. As ações da retro da Sprint 13 foram feitas:
- **TK-021:** desde ele, todos os merges da sprint saíram no padrão.
- **TK-022:** a suíte rodou na cópia por script em todos os itens.
- **Regra de infraestrutura:** foi usada no SEC-030 (consultas reais ao serviço) e no DEBT-019 (a limitação do Dependabot apareceu antes de qualquer código).

| Funcionou bem | Melhorar | Ação (vira item no backlog) |
|---|---|---|
| Decisões de PO tomadas antes da execução (SEC-025, SEC-028, SEC-029, SEC-030): o modo contínuo parou só nos testes alterados | A regra da auditoria do `dod_check` reprovou o BUG-002 por causa de "pendente" dentro de `foto_pendente`, e o registro precisou ser reescrito | **DEBT-023**: `dod_check` sem falso positivo em nomes de código, com testes |
| A revisão de código pegou defeitos sérios antes do merge: o event loop travado (SEC-030), a marca antes do MFA e o seed fora da restrição (SEC-029), a liberação que vazava (SEC-025), a terceira rota com foto órfã (BUG-002) | O script de fechamento foi apagado do scratchpad várias vezes e recriado à mão | **TK-023**: script versionado que fecha um item da sprint |
| O Postgres temporário pegou o erro do `%` no trigger, que o SQLite não mostra, antes do CI | Um teste do BUG-002 simulava a falha antes da gravação e passava sem testar a limpeza; só a cobertura revelou | Sem item: regra nova no passo 3 do `sprint-executor`. Provar, pela cobertura ou por uma asserção, que o caminho testado rodou |
| Protocolo de testes alterados: cinco aprovações explícitas, nenhum teste enfraquecido | O prazo do SEC-030 foi fixado sem medir a primeira chamada de um processo novo e subiu de 2 s para 3 s depois de falhar | Sem item: regra nova no passo 3 do `sprint-executor`. Medir várias chamadas reais, inclusive a fria, antes de fixar um prazo |

## Métricas
Sprint fechada em 2026-11-13.

- **Velocity:** 29 pts de 32 comprometidos (91%), em 10 itens. As três últimas sprints fecharam com 52, 44 e 29 pts, o que dá uma capacidade sugerida de 41,7 pts.
- **Itens que voltaram ao backlog:** nenhum no `close`. O DEBT-019 (3 pts) já tinha saído em 2026-11-13, por decisão do PO, e ficou previsto para a Sprint 15: ele só se prova depois da release.
- **Escopo:** nenhum item entrou durante a sprint. Ficaram fora dela os itens descobertos (DEBT-022) e as ações da retro (DEBT-023 e TK-023).
- **Burndown:** 32 → 3 (12/11 e 13/11). Os 3 pts restantes são do DEBT-019.
- **Qualidade:** suíte de 1398 para 1521 testes, cobertura de branches em 97%; 22 PRs mesclados, todos com o CI verde; 5 alterações de testes existentes, todas aprovadas.
