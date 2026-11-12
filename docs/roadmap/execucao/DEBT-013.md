# DEBT-013 — Mensagem de erro específica para token de verificação usado no setup-login e no activate-login

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 14 · **Issue:** #112 · **Branch:** `fix/DEBT-013-mensagem-token-verificacao` · **PR:** #<n>

## Entrega
`GET /auth/mfa/setup-login` e `POST /auth/mfa/activate-login` respondiam "Token MFA inválido ou expirado" tanto para um token ilegível ou expirado quanto para um token válido do tipo `mfa`, que é emitido para quem já tem autenticador. A recusa continua igual (falha N1, SEC-021). Só a mensagem desse caso passa a apontar o caminho certo.

- **`app/routers/auth_router.py`:** `_erro_do_token_de_primeiro_acesso` decide a mensagem só pelo token, antes de qualquer consulta ao banco. As duas rotas a usam.

| Critério de aceite | Prova |
|---|---|
| Token temporário válido do tipo `mfa` no `GET /auth/mfa/setup-login`: 401 com a mensagem que indica o `/auth/mfa/verify` | `TestTokenDeVerificacao::test_recusa_com_a_mensagem_especifica[setup-login]` |
| O mesmo token no `POST /auth/mfa/activate-login`: `sucesso=false` com a mesma mensagem, e nenhum segredo gerado ou alterado | `test_recusa_com_a_mensagem_especifica[activate-login]` (o `mfa_secret` e o `mfa_secret_pendente` não mudam) |
| Token ilegível, com assinatura inválida ou expirado: a mensagem continua genérica | `TestOutrosTokensContinuamGenericos` (os três casos nas duas rotas) |
| A recusa do token `mfa` acontece antes de consultar o usuário; `test_seguranca_mfa_bypass.py` continua passando, com teste novo para cada mensagem | `test_recusa_antes_de_consultar_o_usuario` (com o id de um usuário que não existe, a resposta é a mesma). A suíte inteira passa |
| A collection do Insomnia é atualizada com a nova mensagem | O caso "Token de verificação não serve no setup-login → 401" passa a esperar a nova mensagem: 168/168. A pasta 00a, rodada à parte, tem as mesmas exceções documentadas no TK-020 |

## Testes
- **Novos:** 11 testes em `tests/integration/test_mfa_mensagem_token_verificacao.py`.
  - Antes da mudança, falhavam os 4 da mensagem específica.
  - Os 6 da mensagem genérica já passavam e garantem que ela continua nos outros casos.
- **Suíte completa:** 1482 passaram, 6 pulados, cobertura de branches em 97%. Rodada por `scripts/testes_na_copia.sh`, sem o arquivo de segredos local.

## Segurança
- `/security-audit diff dev` em 2026-11-11: os 7 scanners com status `ok`. **Nenhum achado novo.**
  - **Falsos positivos:**
    - o bandit lê como senha as constantes das mensagens (`TOKEN_DE_VERIFICACAO`, `TOKEN_MFA_INVALIDO`);
    - o semgrep acusa a chave JWT do teste de assinatura inválida, que é fictícia.
  - O SHA-1 do `gerar_collection.py` (id determinístico da collection) e os demais já existiam.
- `/code-review` (medium), com 7 apontamentos:
  - **Corrigidos:**
    - a mensagem cita o caminho completo (`POST /api/v1/auth/mfa/verify`), com um teste;
    - a constante da mensagem genérica vale em todo o arquivo;
    - a função auxiliar ficou mais simples;
    - os testes importam as constantes, em vez de copiar o texto.
  - **Sem mudança:**
    - o caminho inverso (token de primeiro acesso no `/mfa/verify`) fica fora dos critérios deste item;
    - a dica também aparece para um token `mfa` de sessão revogada, porque o critério pede a recusa antes de consultar o banco. O `/mfa/verify` recusa o token depois.
- **A mensagem nova não revela nada que o token já não diga.** Ela depende só do tipo, que quem tem o token consegue ler. Ela não depende da conta, então não diz se a conta existe nem se tem autenticador.
- A barreira da falha N1 continua: o token `mfa` nunca serve no primeiro acesso.

## Checklist antes da revisão
- [-] Campos que o perfil que ganha acesso passa a ver: não se aplica, ninguém ganha acesso.
- [-] Status finais: não se aplica.
- [x] Autorização antes de ler o corpo: a conferência do tipo do token continua antes da consulta ao usuário e de qualquer gravação.
- [x] Login, refresh e tokens: o token `mfa` continua recusado nas duas rotas, e o `/mfa/verify` não muda. A suíte de MFA (`test_seguranca_mfa_bypass.py` e as demais) passa.
- [x] Perfis proibidos barrados antes da busca por ID: a resposta não depende do usuário do token (`test_recusa_antes_de_consultar_o_usuario`).

## Testes existentes alterados
Nenhum.

## Documentação
- Collection do Insomnia: o caso do token de verificação no setup-login espera a nova mensagem.
