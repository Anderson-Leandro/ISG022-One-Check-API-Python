# DEBT-004 — Lint e formatação (ruff) no CI

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 13 · **Issue:** #80 · **Branch:** `chore/DEBT-004-ruff-lint` · **PR:** #<n>

## Entrega
- `ruff.toml`: linha de 120, Python 3.12. Regras: o conjunto padrão (E4, E7, E9, F), `I` (ordem dos imports), `UP` (sintaxe do 3.12) e `B` (bugbear). Ficam de fora, com o motivo no arquivo: `B008` (o `Depends(...)` do FastAPI), `E712` (`coluna == True` monta o SQL no SQLAlchemy), `E741` e `UP046` (só estilo).
- CI (`.github/workflows/tests.yml`, job `test`, que é um check obrigatório): `ruff check --output-format=github .` e `ruff format --check .` antes do pytest. Um aviso de lint ou um arquivo fora do formato reprova o PR. O `ruff==0.17.4` fica fixado em `requirements-test.txt`, e o `pip-audit` do CI o confere.
- Base atual sem avisos:
  - `ruff format` nos arquivos `.py` (só formatação; com as correções abaixo, 94 arquivos `.py` mudam);
  - `ruff check --fix`: ordem dos imports, imports sem uso, `timezone.utc` → `UTC`;
  - à mão: `raise ... from None` em 3 conversões de erro (`agendamentos`, `contratos`, `uploads`), a mensagem continua igual; uma variável sem uso em `imoveis.py` (o `pop` continua); uma f-string em `gerar_collection.py` (a collection gerada não muda).

| Critério de aceite | Prova |
|---|---|
| `ruff check` e `ruff format --check` rodam no workflow e falham o PR com erro | os dois passos no job `test` (check obrigatório do ruleset); `ruff` sai com código 1 em qualquer aviso |
| A base atual passa sem avisos | `ruff check .` → "All checks passed!"; `ruff format --check .` → "103 files already formatted" (os `.md` ficam fora: os trechos de código neles são citações) |

## Testes
- Nenhum teste novo: o critério é conferido pelo próprio CI, que roda o ruff.
- **Suíte completa:** 1180 passaram, 3 pulados, cobertura 96%. Rodada numa cópia sem o arquivo de segredos local.
- **Collection do Insomnia:** 166/166, contra a API local da cópia (porta livre). O `gerar_collection.py` gera o mesmo JSON.
- Os 34 testes do hook `guarda.py` (também reformatado) passam.

## Segurança
- `/security-audit diff dev` em 2026-11-08: os 7 scanners com status `ok`. **Nenhum achado novo.** Como a formatação toca 94 arquivos, o modo diff varre quase o projeto todo e mostra resultados que já existiam na `dev`, conferidos um a um (`grep` na `origin/dev`): o segredo TOTP público de demonstração no seed e no `populate_and_test.py`, o `urlopen` do `populate_and_test.py`, a mensagem de log do `JWT_SECRET` em `app/config.py`, o SHA-1 do `gerar_collection.py`, o B110 do dashboard (SEC-020), o `subprocess` dos scripts, a chave JWT fictícia do teste de assinatura, os valores fictícios do teste do seed e o DS026 do Dockerfile.
- `raise ... from None` (datas) e `from e` (upload) não mudam a resposta ao cliente: a mensagem é a mesma. No upload, o erro original do Pillow continua como causa no log interno.
- `/code-review` (medium), com 7 apontamentos, sem defeito de correção (os imports removidos não eram usados nem trocados por nenhum teste):
  - **Corrigidos:**
    - o ruff sai do grupo semanal do Dependabot e ganha PR próprio, porque uma versão minor do 0.x pode mudar o formatador e travar as outras atualizações;
    - os testes rodam mesmo com o lint vermelho (`if: !cancelled()`), para o PR mostrar os dois resultados;
    - o README diz de onde vem o `ruff`;
    - o upload guarda a causa (`from e`).
  - **Sem mudança:**
    - o `_parse_datetime` repetido em `agendamentos.py` e `contratos.py`, que já existia e fica fora do critério;
    - o `E712` ignorado no projeto todo: os filtros `== True` do SQLAlchemy estão em `app/` e em `tests/`, e trocá-los por `.is_(True)` mudaria consultas fora deste item;
    - o PR no registro, que o fechamento preenche.

## Checklist antes da revisão
- [-] Campos que o perfil que ganha acesso passa a ver: não se aplica, nenhuma resposta muda.
- [-] Status finais: não se aplica, nenhuma regra de status muda.
- [-] Autorização antes de ler o corpo: não se aplica, nenhuma rota muda de comportamento.
- [-] Login, refresh e tokens: não se aplica, nada de sessão muda.
- [-] Perfis proibidos barrados antes da busca por ID: não se aplica, nenhuma rota muda.

## Testes existentes alterados
58 arquivos de teste mudam, todos por ferramenta ou por limpeza mecânica. **Nenhuma asserção, fixture ou chamada à API muda, e nenhum teste é removido.** A prova: comparando a árvore sintática (`ast`) de antes e de depois, 37 arquivos são idênticos (só espaços, quebras de linha e vírgulas), e os outros 21 diferem só nas linhas da tabela abaixo.

| Arquivo :: teste | Antes | Depois | Por que precisa mudar | O comportamento atual quebra? |
|---|---|---|---|---|
| 37 arquivos em `tests/` (todos os de `tests/unit/` e `tests/integration/` tocados pelo `ruff format`) | código fora do formato do ruff | mesmo código formatado (árvore sintática idêntica) | critério "a base atual passa sem avisos" e `ruff format --check` no CI | Não |
| `tests/conftest.py`, `tests/integration/test_dashboard.py`, `test_problemas.py`, `test_seguranca_limite_corpo.py`, `test_seguranca_mfa_bypass.py`, `test_seguranca_mfa_desativacao.py`, `test_seguranca_rate_limit.py`, `test_seguranca_senha_regras.py`, `test_usuarios.py`, `tests/unit/test_geocoding.py` | imports fora de ordem | imports em ordem (regra `I001`); no `conftest.py`, o `# noqa: E402` na linha do `engine`, que o ruff separou | regra `I` do lint | Não |
| `tests/integration/test_auth_routes.py` (módulo e `test_mfa_verify_token_tipo_errado`) | importava `MFA_TEST_SECRET` sem usar; linha `access_token = create_temp_token.__module__` sem uso | import e linha removidos | `F401` e `F841` (código morto; o teste segue montando o access token real logo abaixo) | Não |
| `tests/integration/test_checklists.py`, `test_seguranca_acesso_nega_por_padrao.py`, `test_seguranca_auditoria.py`, `test_seguranca_gestao_usuarios.py`, `tests/unit/test_serializers.py`, `tests/integration/test_contratos.py` (dentro de 2 testes) | importavam `pytest`, `Checklist`, `Usuario`, `totp_now`, `Contrato` e `Imovel` sem usar | imports removidos | `F401` | Não |
| `tests/unit/test_auth.py`, `tests/unit/test_seguranca_dependencias_jwt.py`, `tests/integration/test_seguranca_lgpd_mfa.py`, `test_seguranca_revogacao_sessoes.py` | `datetime.now(timezone.utc)` | `datetime.now(UTC)` (`from datetime import UTC`) | `UP017`; `datetime.UTC` é o mesmo objeto que `timezone.utc` | Não |

Nenhuma alteração enfraquece um teste.

Aprovado por: Anderson em 2026-11-08

## Documentação
- `ruff.toml` (novo), com o motivo de cada regra ignorada.
- `README.md`: os comandos do lint.
- `.github/dependabot.yml`: o ruff fora do grupo semanal do pip.
