# <ID> — <título do item>

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** <N> · **Issue:** #<n> · **Branch:** `<tipo/ID-descricao>` · **PR:** #<n>

## Entrega
<!-- O que mudou, em 2 a 5 linhas, e como cada critério de aceite foi atendido (critério → prova). -->

## Testes
<!-- Testes novos (arquivo e o que cobrem, incluindo o cenário negado), resultado da suíte completa
     (passaram, pulados, cobertura) e onde rodou (cópia sem .env). -->

## Segurança
<!-- Resultado da /security-audit diff dev: achados por severidade e o que foi feito com cada um.
     Se não se aplica (só documentação), dizer por quê. -->

## Checklist antes da revisão
<!-- Preencha ANTES do /code-review. Marque cada linha com [x] (conferido, diga como) ou [-] (não se aplica,
     diga por quê). O dod_check falha se sobrar alguma linha com [ ]. -->
- [ ] Campos que o perfil que ganha acesso passa a ver: a resposta não leva nada além do necessário (notas internas, IP, e-mails, segredos).
- [ ] Status finais: toda regra que depende do status trata todos os estados finais (ex.: resolvido e fechado; aceito e rejeitado).
- [ ] Autorização antes de ler o corpo: quem não pode agir é recusado antes de o corpo ou o upload serem lidos.
- [ ] Login, refresh e tokens: o caso novo também vale no login, no refresh e nos tokens já emitidos.
- [ ] Perfis proibidos barrados antes da busca por ID: um 404 contra 403 não revela quais registros existem.

## Testes existentes alterados
<!-- "Nenhum." quando só houve testes novos ou asserções acrescentadas.
     Caso contrário, uma linha por teste alterado ou removido, ANTES do commit, e parar para aprovação:

| Arquivo :: teste | Antes | Depois | Por que precisa mudar | O comportamento atual quebra? |
|---|---|---|---|---|

Aprovado por: <nome> em AAAA-MM-DD -->

## Documentação
<!-- README, ADR, collection do Insomnia, MUDANCAS_DE_CONTRATO.md (local), riscos. "Nada a atualizar" com o motivo. -->
