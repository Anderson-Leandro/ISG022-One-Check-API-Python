# Security Baseline — OneCheck API

## 1. Contexto do Sistema

O **OneCheck** é um sistema para automação e segurança no fluxo de vistorias de locação imobiliária. A aplicação é composta por uma API Backend em Python (FastAPI + SQLAlchemy) que atende a quatro perfis de usuários com diferentes níveis de privilégio:
- **Administrador (`admin`):** Responsável pela gestão de usuários, parametrizações, auditoria e controle geral do sistema.
- **Gestor (`gestor`):** Responsável pela gestão de carteira imobiliária, alocação de vistorias e contratos.
- **Vistoriador (`vistoriador`):** Responsável pela execução em campo de vistorias, registro fotográfico de cômodos e apontamento de avarias.
- **Locatário (`locatario`):** Inquilino titular do contrato que consulta o laudo de vistoria e realiza o aceite ou contestação formal do estado do imóvel.

---

## 2. Ativos Prioritários

| Ativo | Valor / Por que tem valor? | CIA/AUT mais relevante | Responsável / Componente |
|---|---|---|---|
| **1. Dados Cadastrais e Credenciais dos Usuários (`Usuario`)** | Contém dados pessoais protegidos por lei (LGPD), hashes de senha e segredos TOTP de MFA. Sua exposição causa usurpação de identidade e acesso indevido generalizado. | **C + AUT** (Confidencialidade + Autenticidade) | Backend (`app/routers/auth_router.py`, `app/routers/usuarios.py`) / Banco de Dados |
| **2. Dados Cadastrais e Endereço dos Imóveis (`Imovel` + `Endereco`)** | Define o patrimônio sob gestão da imobiliária e a localização física dos inquilinos (com geocoding de alta precisão). Adulteração causa desorganização operacional e exposição gera violação de privacidade residencial. | **I + C** (Integridade + Confidencialidade) | Backend (`app/routers/imoveis.py`, `app/geocoding.py`) / Banco de Dados |
| **3. Contratos de Locação e Vínculos de Acesso (`Contrato`)** | Estabelece as regras jurídicas de locação e atua como a âncora de autorização (ACL/ABAC): um locatário só pode acessar dados do imóvel e checklists associados ao seu contrato ativo. | **I + AUT** (Integridade + Autenticidade) | Backend (`app/routers/contratos.py`) / Banco de Dados |
| **4. Laudos de Vistoria e Registros de Aceite (`Checklist` + `ItemChecklist` + `AceiteChecklist`)** | Documento comprobatório pericial do estado físico do imóvel na entrega e na devolução das chaves. Possui valor legal e probatório em disputas judiciais e ressarcimento de danos. | **I + AUT** (Integridade + Autenticidade) | Backend (`app/routers/checklists.py`) / Banco de Dados / Storage |
| **5. Logs de Auditoria e Rastreabilidade Operacional (`LogOperacao`)** | Registra todas as mutações e acessos críticos (autor, entidade, ID, ação, data/hora, IP de origem e payload). Permite investigação de incidentes, resolução de conflitos e garantia de não-repúdio. | **I + A** (Integridade + Disponibilidade) | Backend (`app/serializers.py`, `app/routers/dashboard.py`) / Banco de Dados |

---

## 3. Princípios Adotados e Decisões de Projeto

### Menor Privilégio
- **Decisão no Projeto:** Locatários só podem consultar imóveis e laudos vinculados a contratos ativos dos quais são titulares diretos. Endpoints de gerenciamento (criação, edição e exclusão de imóveis, usuários e catálogo de itens) exigem perfil administrativo (`admin` ou `gestor`), com bloqueio por dependência injetada (`require_roles`).
- **Controle:** Verificação estrita de RBAC e validação contextual de titularidade no banco antes de retornar qualquer registro.

### Defesa em Profundidade
- **Decisão no Projeto:** A segurança não depende apenas da autenticação por senha. Contas administrativas e técnicas (`admin`, `gestor`, `vistoriador`) exigem autenticação em dois fatores (MFA via TOTP). Adicionalmente, tokens JWT possuem tempo de expiração curto (15 minutos), exigindo rotação periódica via Refresh Token em hash SHA-256 no banco de dados.
- **Controle:** `needs_mfa` + `mfa_setup_required` no login, tokens temporários restritos para setup de 2FA e invalidação atômica de refresh tokens no logout e no refresh.

### Redução da Superfície de Ataque
- **Decisão no Projeto:** Endpoints não expõem campos sensíveis como `senha_hash` ou segredos brutos de TOTP nas respostas JSON. Respostas de erro de autenticação utilizam mensagens genéricas (`"Credenciais inválidas"`), impedindo enumeração de e-mails válidos.
- **Controle:** Serializers dedicados e schemas Pydantic de saída (`UsuarioOut`, `LoginResponse`, etc.) expurgando campos internos.

### Secure by Default
- **Decisão no Projeto:** Ao cadastrar um novo usuário administrativo, a flag `mfa_enabled` é inicializada como verdadeira automaticamente. Caso o usuário ainda não tenha configurado seu app autenticador, o login bloqueia a emissão do `access_token` e força o fluxo de onboarding seguro (`/auth/mfa/setup-login` ➔ `/auth/mfa/activate-login`).
- **Controle:** Verificação automatizada no endpoint `/auth/login` retornando `mfa_setup_required: true`.

### Fail Secure
- **Decisão no Projeto:** Na falha de qualquer dependência externa (ex.: indisponibilidade do OpenStreetMap / ViaCEP para busca de coordenadas), a criação do imóvel não é abortada nem expõe falhas internas; o sistema grava o endereço com coordenadas nulas e loga o aviso com segurança, sem quebrar a integridade transacional. Caso uma validação de contrato falhe, o sistema retorna erro 403 e nega o acesso por padrão.
- **Controle:** Blocos `try/except` com timeouts rígidos (5s) em `app/geocoding.py` e bloqueio preventivo de acessos não autorizados.

### Fronteiras de Confiança
- **Decisão no Projeto:** Todos os dados recebidos da zona não confiável (Internet/Frontend) são estritamente validados contra esquemas Pydantic antes de atingirem a lógica de negócio ou o banco de dados. A camada de persistência utiliza o ORM SQLAlchemy para garantir parametrização total de queries contra SQL Injection.
- **Controle:** Schemas Pydantic tipados com limites de tamanho, formato e regex; ORM com sessões transacionais controladas.

---

## 4. Riscos Residuais e Premissas

- **Premissa 1:** A infraestrutura de produção executará obrigatoriamente sobre TLS/HTTPS com certificados válidos e segredos de ambiente (`JWT_SECRET`) fortes e confidenciais.
- **Risco Residual 1 (Comprometimento de Dispositivo do Vistoriador/Admin):** Se o dispositivo físico ou aplicativo autenticador do usuário for comprometido, um atacante pode gerar tokens de 6 dígitos. *Mitigação:* Mecanismo de revogação/reset administrativo de MFA (`POST /auth/mfa/disable`) e expiração curta de sessões.
- **Risco Residual 2 (Dependência de Terceiros para Geocoding):** Mudanças de termos de uso ou indisponibilidade da API pública do OpenStreetMap podem limitar temporariamente o cálculo automático de latitude/longitude. *Mitigação:* O sistema permite inserção manual de coordenadas e fallback gracioso.

---

## 5. Próximos Passos (Roadmap de Segurança)

1. **Implementação de Rate Limiting:** Adicionar controle de taxa de requisições nos endpoints sensíveis (`/auth/login`, `/auth/mfa/*`) para prevenir ataques de força bruta.
2. **Armazenamento Seguro de Mídias (S3 com Presigned URLs):** Migrar upload de fotos de vistoria do disco local para bucket em nuvem com URLs assinadas e expiração automática.
3. **Assinatura Digital de PDF (ICP-Brasil / Hash Sha-256):** Implementar carimbo de tempo e hash criptográfico nos laudos de vistoria gerados para garantir imutabilidade probatória.
