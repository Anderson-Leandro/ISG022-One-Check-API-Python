# DEBT-008 — Conventional Commits em pelo menos 70% dos commits

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 13 · **Issue:** #84 · **Branch:** `chore/DEBT-008-conventional-commits` · **PR:** #217

## Entrega
Diagnóstico: o `diagnose.py` mostrava **58%** sobre os últimos 300 commits. Os commits de autoria já estavam em 90% (165 de 183). O que puxava a medida para baixo eram os 103 commits de merge do GitHub, com o assunto padrão "Merge pull request #N from ...". O histórico publicado não é reescrito (regra do projeto).

Decisão do usuário (2026-11-09): as duas medidas.
- **Merges no padrão daqui em diante:** o `sprint-executor` (`.claude/skills/sprint-executor/SKILL.md`, passo 7) mescla com `gh pr merge <n> --merge --subject "<título do PR> (#<n>)"`. O título do PR já segue o Conventional Commits, então o commit de merge também segue. O `docs/roadmap/working-agreement.md` registra a regra.
- **Medida sem os merges:** o `diagnose.py` (skill global `_roadmap-shared`, fora do repositório) passa a usar `git log --no-merges`. O padrão vale para os commits de autoria, e o assunto do merge é gerado pela ferramenta. O relatório diz "(sem os merges)".

| Critério de aceite | Prova |
|---|---|
| Os próximos 10 commits seguem o padrão do working-agreement (`tipo(escopo): descrição (ID)`) | os 10 últimos commits de autoria da `dev`: 10 de 10 no padrão (conferido com a mesma expressão do `diagnose.py`). Os commits deste item e o merge deste PR, com `--subject`, também seguem |
| `diagnose.py` mostra ≥ 70% | `python3 ~/.claude/skills/_roadmap-shared/scripts/diagnose.py --root .` → "Conventional Commits: 90% dos últimos commits (sem os merges)" e `[x] Conventional Commits (≥ 70% dos commits)` |

## Testes
Item de processo: nenhum código da API nem teste muda. O CI do PR roda a suíte normalmente. A medida foi conferida com o próprio `diagnose.py` e com a expressão `CONVENTIONAL` dele.

## Segurança
- `/security-audit diff dev` em 2026-11-09: os scanners aplicáveis com status `ok` (bandit pulado, porque nenhum `.py` do repositório mudou). **Nenhum achado novo.**
- Item de processo, sem superfície da API.

## Checklist antes da revisão
- [-] Campos que o perfil que ganha acesso passa a ver: não se aplica, nenhuma rota muda.
- [-] Status finais: não se aplica.
- [-] Autorização antes de ler o corpo: não se aplica.
- [-] Login, refresh e tokens: não se aplica.
- [-] Perfis proibidos barrados antes da busca por ID: não se aplica.

## Testes existentes alterados
Nenhum.

## Documentação
- `docs/roadmap/working-agreement.md`: o assunto do merge e como a proporção é medida.
- `.claude/skills/sprint-executor/SKILL.md`: o `gh pr merge` com `--subject`.
- Fora do repositório: `~/.claude/skills/_roadmap-shared/scripts/diagnose.py` (`--no-merges`), que vale para todos os projetos que usam a skill.
