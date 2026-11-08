# ADR-0004: Sessão com JWT curto, refresh token rotativo e `token_version`

- **Status:** aceito (registro retroativo; decisão tomada em 2026-06 e revista nas correções de segurança de 2026-10-25)
- **Data:** 2026-11-08
- **Itens relacionados:** DEBT-009, SEC-005, SEC-006, SEC-014, SEC-021, SEC-027, R-002, R-011

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
A API é chamada por clientes diferentes (web e mobile), sem cookie de sessão compartilhado. Ela precisa:
- autenticar cada requisição sem consultar uma tabela de sessões a cada chamada;
- manter o usuário logado por dias sem pedir a senha de novo;
- **encerrar todas as sessões** de uma conta quando uma credencial muda (senha, perfil, MFA, desativação). Na versão original, um token emitido antes da troca de senha continuava valendo até expirar (corrigido no SEC-005).

## Opções consideradas
1. **Sessão no servidor (tabela ou Redis) com um identificador opaco.**
   - Prós: revogação imediata e simples.
   - Contras: uma consulta por requisição; um Redis a mais no deploy gratuito.
2. **Só JWT de longa duração.**
   - Prós: nenhum estado no servidor.
   - Contras: não há como revogar; um token vazado vale até expirar.
3. **JWT curto + refresh token opaco guardado como hash + versão do usuário no JWT.**
   - Prós: o access token é conferido sem estado extra além do usuário, que já é carregado em toda rota; o refresh é revogável; a versão encerra todas as sessões de uma vez.
   - Contras: um access token já emitido vale até expirar se a versão não mudar (logout comum não o invalida).

## Decisão
Vamos usar a **opção 3**:
- **Access token:** JWT HS256 (`app/auth.py:45`), 60 minutos (`JWT_ACCESS_MINUTES`), com `sub`, `role`, `type: access`, `ver` e `exp`. O `decode_token` fixa o algoritmo e exige `exp`, `sub` e `type` (`app/auth.py:86`), o que barra `alg=none` e a troca de algoritmo.
- **Tipos separados:** os tokens do passo de MFA (`mfa`) e do primeiro acesso (`mfa_setup`) duram 10 minutos e não servem como access token (SEC-021).
- **Refresh token:** 48 bytes aleatórios (`secrets.token_urlsafe`), guardado só como SHA-256 em `auth_refresh_tokens`, 30 dias (`JWT_REFRESH_DAYS`).
- **Rotação:** cada `POST /auth/refresh` emite um par novo e apaga o refresh usado (`app/routers/auth_router.py:286`).
- **`token_version`:** a coluna do usuário entra no JWT como `ver`. `get_current_user` recusa token com versão diferente (`app/deps.py:24`). `encerrar_sessoes` (`app/auth.py:72`) incrementa a versão e apaga os refresh tokens; é chamada na troca de senha, de perfil, de MFA e na desativação. Quem fez a troca recebe um par novo (`nova_sessao`).
- **Limpeza:** refresh tokens vencidos são apagados no start (`scripts/limpar_dados_vencidos.py`, SEC-014).

## Consequências
- **Positivas:**
  - uma troca de credencial encerra todas as sessões, inclusive access tokens ainda válidos;
  - um vazamento do banco não entrega refresh tokens utilizáveis (só os hashes);
  - nenhum serviço a mais no deploy.
- **Negativas / custos:**
  - o logout apaga só o refresh enviado; o access token continua válido até expirar (no máximo 60 minutos);
  - toda requisição autenticada carrega o usuário do banco para conferir `ativo` e a versão.
- **Segurança:**
  - **reuso de refresh já trocado não é detectado:** quem roubou um refresh e o usa antes do dono ganha uma sessão paralela; o uso pelo dono depois só falha. Risco R-011, tratado no SEC-027 (encerrar todas as sessões quando um refresh trocado for reutilizado);
  - o `JWT_SECRET` é obrigatório fora de desenvolvimento, com 32 ou mais caracteres (`app/config.py`); trocar o segredo encerra todas as sessões.
