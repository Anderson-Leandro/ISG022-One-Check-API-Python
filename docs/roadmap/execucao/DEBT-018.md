# DEBT-018 — dod_check sem falhas indevidas: PR de release, intervalos de IDs e caminhos curtos

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 13 · **Issue:** #176 · **Branch:** `chore/DEBT-018-dod-check-falsos-negativos` · **PR:** #194

## Entrega
Ação da retrospectiva da Sprint 12. Mudanças em `scripts/dod_check.py`, com funções puras e testáveis:
- `conferir_pr`: um PR de release (base `main` e head `dev`) confere só se foi mesclado com o CI verde, e não conta como PR de implementação; o item continua precisando de pelo menos um PR de implementação. A base `dev`, o ID na branch e "muda app/ e traz testes" ficam só para os PRs de implementação.
- `cita_id`: o acompanhamento da sprint cita o ID direto (palavra inteira, então `DEBT-0181` não conta como `DEBT-018`) ou num intervalo do mesmo tipo e da mesma largura (`SPK-001 a SPK-004`, `até`, `–`, `-`).
- `faltando_no_relatorio`: o relatório de testes alterados aceita o caminho completo ou só o nome do arquivo, quando nenhum outro arquivo em `tests/` da `origin/dev` tem o mesmo nome (lido uma vez por execução); `test_x.py.bak` ou `old_test_x.py` não contam.
- `secao`: extrai uma seção pelo título no começo da linha (aceita complemento como `## Segurança (diff dev)`), usada em todas as seções obrigatórias e no Acompanhamento.
- **Fora dos critérios, mesmo tema (nota de escopo):** `auditoria_rodou` reprova "não foi rodada", "não rodou", "não executada", "ainda não" e "pendente", salvo quando a frase fala de um item do backlog ("SEC-019 continua pendente", "os itens pendentes"). Antes, qualquer "pendente" na seção Segurança, como "item X continua pendente no backlog", reprovava o item (aconteceu no SEC-035 e no TK-019).

| Critério de aceite | Prova |
|---|---|
| PR com base main em links.prs não passa pelas checagens de implementação | `TestPrDeRelease` (release com branch `dev` e app/ sem tests/ passa; release aberta ou com CI falho reprova; PR de implementação continua conferido). O #172 real passa: "release na main mesclada com o CI verde" |
| Intervalo de IDs conta como citação de cada ID | `TestIntervaloDeIds` (os IDs do intervalo, as outras grafias, fora do intervalo, outro tipo ou outra largura não contam) |
| Nome do arquivo sem o caminho, se único | `TestRelatorioDeTestesAlterados` (nome único basta; nome repetido em outra pasta exige o caminho; nome parecido não conta) |
| Testes cobrindo os três casos | as três classes acima, em `tests/unit/test_dod_check.py` |

## Testes
- **Novos:** 38 testes em `tests/unit/test_dod_check.py` (as três classes acima e `TestSecaoSeguranca`), incluindo os cenários negados: release aberta ou com CI falho, feature mesclada direto na main, ID fora do intervalo ou com larguras diferentes, nome de arquivo repetido, parecido ou com sufixo, auditoria não rodada ou pendente.
- **Suíte completa:** 1172 passaram, 3 pulados, cobertura 96%. Rodada numa cópia sem o arquivo de segredos local.
- **Itens já fechados:** o `dod_check` de todos os itens com registro em `docs/roadmap/execucao/` continua verde.

## Segurança
- `/security-audit diff dev` em 2026-11-08: os 7 scanners com status `ok`. **Nenhum achado novo.** Os avisos do bandit sobre `subprocess` em `scripts/dod_check.py` já existiam (argumentos fixos, sem shell); os do gitleaks são o arquivo local fora do git e os valores fictícios do teste de credenciais do seed.
- Script de processo, fora da API: nenhuma superfície da API muda.
- `/code-review` (medium), com 10 apontamentos:
  - **Corrigidos:**
    - a release exige head `dev` (uma feature mesclada direto na `main` continua conferida como implementação);
    - o item precisa de pelo menos um PR de implementação, além da release;
    - a regra da auditoria pendente, por frase, e as outras grafias de "não rodada";
    - o título de seção com complemento;
    - a largura dos dois limites do intervalo;
    - o nome do arquivo com sufixo;
    - a lista de testes lida uma vez, da `origin/dev`;
    - todas as seções obrigatórias lidas por `secao`.
  - **Sem mudança:** intervalos abreviados ("SPK-001 a 004", "SPK-001 e SPK-004"), que ficam fora do critério; o acompanhamento usa o ID completo.

## Checklist antes da revisão
- [-] Campos que o perfil que ganha acesso passa a ver: não se aplica, nenhuma rota da API muda.
- [-] Status finais: não se aplica, nenhuma regra de status da API muda (o estado do PR, MERGED ou não, está coberto nos testes da release).
- [-] Autorização antes de ler o corpo: não se aplica, script local sem autorização.
- [-] Login, refresh e tokens: não se aplica, nada de sessão muda.
- [-] Perfis proibidos barrados antes da busca por ID: não se aplica, nenhuma rota muda.

## Testes existentes alterados
Nenhum. `tests/unit/test_dod_check.py` só ganhou testes novos.

## Documentação
- Nada no README ou ADR: o comportamento do `dod_check` está nas docstrings das funções novas.
