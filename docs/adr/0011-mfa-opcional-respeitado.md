# ADR-0011: O MFA ligado pelo próprio usuário passa a valer no login

- **Status:** aceito (complementa o ADR-0005)
- **Data:** 2026-11-08
- **Itens relacionados:** SPK-003, SEC-036, SEC-015, ADR-0005, ADR-0009, R-002

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
O ADR-0005 torna o MFA obrigatório para admin, gestor e vistoriador e opcional para os outros perfis. Na prática, o opcional não protegia nada: o locatário consegue ligar o MFA (`POST /usuarios/me/mfa/enable` grava o segredo e liga `mfa_enabled`), mas `needs_mfa` (`app/auth.py`) só olha os perfis obrigatórios, e o login nunca pede o código. A pessoa acha que está protegida e não está.

Com a remoção do visualizador (ADR-0009), o único perfil com MFA opcional é o locatário.

## Opções consideradas
1. **Respeitar o opcional:** quem ligou o MFA e configurou o autenticador recebe `mfa_required` no login, em qualquer perfil.
2. **Obrigatório para todos:** o locatário também configura no primeiro acesso. Contras: atrito no perfil mais numeroso, e a recuperação depende do admin.
3. **Tirar o opcional:** as rotas de ligar o MFA recusam o locatário. Contras: perde a proteção de quem queria.

## Decisão
Vamos usar a **opção 1**, decidida pelo usuário (PO) em 2026-11-08, implementada no SEC-036: `needs_mfa` passa a valer para qualquer usuário com `mfa_enabled` e segredo configurado. O fluxo é o mesmo dos perfis obrigatórios (token `mfa`, `POST /auth/mfa/verify`, limite de tentativas). Desligar continua exigindo senha e código atual.

## Consequências
- **Positivas:** o sistema cumpre o que mostra; o locatário que quiser ganha a mesma proteção das contas privilegiadas.
- **Negativas / custos:** o locatário que perder o autenticador depende do admin ou do gestor para reiniciar o MFA, como os outros perfis.
- **Segurança:** fecha uma falsa sensação de segurança (CWE-308, OWASP API2:2023).
