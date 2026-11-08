# ADR-0005: MFA por TOTP, obrigatório para admin, gestor e vistoriador

- **Status:** aceito (registro retroativo; decisão tomada em 2026-06 e revista nas correções de segurança de 2026-10); complementado pelo ADR-0011 (o MFA opcional passa a valer no login) e pelo ADR-0009 (o perfil visualizador é removido)
- **Data:** 2026-11-08
- **Itens relacionados:** DEBT-009, US-002, SEC-021, SPK-003, SEC-035, R-002, R-013

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
Admin, gestor e vistoriador criam e alteram laudos, contratos e contas. Uma senha vazada de um desses perfis dá acesso a dados de todos os imóveis e permite fraudar laudos (R-002). Locatário e visualizador só veem os próprios dados. A API não tem envio de SMS nem de e-mail transacional.

## Opções consideradas
1. **MFA opcional para todos.**
   - Prós: nenhum atrito no primeiro acesso.
   - Contras: as contas privilegiadas ficam protegidas só se cada pessoa quiser.
2. **TOTP (RFC 6238) obrigatório nos perfis privilegiados e opcional nos outros.**
   - Prós: não depende de serviço externo nem de custo por mensagem; funciona com qualquer app autenticador.
   - Contras: perder o celular exige que o admin reinicie o MFA da conta.
3. **Código por e-mail ou SMS.**
   - Prós: familiar para o usuário.
   - Contras: precisa de provedor pago; SMS é vulnerável a troca de chip; o e-mail costuma ser a conta que já vazou.
4. **WebAuthn / passkeys.**
   - Prós: resistente a phishing.
   - Contras: mais complexo de implementar nos dois clientes; sem suporte uniforme no parque de aparelhos dos vistoriadores.

## Decisão
Vamos usar a **opção 2**:
- **Perfis obrigatórios:** `MFA_REQUIRED_ROLES = {"admin", "vistoriador", "gestor"}` (`app/auth.py:21`). Para eles, o MFA não pode ser desligado (`app/routers/usuarios.py:219` responde 422) e uma promoção para esses perfis liga o MFA.
- **Login em dois passos:** senha correta devolve um token curto em vez da sessão:
  - quem já tem autenticador recebe `mfa_required` e um token `mfa` para `POST /auth/mfa/verify`;
  - quem ainda não configurou recebe `mfa_setup_required` e um token `mfa_setup`, que só serve para `GET /auth/mfa/setup-login` e `POST /auth/mfa/activate-login`. Os dois tipos não se trocam (SEC-021).
- **Configuração:** o segredo gerado fica em `mfa_secret_pendente` e só vira `mfa_secret` depois que um código válido o confirma. Trocar um autenticador em uso exige o código atual (`mfa_troca_error`).
- **Conferência:** `pyotp`, janela de ±1 passo de 30 segundos (`valid_window=1`).
- **Limite de tentativas:** códigos errados contam por conta e por IP (`app/rate_limit.py`), com bloqueio temporário (R-013).
- **Recuperação:** o admin ou o gestor reinicia o MFA da conta (`reset_mfa`); em perfis obrigatórios, o próximo login pede a configuração de novo. Toda mudança de MFA encerra as sessões (ADR-0004).
- **Locatário e visualizador:** MFA opcional. Se deve passar a valer para eles é a pergunta do SPK-003.

## Consequências
- **Positivas:**
  - uma senha vazada de conta privilegiada não basta para entrar;
  - nenhum custo nem serviço externo para enviar códigos.
- **Negativas / custos:**
  - não há códigos de recuperação: quem perde o autenticador depende de outra pessoa com perfil admin ou gestor;
  - o primeiro acesso das contas privilegiadas tem um passo a mais.
- **Segurança:**
  - o segredo TOTP fica em texto no banco (ativo A-01); quem lê o banco consegue gerar códigos. Cifrar a coluna fica para quando houver gestão de chaves (o mesmo caso do CPF, SEC-031);
  - **o `qr_url` devolvido no setup aponta para um serviço externo** (`api.qrserver.com`, `app/auth.py:178`) e leva na URL o `otpauth://` com o segredo e o e-mail. Quem abre o QR entrega a semente do MFA a um terceiro. Registrado em 2026-11-08, na escrita deste ADR, como SEC-035;
  - o código TOTP pode ser reusado dentro da janela de 90 segundos; o limite de tentativas reduz, mas não elimina, o ataque de quem já viu o código.
