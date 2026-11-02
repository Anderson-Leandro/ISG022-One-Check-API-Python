# Relatório de Segurança — OneCheck API

- **Data:** 2026-11-02
- **Modo:** diff contra `f081c60` (base da [auditoria completa de 2026-10-25](relatorio-2026-10-25.md)) · **Commit:** `d0b5f35`
- **Escopo:** os 72 arquivos alterados desde a base. Isso inclui 25 módulos de `app/`, os scripts, `start.sh`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `render.yaml`, o workflow de CI, as dependências e os testes. Quando foi preciso entender um fluxo, li também os chamadores e o que eles chamam (por exemplo, o `ProxyHeadersMiddleware` do uvicorn).
- **Stack:** Python 3.12, FastAPI, SQLAlchemy 2, PyJWT, bcrypt, Pillow 13, PostgreSQL 16 / SQLite; deploy no Render e Docker Compose.
- **Ferramentas:** Claude (revisão manual guiada), semgrep, bandit, gitleaks (diretório e histórico), trivy (fs e config) e osv-scanner. Todos rodaram sem erro.
- **Numeração:** os IDs continuam a sequência da auditoria anterior (SEC-001 a SEC-016, todos corrigidos) para não haver dois "SEC-001".

## 1. Sumário executivo
As correções SEC-001 a SEC-016 e N1 a N8 não abriram falhas novas de severidade média ou maior. Os scanners não acharam nenhuma dependência vulnerável nem segredo versionado. Os dois achados baixos ficam nas bordas dos controles novos:
- **SEC-017:** o IP usado no limite de tentativas e na trilha de auditoria é o primeiro item do `X-Forwarded-For`, que o cliente pode forjar se o proxy do Render só acrescentar o IP real ao cabeçalho;
- **SEC-018:** o gestor lê a trilha de auditoria inteira, com IPs.

**Ação prioritária:** confirmar no Render como o proxy trata o `X-Forwarded-For` (teste de 1 minuto, descrito no SEC-017).

| Crítica | Alta | Média | Baixa | Info |
|---|---|---|---|---|
| 0 | 0 | 0 | 2 | 2 |

Scanners: 11 resultados brutos → 2 confirmados (os dois bandit B110, que formam o SEC-020); 9 descartados, sendo 8 falsos positivos e 1 item já mitigado no Compose (lista na seção 8); 0 suprimidos (não há `.security-audit-ignore.json`).

## 2. Pilares de segurança
| Pilar | Achados | Avaliação |
|---|---|---|
| Confidencialidade | SEC-018, SEC-019 | ok: há exposição a mais só para perfis internos |
| Integridade | SEC-020 | ok |
| Disponibilidade | SEC-017 | atenção: a camada por IP do limite de tentativas pode ser contornada |
| Autenticidade | — | ok: MFA, sessões, política de senha e tempo do login revisados sem achados |
| Não-repúdio / Auditoria | SEC-017 | atenção: o IP gravado só é confiável se o proxy sobrescrever o cabeçalho |

## 3. Princípios de design
| Princípio | Achados | Avaliação |
|---|---|---|
| Menor privilégio | SEC-018 | atenção |
| Secure by default | — | ok: compose sem CORS `*`, segredos obrigatórios, `/docs` desligado |
| Fail secure | SEC-017, SEC-020 | atenção |
| Mediação completa | — | ok: `assert_acesso_*` em todas as rotas por ID revisadas |
| Defesa em profundidade | SEC-017 | ok: o limite por conta continua valendo |
| Superfície de ataque mínima | — | ok: rota de setup de MFA por terceiros removida |

## 4. STRIDE
| Categoria | Ameaças identificadas | Mitigadas | Achados |
|---|---|---|---|
| S — Spoofing | 7 (T-01 a T-06, T-25) | 6 | SEC-017 |
| T — Tampering | 4 (T-08, 12, 13, 17) | 4 | — |
| R — Repudiation | 3 (T-18, 19, T-25) | 2 | SEC-017 |
| I — Information disclosure | 8 (T-09, 10, 11, 14, 21, 22, 24, 26) | 6 | SEC-018, 019 |
| D — Denial of service | 2 (T-15, 16) | 1 (T-16 aceita) | — |
| E — Elevation of privilege | 4 (T-07, 08, 20, 23) | 4 | — |

Detalhes no [modelo de ameaças](threat-model.md).

## 5. Achados

### SEC-017 — IP de origem lido do primeiro item do X-Forwarded-For · Baixa (a confirmar no Render)
| | |
|---|---|
| **Pilar** | Não-repúdio, Disponibilidade |
| **Princípio violado** | Fail secure, Defesa em profundidade |
| **STRIDE** | S, R |
| **CWE / OWASP** | CWE-348 / API4:2023 |
| **Local** | `render.yaml:18`, `app/rate_limit.py:74`, `app/auditoria.py:41` |
| **Fonte** | Claude |

**Evidência**
```yaml
# render.yaml:18
- key: FORWARDED_ALLOW_IPS
  value: "*"
```
```python
# uvicorn 0.34, middleware/proxy_headers.py:132 — com "*", vale o PRIMEIRO item do cabeçalho
if self.always_trust:
    return x_forwarded_for_hosts[0]
```
**Cenário de exploração:**
1. O proxy do Render recebe `X-Forwarded-For: 203.0.113.9` do cliente e, se apenas acrescentar o IP real, repassa `203.0.113.9, <IP real>`.
2. O uvicorn confia em qualquer origem (`*`) e escolhe o primeiro item, `203.0.113.9`.
3. O atacante troca o valor a cada tentativa: o limite por IP (20 falhas em 15 min) nunca dispara, e cada evento de `log_operacao` grava um IP inventado.

**Impacto:**
- Contorna a camada por IP do limite de tentativas. O limite por conta, de 5 falhas, continua valendo, então a força bruta em uma conta segue bloqueada; o que fica livre é a varredura de muitas contas (credential stuffing).
- O IP da trilha de auditoria (SEC-010) deixa de servir como prova.
- A severidade é Baixa porque o comportamento do proxy não foi verificado: o modelo de ameaças já o registrava como premissa. Se confirmado, vira Média.

**Correção recomendada:**
1. **Verificar** (sem risco, numa conta de teste): `curl -X POST https://<api>/api/v1/auth/login -H 'X-Forwarded-For: 203.0.113.9' -H 'Content-Type: application/json' -d '{"email":"teste@x.com","senha":"x"}'` e depois olhar o `ip` do evento `login_falho` em `GET /logs`. Se aparecer `203.0.113.9`, o cabeçalho é acrescentado.
2. **Corrigir**, se for o caso: não usar `FORWARDED_ALLOW_IPS=*`, e ler o **último** item do `X-Forwarded-For` (o que o proxy do Render adiciona) num middleware próprio. Outra opção é restringir `FORWARDED_ALLOW_IPS` à rede interna do proxy.

### SEC-018 — Gestor lê toda a trilha de auditoria, com IP e e-mails · Baixa
| | |
|---|---|
| **Pilar** | Confidencialidade (LGPD) |
| **Princípio violado** | Menor privilégio |
| **STRIDE** | I |
| **CWE / OWASP** | CWE-359 / API3:2023 |
| **Local** | `app/routers/dashboard.py:85`, `app/routers/dashboard.py:118` |
| **Fonte** | Claude |

**Evidência**
```python
_: Usuario = Depends(require_roles("admin", "gestor")),   # :85
...
"detalhes": l.detalhes,                                    # :116
"ip": l.ip,                                                # :118
```
**Cenário de exploração:** um gestor chama `GET /logs?acao=login` e recebe IP e horário de todos os logins, inclusive os dos admins, além dos e-mails digitados nos logins falhos.

**Impacto:**
- Desde o SEC-010, o log tem IP, que é dado pessoal, e o gestor vê isso de todas as contas.
- O [product backlog](../product-backlog.md) define a auditoria como atribuição do administrador, e o gestor "sem acesso irrestrito a administração total".
- A severidade é Baixa porque exige uma conta de gestor, que é um perfil interno.

**Correção recomendada:** deixar `GET /logs` só para o admin. Se o gestor precisar, devolver a ele a lista sem `ip` e `detalhes` e sem os eventos de contas admin e gestor.

### SEC-019 — Login falho grava o texto digitado no campo e-mail · Info
| | |
|---|---|
| **Pilar** | Confidencialidade (LGPD, minimização) |
| **Princípio violado** | Minimização |
| **STRIDE** | I |
| **CWE / OWASP** | CWE-532 / A09:2021 |
| **Local** | `app/routers/auth_router.py:58` |
| **Fonte** | Claude |

**Evidência**
```python
log_operacao(db, None, "login_falho", "usuario", None, f"email: {body.email}")
```
**Cenário:** o usuário digita a senha no campo de e-mail por engano. O texto fica em `log_operacao` e aparece em `GET /logs`.

**Impacto:** é um dado sem finalidade, guardado por até `LOG_RETENCAO_DIAS`. A retenção do SEC-014 limita o tempo.

**Correção recomendada:** gravar o `usuario_id` quando a conta existir; quando não existir, gravar só o domínio do e-mail, ou um hash dele.

### SEC-020 — Filtros de data inválidos em /logs são ignorados em silêncio · Info
| | |
|---|---|
| **Pilar** | Integridade |
| **Princípio violado** | Fail secure |
| **STRIDE** | I |
| **CWE / OWASP** | CWE-390 / — |
| **Local** | `app/routers/dashboard.py:98`, `app/routers/dashboard.py:104` |
| **Fonte** | bandit (B110), Claude |

**Evidência**
```python
try:
    de_dt = datetime.fromisoformat(de)
    q = q.filter(LogOperacao.created_at >= de_dt)
except Exception:
    pass
```
**Cenário:** `de=31/10/2026`, um formato inválido, devolve os logs de todo o período sem nenhum aviso.

**Impacto:** não dá acesso a mais nada, porque a rota já é só para admin e gestor. Mas pode levar a uma conclusão errada numa investigação.

**Correção recomendada:** declarar `de` e `ate` como `date`/`datetime` no FastAPI, para que um valor inválido dê `422`.

## 6. Dependências e componentes
| Pacote | Versão | CVE / ID | Severidade | Versão corrigida | Alcançável? |
|---|---|---|---|---|---|
| — | — | nenhum (trivy e osv-scanner sobre `requirements.lock`) | — | — | — |

O lockfile com hashes do SEC-006 está em vigor. Os pacotes que tinham CVEs na auditoria anterior (pillow, python-multipart, starlette, python-jose e cryptography) foram atualizados ou removidos.

## 7. Pontos positivos
- **Limite de corpo:** `LimiteCorpoMiddleware` conta os bytes também em corpo chunked e responde `413` antes da autenticação.
- **Uploads:** a assinatura do arquivo é conferida antes do Pillow, com `formats` restrito e limite de pixels. O nome é aleatório, e o arquivo servido passa pelo `caminho_seguro`, que impede path traversal.
- **Sessões:** `token_version` invalida as sessões em toda troca de credencial, inclusive quando a troca é feita por um admin.
- **Login:** bcrypt contra hash fictício, para não revelar a existência do e-mail pelo tempo, e mensagem única.
- **MFA:** o segredo fica pendente até ser confirmado, e o admin não conhece mais o segredo de ninguém.
- **Dados pessoais:** CPF mascarado e validado, e retenção de logs e tokens.
- **Container e CI:** container sem root, sem capabilities e com `no-new-privileges`; CI com `permissions: contents: read` e actions fixadas por SHA.
- **Testes:** 824 testes, 95% de cobertura, com testes de cenário negado para cada correção.

## 8. Limitações
- **Modo diff:** os arquivos que não mudaram desde `f081c60` (por exemplo, `app/routers/admin.py`, `app/routers/health.py` e `app/rate_limit.py`) foram analisados só quando apareceram no fluxo de um arquivo alterado.
- **Ambiente:** o comportamento do proxy do Render não foi testado, porque a regra deste trabalho é não acessar a produção. Isso afeta diretamente o SEC-017.
- **Resultados de scanner descartados (9):**
  - bandit B105 em `app/seed_service.py:29`: segredo TOTP de demonstração, que só vale em `APP_ENV=development`/`test` (SEC-001);
  - semgrep em `app/config.py:33`: o log mostra uma mensagem, e não o segredo;
  - semgrep em `tests/unit/test_auth.py:83`: chave de teste;
  - gitleaks (diretório e histórico) em `tests/integration/test_seguranca_seed_credenciais.py:137,165`, 4 resultados: segredos fictícios de teste;
  - gitleaks em `.env:11`: arquivo local, ignorado pelo `.gitignore`. Não está versionado nem no histórico (`git ls-files .env` vazio, e o gitleaks do histórico não acusa);
  - trivy DS026 (`HEALTHCHECK` no `Dockerfile`): o `docker-compose.yml` já define o healthcheck da API.
- **Tipo de análise:** é estática; não substitui teste dinâmico (DAST) nem pentest.

## 9. Plano de ação sugerido
1. **Imediato:** fazer o teste do SEC-017 no Render e, se o cabeçalho for acrescentado, corrigir a leitura do IP.
2. **Curto prazo:** restringir `GET /logs` ao admin (SEC-018) e ajustar o registro do login falho (SEC-019).
3. **Melhoria contínua:** `422` para filtros inválidos (SEC-020); rodar `/security-audit diff` a cada PR e `pip-audit` no CI (já existe).
