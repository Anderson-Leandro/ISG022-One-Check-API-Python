# DEBT-007 — CHANGELOG e release v0.1.0

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 12 · **Issue:** #83 · **Branch:** `chore/DEBT-007-changelog-v0.1.0` · **PR:** #170

## Entrega
- `CHANGELOG.md` na raiz, no formato Keep a Changelog. A versão **0.1.0** reúne a migração da API em PHP, as correções da auditoria de segurança e as Sprints 11 e 12, em Adicionado, Alterado, Removido e Segurança. Foi montado a partir dos commits (`git log`) e dos relatórios `docs/security/correcao-*.md`, com links para os ADRs.
- **Tag `v0.1.0`:** ainda não criada. Ela é publicada no remoto e depende da decisão do usuário sobre onde marcar (ver abaixo).

| Critério de aceite | Prova |
|---|---|
| Existe `CHANGELOG.md` com as entregas até agora (commits e relatórios de correção) | `CHANGELOG.md`, versão 0.1.0 |
| Existe a tag `v0.1.0` apontando para um commit com o CI verde | pendente: decisão do usuário sobre o commit (dev ou main) |

## Testes
Item só de documentação: nenhum código nem teste muda. O CI do PR roda a suíte normalmente (1076 testes na `dev`).

## Segurança
- `/security-audit diff dev` em 2026-11-08: os scanners aplicáveis com status `ok` (bandit pulado: nenhum `.py` no diff). **Nenhum achado novo.**
- O CHANGELOG cita as correções de segurança só pelo nome e pelo item, sem passo a passo de exploração, porque o repositório é público. Os itens abertos (SEC-035, R-017) ficam fora dele.

## Testes existentes alterados
Nenhum.

## Documentação
- `CHANGELOG.md` (novo).
