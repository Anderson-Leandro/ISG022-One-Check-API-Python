# DEBT-006 — Definir a licença do repositório público

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 12 · **Issue:** #82 · **Branch:** `chore/DEBT-006-licenca-mit` · **PR:** #<n>

## Entrega
Decisão do usuário em 2026-11-08: licença **MIT**, com o titular **Equipe One Check**.
- `LICENSE` na raiz, com o texto oficial da MIT e `Copyright (c) 2026 Equipe One Check`.
- `README.md`: seção "Licença" no fim, com o que a MIT permite e exige e o link para o `LICENSE`.

**Dependências:** as dependências diretas (`requirements.txt`) usam licenças permissivas (MIT, BSD, Apache-2.0, a do Pillow), além do `psycopg2` (LGPL, usado como biblioteca, sem modificação). Nenhuma delas impede a MIT.

| Critério de aceite | Prova |
|---|---|
| Existe `LICENSE` na raiz e o README cita a licença | `LICENSE` (MIT, Equipe One Check) e a seção "Licença" do `README.md` |

## Testes
Item só de documentação: nenhum código nem teste muda. O CI do PR roda a suíte normalmente.

## Segurança
- `/security-audit diff dev` em 2026-11-08: os scanners aplicáveis com status `ok` (bandit pulado: nenhum `.py` no diff). **Nenhum achado novo.**
- A licença não muda nenhum controle de segurança; o aviso de "sem garantia" da MIT passa a valer para o código publicado.

## Testes existentes alterados
Nenhum.

## Documentação
- `LICENSE` (novo) e a seção "Licença" do `README.md`.
