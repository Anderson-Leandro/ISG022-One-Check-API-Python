# DEBT-009 — ADRs retroativos das decisões principais

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 12 · **Issue:** #85 · **Branch:** `chore/DEBT-009-adrs-retroativos` · **PR:** #<n>

## Entrega
Quatro ADRs retroativos, no modelo do ADR-0001, escritos a partir do código atual (cada afirmação com `arquivo:linha` conferido) e do histórico do git:

| Decisão do critério de aceite | ADR |
|---|---|
| JWT com refresh rotativo e `token_version` | `docs/adr/0004-sessao-jwt-refresh-rotativo-token-version.md` |
| MFA TOTP obrigatório por perfil | `docs/adr/0005-mfa-totp-obrigatorio-por-perfil.md` |
| Uploads em disco local | `docs/adr/0006-uploads-em-disco-local.md` |
| Deploy no Render com 1 worker (limite de tentativas em memória) | `docs/adr/0007-deploy-render-um-worker.md` |

**Achados durante a escrita** (registrados fora da sprint, sem mudar código):
- **SEC-035** (médio): o `qr_url` do setup de MFA aponta para `api.qrserver.com` e leva o segredo TOTP e o e-mail na URL (`app/auth.py:178`).
- **TK-018** e risco **R-017** (alto, a confirmar): o `render.yaml` não declara disco persistente e, pela documentação do Render, o disco do plano gratuito é efêmero; as fotos em `UPLOAD_DIR` se perderiam a cada deploy ou reinício. A confirmação depende do acesso ao painel do Render.

## Testes
Item só de documentação: nenhum código nem teste muda. O CI do PR roda a suíte normalmente.

## Segurança
- `/security-audit diff dev` em 2026-11-08: os scanners aplicáveis com status `ok` (bandit pulado: nenhum `.py` no diff). **Nenhum achado novo** nos arquivos alterados. Os 4 resultados que aparecem (arquivo de segredos local fora do índice, valores fictícios em teste, `HEALTHCHECK` no Dockerfile) são anteriores, ficam fora do diff e já tinham sido avaliados no relatório de 2026-11-07.
- **Revisão manual** feita na escrita dos ADRs: dois achados novos, registrados como SEC-035 e TK-018/R-017 (acima). O ADR-0005 descreve o problema do QR sem passo a passo de exploração, por ser repositório público.

## Testes existentes alterados
Nenhum.

## Documentação
- ADR-0004 a ADR-0007 (novos).
- `docs/risks/risk-register.md`: risco R-017.
- Backlog: SEC-035 e TK-018, fora da sprint.
- Nada no README nem na collection do Insomnia: o comportamento da API não mudou.
