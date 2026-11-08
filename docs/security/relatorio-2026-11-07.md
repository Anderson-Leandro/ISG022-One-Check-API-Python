# Relatório de Segurança — OneCheck API

- **Data:** 2026-11-07
- **Modo:** diff contra `ed36a41` (antes do DEBT-014) · **Commit:** `4440ea0` + mudanças não commitadas das branches `chore/sprint-executor` e `test/DEBT-014-testes-refresh-admin`
- **Escopo:**
  - status HTTP dos erros de negócio: `app/schemas.py` e os 7 routers (DEBT-014, ADR-0003);
  - testes alterados;
  - collection do Insomnia;
  - ferramentas do processo: `.claude/hooks/guarda.py`, `.claude/settings.json`, `scripts/dod_check.py`, skill `sprint-executor`;
  - 35 arquivos ao todo (`changed-files.txt`).
- **Stack:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL (Render), Docker
- **Ferramentas:** Claude (revisão manual guiada) + semgrep, bandit, gitleaks (diretório e histórico), trivy, osv-scanner, todos com status `ok`

## 1. Sumário executivo
A mudança principal (DEBT-014) **não altera quem pode fazer o quê**: só troca o status HTTP das respostas de erro. Ela melhora a detecção de abuso, porque login falho, MFA errado e acesso negado deixam de aparecer como 200 nos logs (A09:2021).

As ferramentas novas do processo não abrem superfície de ataque. Não há dependência vulnerável nem segredo novo. Os três achados são informativos.

| Crítica | Alta | Média | Baixa | Info |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 3 |

Scanners: 15 resultados brutos → 1 confirmado (SEC-035, como info), 14 descartados, 0 suprimidos.

| Resultados descartados | Qtd. | Motivo |
|---|---|---|
| bandit B404/B603/B607 em `guarda.py` e `dod_check.py` | 9 | `subprocess` com lista fixa de argumentos e sem shell, em ferramenta local que não recebe entrada externa |
| gitleaks `.env:11` | 1 | o `.env` local não é versionado (nenhum arquivo sensível no índice) e está fora do diff |
| gitleaks em `tests/integration/test_seguranca_seed_credenciais.py:137,165` | 2 | valores fictícios de teste, em arquivo fora do diff (já existia) |
| trivy DS026 (`HEALTHCHECK` no `Dockerfile`) | 1 | fora do diff e já conhecido |
| semgrep e bandit SHA-1, mesmo local | 1 | duplicado do SEC-035 |

## 2. Pilares de segurança
| Pilar | Achados | Avaliação |
|---|---|---|
| Confidencialidade | SEC-036, SEC-037 | ok: nenhuma informação nova exposta; as mensagens genéricas de autenticação foram mantidas |
| Integridade | SEC-035 | ok |
| Disponibilidade | — | ok: o limite de tentativas não mudou |
| Autenticidade | — | ok: login, MFA e refresh continuam com as mesmas checagens; só o status mudou |
| Não-repúdio / Auditoria | — | melhorou: 401, 403 e 429 ficam visíveis nos logs de acesso |

## 3. Princípios de design
| Princípio | Achados | Avaliação |
|---|---|---|
| Menor privilégio | — | sem mudança |
| Secure by default | — | `fail()` sem status responde 400, nunca 2xx |
| Fail secure | SEC-037 | `fail()` recusa status < 400 (`ValueError`); o teste de contrato na suíte barra regressões |
| Mediação completa | — | sem mudança nas checagens de acesso |
| Defesa em profundidade | SEC-036 | o hook se soma ao `.gitignore` e às regras, mas não é controle de segurança |
| Superfície de ataque mínima | SEC-035 | ok |

## 4. STRIDE
| Categoria | Ameaças identificadas | Mitigadas | Achados |
|---|---|---|---|
| S — Spoofing | enumeração de contas pela resposta do login | sim: mesma resposta (status e corpo) para e-mail existente e inexistente, com teste em `test_status_http_erros.py` | — |
| T — Tampering | — | — | — |
| R — Repudiation | abuso invisível no monitoramento (200 em falha) | sim, pelo ADR-0003 | — |
| I — Information disclosure | existência de recurso por 403 × 404 | parcial: já existia pela mensagem; IDs são UUID | SEC-037 |
| D — Denial of service | — | — | — |
| E — Elevation of privilege | — | — | — |

Detalhes no [modelo de ameaças](threat-model.md).

## 5. Achados

### SEC-035 — SHA-1 usado só para IDs estáveis no gerador da collection · Info
| | |
|---|---|
| **Pilar** | Integridade |
| **Princípio violado** | — |
| **STRIDE** | — |
| **CWE / OWASP** | CWE-328 / A02:2021 |
| **Local** | `docs/insomnia/gerar_collection.py:148` |
| **Fonte** | semgrep, bandit |

**Evidência**
```python
return prefixo + "_" + hashlib.sha1("|".join(partes).encode()).hexdigest()[:24]
```
**Cenário de exploração:** nenhum. O hash só gera IDs de requisição estáveis.
**Impacto:** nenhum. É ruído nos scanners.
**Correção recomendada:** `hashlib.sha1(..., usedforsecurity=False)`.

### SEC-036 — O hook `guarda.py` é contornável por ofuscação · Info
| | |
|---|---|
| **Pilar** | Confidencialidade |
| **Princípio violado** | Defesa em profundidade (limitação conhecida) |
| **STRIDE** | I |
| **CWE / OWASP** | CWE-184 / A05:2021 |
| **Local** | `.claude/hooks/guarda.py:21` |
| **Fonte** | Claude |

**Evidência**
```python
ENV = re.compile(r"(?<![\w.-])\.env(?![\w.-])")
```
**Cenário de exploração:** um comando que monta o nome do arquivo em partes não cita `.env` literalmente e passa pelo hook.
**Impacto:** o hook evita erros do agente, mas não segura quem quer contornar. A proteção real continua sendo o `.gitignore` e as regras.
**Correção recomendada:** não tratar o hook como controle de segurança. Opcionalmente, negar `Read(.env)` em `permissions.deny`.

### SEC-037 — 403 e 404 distinguem contrato inexistente de contrato alheio · Info
| | |
|---|---|
| **Pilar** | Confidencialidade |
| **Princípio violado** | Fail secure |
| **STRIDE** | I |
| **CWE / OWASP** | CWE-204 / API1:2023 |
| **Local** | `app/routers/contratos.py:267`, `app/routers/contratos.py:269` |
| **Fonte** | Claude |

**Evidência**
```python
return fail("Contrato não encontrado", status_code=404)
...
return fail("Sem permissão para ver vistorias deste contrato", status_code=403)
```
**Cenário de exploração:** um locatário autenticado testa IDs de contrato e separa os que existem (403) dos que não existem (404).
**Impacto:** nenhum novo. As mensagens já diferiam antes, e os IDs são UUID v4. O ADR-0003 cita 404 para recurso "não visível", o que deixa a escolha ambígua.
**Correção recomendada:** decidir no ADR-0003 entre 403 e 404 para recurso de outro dono e aplicar a mesma regra em todas as rotas por ID.

## 6. Dependências e componentes
Nenhum pacote vulnerável (trivy + osv-scanner sobre `requirements.lock`).

## 7. Pontos positivos
- `fail()` recusa status abaixo de 400, e a suíte inteira barra `sucesso:false` com 2xx (`tests/conftest.py`). Uma regressão ao padrão antigo quebra o CI.
- A resposta do login é idêntica, em status e corpo, para e-mail existente e inexistente, e há teste para isso.
- Reautenticação recusada com sessão válida responde 403, e não 401, para o cliente não tratar o erro como sessão expirada.
- O hook do projeto bloqueia commit e push direto na `dev` e na `main` e o `git add` das notas locais.
- O `dod_check.py` só lê: chama `git` e `gh` com argumentos fixos, sem shell.

## 8. Limitações
- Modo diff: rotas que não mudaram não foram revisadas.
- Análise estática: não substitui teste dinâmico (DAST) nem pentest.

## 9. Plano de ação sugerido
1. **Imediato (Crítica/Alta):** nada.
2. **Melhoria contínua:**
   - `usedforsecurity=False` no gerador (SEC-035);
   - a decisão 403 × 404 no ADR-0003 (SEC-037);
   - opcionalmente, `permissions.deny` para o `.env` (SEC-036).
