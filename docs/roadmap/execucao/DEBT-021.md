# DEBT-021 — Imagem base do Dockerfile fixada por digest e coberta pelo Dependabot

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 14 · **Issue:** #233 · **Branch:** `chore/DEBT-021-imagem-por-digest` · **PR:** #<n>

## Entrega
Separado do DEBT-019 no refinamento de 2026-11-11. É a pendência do SEC-008: a imagem base seguia numa tag móvel, e o Dependabot não cobria o Docker.

- **`Dockerfile`:** `FROM python:3.12-slim@sha256:5e2bdb1b…`. A tag diz a versão, e o digest garante a mesma imagem em todo build. O digest foi lido em 2026-11-11 com `docker buildx imagetools inspect python:3.12-slim`.
- **`.github/dependabot.yml`:** o ecossistema `docker` entra com base `dev`, agenda semanal, cooldown de 7 dias e o prefixo `chore(deps)`, como os outros. O Dependabot troca o digest, e a tag numa versão nova, no mesmo PR.

| Critério de aceite | Prova |
|---|---|
| O Dockerfile fixa a imagem base por digest (tag e `@sha256`), e um teste confere que não há `FROM` sem digest | `TestContainer::test_imagem_base_fixada_por_digest` (`tests/unit/test_seguranca_infra.py`) |
| O `dependabot.yml` cobre o ecossistema docker, com base `dev` e o mesmo cooldown | `test_versao_2_com_pip_github_actions_e_docker`; os casos `[docker]` de `test_prs_contra_a_dev_na_raiz_com_agenda` e `test_cooldown_contra_versao_recem_publicada`; `test_docker_com_o_mesmo_prefixo_de_commit` |
| O docker compose local continua subindo com a imagem fixada | O compose constrói a API pelo Dockerfile (`build: .`). `docker build` com a imagem fixada passou, com Python 3.12.16 e FastAPI 0.162 dentro dela. A imagem de teste foi apagada. O compose do usuário não foi subido nem tocado: os containers dele continuam os mesmos |

## Testes
- **Novos:** o teste do digest no Dockerfile, o caso `docker` nos dois testes parametrizados e o teste do prefixo de commit. Antes da mudança, os 5 falhavam.
- **Suíte completa:** 1486 passaram, 6 pulados, cobertura de branches em 97%. Rodada por `scripts/testes_na_copia.sh`, sem o arquivo de segredos local.

## Segurança
- `/security-audit diff dev` em 2026-11-11: os 7 scanners com status `ok`. **Nenhum achado novo.** O DS026 do Dockerfile (sem `HEALTHCHECK`, que o compose já faz) e os demais já existiam.
- OWASP A06:2021 e CWE-1357: o build não muda de imagem sem um PR revisável, e uma imagem nova passa pelo cooldown e pelo CI.
- `/code-review`: dispensado, porque o item só muda configuração (Dockerfile e `dependabot.yml`), sem código da API.

## Checklist antes da revisão
- [-] Campos que o perfil que ganha acesso passa a ver: não se aplica, nenhuma rota muda.
- [-] Status finais: não se aplica.
- [-] Autorização antes de ler o corpo: não se aplica.
- [-] Login, refresh e tokens: não se aplica.
- [-] Perfis proibidos barrados antes da busca por ID: não se aplica.

## Testes existentes alterados
| Arquivo :: teste | Antes | Depois | Por que precisa mudar | O comportamento atual quebra? |
|---|---|---|---|---|
| `tests/unit/test_dependabot.py` :: `test_versao_2_com_pip_e_github_actions` → `test_versao_2_com_pip_github_actions_e_docker` | os ecossistemas são exatamente `{"pip", "github-actions"}` | exatamente `{"pip", "github-actions", "docker"}` | o critério 2 inclui o ecossistema docker. Com a igualdade exata, o teste antigo recusaria qualquer ecossistema novo | Não. A asserção continua exata, com um ecossistema a mais |
| `tests/unit/test_dependabot.py` :: `test_prs_contra_a_dev_na_raiz_com_agenda` e `test_cooldown_contra_versao_recem_publicada` | parametrizados com `pip` e `github-actions` | também com `docker` | as mesmas regras (base `dev`, raiz, agenda e cooldown de 7 dias) passam a valer para o docker | Não. São casos a mais, e os dois antigos continuam |

Nenhuma alteração enfraquece um teste: as asserções antigas continuam, e os testes passam a cobrir também o docker.

Aprovado por: Anderson em 2026-11-11

## Documentação
- `Dockerfile` e `.github/dependabot.yml`: comentários sobre a tag com o digest e sobre o ecossistema docker.
