# Changelog

Todas as mudanças relevantes da API OneCheck ficam registradas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/). Enquanto a versão começar com `0.`, uma versão nova pode mudar o contrato da API; essas mudanças aparecem em **Alterado** e **Removido**.

## [Não lançado]

## [0.1.0] - 2026-11-08

Primeira versão marcada. Reúne a migração da API em PHP para Python (2026-06 a 2026-09), as correções da auditoria de segurança (2026-10) e as Sprints 11 e 12.

### Adicionado
- **Autenticação e sessão** ([ADR-0004](docs/adr/0004-sessao-jwt-refresh-rotativo-token-version.md)):
  - JWT de acesso de 60 minutos, refresh token rotativo guardado só como hash;
  - `token_version`, que encerra todas as sessões quando a senha, o perfil ou o MFA mudam.
- **MFA por TOTP** ([ADR-0005](docs/adr/0005-mfa-totp-obrigatorio-por-perfil.md), [ADR-0011](docs/adr/0011-mfa-opcional-respeitado.md)):
  - obrigatório para admin, gestor e vistoriador, com configuração no primeiro login;
  - opcional para o locatário: quando ele liga, o login passa a pedir o código.
- **Gestão de usuários:** perfis admin, gestor, vistoriador e locatário; exclusão lógica; troca de senha dedicada; só o admin gerencia admin e gestor.
- **Imóveis:**
  - cadastro com endereço e geocoding (Nominatim) e busca de CEP (ViaCEP);
  - cômodos;
  - histórico do imóvel em `GET /imoveis/{id}/historico`, com contratos, vistorias e problemas em ordem cronológica (US-017).
- **Contratos:** ciclo de vida (encerrar, cancelar) e agendamentos de vistoria. O locatário lê os agendamentos do próprio contrato (US-018).
- **Vistorias (checklists):**
  - itens por cômodo, fotos validadas pelo conteúdo;
  - envio para aceite, aceite e rejeição com motivo, laudo em PDF;
  - nova vistoria inicial depois de uma rejeição, sem alterar a rejeitada (US-020).
- **Problemas:** registro com foto e linha do tempo. O locatário dono comenta enquanto o problema não estiver resolvido ou fechado (US-019).
- **Exclusão lógica** de contrato, checklist e problema criados por engano, só antes de virarem evidência (US-015, [ADR-0008](docs/adr/0008-exclusao-logica-de-registros.md)).
- **Dashboard e auditoria:** totais com o mesmo recorte por perfil das listagens; trilha de auditoria com autor, IP e campos alterados.
- **Limite de tentativas** no login, no MFA e nas telas que pedem senha ou código.
- **Documentação:**
  - ADRs 0001 a 0012;
  - collection do Insomnia para testes manuais;
  - modelo de ameaças e registro de riscos;
  - gestão ágil em `docs/roadmap/`.
- **Testes:** suíte de integração e unitária com 1076 testes e cobertura de 96%, com cenários negados de autorização em todas as rotas restritas.
- **Licença MIT** (titular Equipe One Check).

### Alterado
- **Erros de negócio respondem com o status HTTP adequado** (400, 401, 403, 404, 409, 422) e não mais com 200 e `sucesso: false`. O envelope `{sucesso, dados, erro, erros}` não muda (DEBT-014, [ADR-0003](docs/adr/0003-status-http-dos-erros.md)).
- Problema novo nasce sempre `aberto`.
- O dashboard segue o recorte de cada perfil.
- CPF mascarado nas respostas, salvo para o próprio usuário e para o detalhe visto por admin ou gestor.
- Os tipos de agendamento (`inicial`, `encerramento`) aparecem como enum no OpenAPI.

### Removido
- **Perfil `visualizador`.** Um perfil fora da lista é recusado em qualquer rota, no login e no refresh (DEBT-015, [ADR-0009](docs/adr/0009-remocao-do-perfil-visualizador.md)).
- Status de checklist `pendente_revisao`, que nenhum fluxo gravava.
- Cópias antigas do código, o banco SQLite versionado e as credenciais fixas do seed.

### Segurança
Correções da auditoria de 2026-10-25 a 2026-11-01 (relatórios em `docs/security/correcao-*.md`), entre elas:
- **Bypass de MFA e reset pelo seed:** o token de verificação servia como sessão, e o reset de dados pelo `/admin/seed` não exigia admin (N1, N2).
- **Credenciais públicas:** o seed criava contas com senha e segredo TOTP fixos (SEC-001).
- **Uploads e limites:**
  - Pillow atualizado, assinatura conferida antes do parser e só JPEG, PNG e WebP (SEC-002, N7);
  - limite de corpo antes do roteamento (SEC-003).
- **Autorização:**
  - checagem de dono por ID para o vistoriador e nos problemas (SEC-004, item 6);
  - autorização de checklists (N3) e escalada de privilégio pelo gestor (N4).
- **Sessão:** revogação das sessões na troca de credencial (SEC-005).
- **Dependências e configuração:**
  - PyJWT no lugar do `python-jose`, lockfile com hashes (SEC-006);
  - CORS sem curinga, `/docs` desligado em produção e cabeçalhos de segurança (SEC-007);
  - container sem root e CI com actions fixadas por SHA (SEC-008).
- **Login e senhas:**
  - política de senha (SEC-011);
  - login sem enumeração de e-mails pelo tempo de resposta (SEC-013);
  - limite de tentativas e segredos obrigatórios sem valor padrão (N6, N8).
- **Dados pessoais e MFA:**
  - CPF validado, retenção de logs e tokens (SEC-014);
  - o admin não define nem conhece o segredo TOTP de outro usuário (SEC-015).
- **Testes de segurança das Sprints 11 e 12** (SEC-032, SEC-033, SEC-034, DEBT-011 e DEBT-012): cada negação confere o status, a mensagem e que nada foi gravado.

[Não lançado]: https://github.com/Anderson-Leandro/ISG022-One-Check-API-Python/compare/v0.1.0...dev
[0.1.0]: https://github.com/Anderson-Leandro/ISG022-One-Check-API-Python/releases/tag/v0.1.0
