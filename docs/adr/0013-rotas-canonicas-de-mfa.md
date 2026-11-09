# ADR-0013: Uma rota canônica por operação de MFA, e os aliases com data de remoção

- **Status:** aceito
- **Data:** 2026-11-08
- **Itens relacionados:** DEBT-003, ADR-0005, ADR-0011

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
A conversão da API em PHP deixou o MFA espalhado em duas famílias de rotas, `/auth/mfa/*` e `/usuarios/*/mfa`, com operações repetidas e regras diferentes:
- **Configurar o próprio autenticador:**
  - `POST /auth/mfa/setup` + `/auth/mfa/activate` guardam o segredo **pendente no servidor**;
  - `POST /usuarios/me/mfa/setup` + `/me/mfa/enable` devolvem o segredo e esperam que o cliente o reenvie.
- **Desligar o próprio MFA:** `POST /auth/mfa/desabilitar` e `DELETE /usuarios/me/mfa`.
- **Resetar o MFA de outro usuário:**
  - `POST /auth/mfa/disable`, só admin;
  - `DELETE /usuarios/{id}/mfa` e `POST /usuarios/{id}/mfa/desabilitar`: admin e gestor, com as regras de gestão de usuários.
- **Exigir o MFA de outro usuário:** `POST /usuarios/{id}/mfa/enable` e `/habilitar`.
- `GET /auth/mfa/setup`, marcado como obsoleto: um GET que grava estado.

Duas rotas para a mesma operação dobram a superfície que precisa de testes e de revisão, e as regras divergem com o tempo (o reset já tinha permissões diferentes).

## Decisão
Tomada pelo usuário (PO) em 2026-11-08: **separar pelo ator**.
- **O próprio MFA:** `/auth/mfa/*`, com `setup`, `activate`, `habilitar` e `desabilitar`. O segredo pendente fica no servidor e o cliente não o reenvia.
- **O MFA de outro usuário:** `/usuarios/{id}/mfa`, com `POST .../enable` e `DELETE`. Valem as mesmas regras da gestão de usuários: a própria conta não, e só admin gerencia admin e gestor.
- **Obsoletas até 2027-01-31:**
  - `POST /usuarios/me/mfa/setup`, `POST /usuarios/me/mfa/enable` e `DELETE /usuarios/me/mfa`;
  - `POST /usuarios/{id}/mfa/habilitar` e `POST /usuarios/{id}/mfa/desabilitar`;
  - `POST /auth/mfa/disable`.
  - Até lá, elas continuam com o comportamento atual. Têm `deprecated: true` no OpenAPI, com a data na descrição, e toda resposta delas traz `Deprecation` (RFC 9745) e `Sunset` (RFC 8594). Também traz `Link rel="successor-version"` com a URL da sucessora, menos no `/auth/mfa/disable`, cuja sucessora depende do `usuario_id` do corpo. O método da sucessora, que pode ser outro, está na descrição do OpenAPI. A tabela de `app/obsoletas.py` é a única fonte do OpenAPI e dos cabeçalhos, e o CORS expõe esses cabeçalhos.
- **Removida agora:** `GET /auth/mfa/setup` (responde `405`).

## Alternativas consideradas
- **Tudo em `/usuarios`** (`/usuarios/me/mfa/*` e `/usuarios/{id}/mfa`), deixando em `/auth/mfa/*` só o fluxo do login: mais próximo de REST. Seria preciso mudar o contrato do `/me/mfa/enable` para o segredo pendente, e as rotas do próprio usuário que já seguem o modelo seguro estão em `/auth`.
- **Remover os aliases já:** mais simples, mas quebraria as integrações sem aviso.

## Consequências
- Depois de 2027-01-31, um item remove as rotas da tabela, junto com os testes delas.
- O reset pelo `DELETE /usuarios/{id}/mfa` também aceita o gestor (para locatário e vistoriador). No alias `/auth/mfa/disable`, que era só do admin, a regra continua até a remoção.
