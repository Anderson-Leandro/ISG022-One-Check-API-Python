# DEBT-005 — Dependabot para pip e GitHub Actions

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 13 · **Issue:** #81 · **Branch:** `chore/DEBT-005-dependabot` · **PR:** #<n>

## Entrega
- `.github/dependabot.yml` com os ecossistemas `pip` e `github-actions`. Os PRs saem toda segunda-feira, contra a `dev`, no máximo 5 abertos por ecossistema, com prefixo `chore(deps)`. Cada ecossistema tem um grupo (pip: minor e patch num PR só; actions: todas juntas) e um `cooldown` de 7 dias contra uma versão recém-publicada.
- **Lock com hash:** o Dependabot pip muda o `requirements.txt`, mas não regenera o `requirements.lock`. O CI já barra o PR até o lock ser regenerado (`test_lockfile_coerente_com_requirements` e `test_lockfile_tem_hash_em_todos_os_pacotes`, nos checks obrigatórios `test` e `dependencias`). O passo manual (rodar o comando do cabeçalho do lock na branch do PR) está no README e no comentário do arquivo.
- **Actions por SHA:** o Dependabot de `github-actions` troca o SHA fixado e o comentário de versão juntos. Um teste confere que toda action do workflow continua fixada por SHA de 40 caracteres, com o comentário `# vX`.
- O `dependabot.yml` só vale na branch padrão (`main`), então começa a funcionar na próxima release `dev → main`.

| Critério de aceite | Prova |
|---|---|
| Existe `.github/dependabot.yml` para pip e github-actions | `test_versao_2_com_pip_e_github_actions`, `test_prs_contra_a_dev_na_raiz_com_agenda` |
| PRs de atualização mantêm o lock com hashes e as actions fixadas por SHA | os testes do lock que já existiam barram o PR sem o lock regenerado; `test_ci_roda_nas_branches_do_dependabot_e_instala_pelo_lock_com_hash`, `test_pip_acha_o_requirements_que_o_lock_trava`, `test_actions_fixadas_por_sha_com_comentario_de_versao` |

## Testes
- **Novos:** 8 testes em `tests/unit/test_dependabot.py` (configuração, cooldown, CI nas branches do Dependabot, lock e actions por SHA).
- `requirements-test.txt` passa a fixar o `pyyaml==6.0.3` (a mesma versão do lock), que os testes de configuração leem e antes só chegava como dependência do `uvicorn[standard]`.
- **Suíte completa:** 1180 passaram, 3 pulados, cobertura 96%. Rodada numa cópia sem o arquivo de segredos local.

## Segurança
- `/security-audit diff dev` em 2026-11-08: os 7 scanners com status `ok`. O semgrep apontou a falta de `cooldown` no `dependabot.yml` (2 avisos), corrigido com 7 dias; na segunda rodada, **nenhum achado novo**. Os do gitleaks são o arquivo local fora do git e os valores fictícios do teste de credenciais do seed; o DS026 do Dockerfile já existia.
- OWASP A06:2021 (componentes desatualizados): as diretas e as actions passam a ter atualização automática, e o cooldown reduz o risco de uma versão maliciosa recém-publicada.
- As "security updates" do Dependabot (configuração do repositório, hoje desligada) abrem PRs contra a `main`, ignorando o `target-branch`. Ligar ou não é decisão do dono do repositório.
- `/code-review` (medium), com 8 apontamentos:
  - **Corrigidos:**
    - o comentário sobre as security updates;
    - o README sobre os PRs do `requirements-test.txt`, que não mexem no lock;
    - o nome do teste do CI, que prometia mais do que conferia;
    - o `pyyaml` fixado nos requisitos de teste;
    - o piso do cooldown no teste (7 dias, como a configuração).
  - **Viraram o DEBT-019, fora da sprint:** o lock num formato que o Dependabot regenera sozinho (sem o passo manual, que também faz o Dependabot parar de rebasear o PR), PRs para as transitivas, e o ecossistema `docker` com a imagem base por digest.

## Checklist antes da revisão
- [-] Campos que o perfil que ganha acesso passa a ver: não se aplica, nenhuma rota da API muda.
- [-] Status finais: não se aplica, nenhuma regra de status muda.
- [-] Autorização antes de ler o corpo: não se aplica, só configuração do repositório.
- [-] Login, refresh e tokens: não se aplica, nada de sessão muda.
- [-] Perfis proibidos barrados antes da busca por ID: não se aplica, nenhuma rota muda.

## Testes existentes alterados
Nenhum.

## Documentação
- `README.md`: o fluxo dos PRs do Dependabot e a regeneração do lock.
- `.github/dependabot.yml`: comentários com o porquê de cada escolha.
- Backlog: DEBT-019 (novo, fora da sprint).
