# Registro de Riscos — OneCheck API

> **Por que isso importa:** risco = probabilidade × impacto. Registrar força uma decisão consciente
> (mitigar, aceitar, transferir ou evitar) em vez de esquecer o problema.

Escala: probabilidade e impacto de 1 (baixo) a 3 (alto). Nível = P × I → 1–2 baixo · 3–4 médio · 6–9 alto.

- **R-001 a R-005** são os riscos R-01 a R-05 de [`docs/security/initial-risks.md`](../security/initial-risks.md), reavaliados depois das correções.
- **Os demais** vêm do [modelo de ameaças](../security/threat-model.md) e das auditorias de 2026-10-25 e 2026-11-02.
- **P e I** são os valores atuais, já considerando os controles existentes.

| ID | Risco (ameaça → ativo → consequência) | Ativo | STRIDE | P | I | Nível | Tratamento | Controle / item | Dono | Status | Risco residual |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R-001 | Usuário autenticado troca o ID na URL → contratos, imóveis e problemas de terceiros → vazamento (IDOR) | A-05, A-06, A-09 | I | 1 | 2 | 2 baixo | mitigar | `assert_acesso_*` (`app/deps.py`); SEC-004, SEC-023 | Anderson Mendes Leandro | mitigado | regra esquecida numa rota nova: coberto por testes negados |
| R-002 | Senha vazada de conta privilegiada sem MFA configurado → sessão admin | A-01 | S | 1 | 3 | 3 médio | mitigar | setup bloqueante no login, tokens de tipos separados; US-002, SEC-021 | Anderson Mendes Leandro | mitigado | dispositivo do usuário comprometido |
| R-003 | Edição de laudo depois do envio ou aceite → fraude no laudo | A-07 | T | 1 | 3 | 3 médio | mitigar | máquina de estados, separação de deveres; US-007, US-014, SEC-022 | Anderson Mendes Leandro | mitigado | bug na máquina de estados: coberto por testes de ciclo de vida |
| R-004 | Admin desativa a própria conta → gestão travada | A-01, A-13 | D | 1 | 2 | 2 baixo | mitigar | bloqueio de auto-desativação; US-003 | Anderson Mendes Leandro | mitigado | desativação cruzada entre admins |
| R-005 | Operador altera dados e nega a autoria → sem não-repúdio | A-10 | R | 2 | 2 | 4 médio | mitigar | IP e campos alterados (SEC-010); falta append-only (SEC-025) | Anderson Mendes Leandro | parcial | quem tem acesso direto ao banco altera o log |
| R-006 | Contas do seed antigo em produção com senha e TOTP públicos → tomada de conta | A-01 | S | 2 | 3 | 6 alto | mitigar | seed sem credenciais fixas (SEC-001); rotação pendente (TK-002) | Anderson Mendes Leandro | **aberto** | — |
| R-007 | URL de foto vazada ou compartilhada → foto do interior do imóvel acessível sem login | A-08 | I | 1 | 2 | 2 baixo | aceitar | nome aleatório de 128 bits; ADR-0010; SEC-026 junto com o armazenamento externo (TK-018) | Anderson Mendes Leandro | aceito | uma URL vazada abre a foto até a troca de armazenamento |
| R-008 | Cliente forja o `X-Forwarded-For` → escapa do limite por IP e grava IP falso na auditoria | A-10, A-13 | S/R | 2 | 2 | 4 médio | mitigar | limite por conta; SEC-017 (confirmar no Render) | Anderson Mendes Leandro | **aberto** | — |
| R-009 | Gestor consulta IP e acessos de todas as contas → exposição de dados pessoais | A-10 | I | 1 | 1 | 1 baixo | mitigar | SEC-018 ✓ (GET /logs só do admin, 2026-11-08); SEC-019 (e-mail digitado no login falho) | Anderson Mendes Leandro | aberto (parcial) | o admin continua vendo IP e e-mails digitados até o SEC-019 |
| R-010 | Visualizador lê toda a operação → acesso além da necessidade | A-05, A-06, A-07 | I | 2 | 2 | 4 médio | a decidir | SPK-001 | Anderson Mendes Leandro | aberto (decisão) | — |
| R-011 | Refresh token roubado e reutilizado após a rotação → sessão paralela até expirar | A-02 | S | 1 | 2 | 2 baixo | mitigar | rotação a cada uso; SEC-027 | Anderson Mendes Leandro | aberto | — |
| R-012 | Limite de tentativas em memória → com mais de um worker ou instância, o limite efetivo se multiplica | A-13, A-01 | D/S | 1 | 2 | 2 baixo | aceitar | 1 instância e 1 worker no Render (premissa) | Anderson Mendes Leandro | aceito | revisar se escalar |
| R-013 | Terceiro esgota as tentativas de uma conta → bloqueio temporário da vítima | A-13 | D | 2 | 1 | 2 baixo | aceitar | janela de 15 min; custo do controle do R-002 (T-16) | Anderson Mendes Leandro | aceito | — |
| R-014 | Acesso direto ao banco ou a um backup → CPFs em texto | A-03, A-12 | I | 1 | 2 | 2 baixo | mitigar | SEC-031 | Anderson Mendes Leandro | aberto | — |
| R-015 | Perda do banco sem backup testado → indisponibilidade e perda de laudos | A-12, A-07 | D | 1 | 3 | 3 médio | mitigar | TK-005 | Anderson Mendes Leandro | **aberto** | — |
| R-016 | Titular pede acesso ou eliminação dos dados e não há como atender → não conformidade com a LGPD | A-03 | — | 2 | 2 | 4 médio | mitigar | SEC-028 | Anderson Mendes Leandro | aberto | — |
| R-017 | Deploy ou reinício no Render com disco efêmero → fotos de vistoria e de problemas apagadas → laudos sem evidência | A-08, A-07 | D | 2 | 3 | 6 alto | mitigar | TK-018 (confirmar no painel do Render); ADR-0006, ADR-0010. Os ambientes atuais serão zerados (2026-11-08): sem fotos reais em risco até o uso de verdade | Anderson Mendes Leandro | **aberto** | — |

**Tratamentos:** mitigar (cria item SEC no backlog) · aceitar (justificar + quem aceitou + quando
revisar) · transferir (seguro, fornecedor) · evitar (remover a funcionalidade).

## Riscos aceitos
| ID | Justificativa | Aceito por | Data | Revisar em |
|---|---|---|---|---|
| R-012 | O deploy tem uma instância e um worker (plano gratuito do Render); um contador em Redis ou no banco não se paga nesse cenário | Anderson Mendes Leandro | 2026-11-02 | ao mudar de plano ou de número de workers |
| R-007 | O nome de 128 bits impede adivinhar a URL; a URL assinada vem junto com o armazenamento externo das fotos, que já a oferece, e fazê-la antes no disco local seria retrabalho (ADR-0010, SPK-002) | Anderson Mendes Leandro | 2026-11-08 | ao adotar um serviço externo de armazenamento das fotos (TK-018) |
| R-013 | É o custo do limite de tentativas, que protege o R-002; o bloqueio dura no máximo 15 minutos | Anderson Mendes Leandro | 2026-11-02 | 2027-05-01 |
