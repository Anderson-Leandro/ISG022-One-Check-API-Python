# OneCheck API (Python)

API REST de alta performance para o ecossistema **OneCheck** — gestão completa de vistorias imobiliárias, contratos de locação, agendamentos, vistorias técnicas com catálogo de itens e fotos, emissão de laudos em PDF, linha do tempo de ocorrências e auditoria detalhada.

---

## 🚀 Funcionalidades Principais

- **🔐 Autenticação & MFA (TOTP)**:
  - Autenticação JWT com access token e refresh token rotativo/revogável.
  - Segundo Fator de Autenticação (MFA via TOTP / Google Authenticator) com setup obrigatório no primeiro acesso para roles administrativas (`admin`, `gestor`, `vistoriador`).
  - Endpoints de auto-gestão de MFA (`/habilitar`, `/desabilitar`, `/setup`, `/activate`, `/disable`).
  - Gestão administrativa de MFA por usuário (`/usuarios/{id}/mfa/*`).

- **👥 Gestão de Usuários & Perfis (RBAC)**:
  - Perfis de acesso: `admin`, `gestor`, `vistoriador`, `locatario`.
  - Endpoint dedicado para alteração de senha (`PUT /usuarios/me/senha`).
  - Soft delete de usuários com bloqueio de auto-exclusão e proteção de integridade.

- **🏠 Imóveis, Endereços & Geolocalização Automática**:
  - Cadastro atômico de imóvel com endereço aninhado.
  - Geocoding automático de latitude e longitude via **OpenStreetMap / Nominatim** e busca de CEP via **ViaCEP**.
  - CRUD completo e isolamento de cômodos (`/imoveis/{id}/comodos`).
  - Soft delete protegido (bloqueio de exclusão para imóveis com locação ativa).

- **📄 Contratos de Locação & Ciclo de Vida**:
  - Vínculo de imóvel a locatário com validação de datas e disponibilidade.
  - Consulta individual com controle estrito de titularidade para locatários.
  - Encerramento (`PATCH /encerrar`) e cancelamento (`PATCH /cancelar`) com liberação atômica do status do imóvel para `disponivel`.

- **📅 Agendamentos de Vistoria**:
  - Agendamento de vistorias iniciais e de encerramento vinculadas a contratos ativos.
  - CRUD dedicado com validação de datas futuras e controle de acesso RBAC (`/agendamentos/{id}`).

- **📋 Checklists de Vistoria, Fotos & Emissão de Laudos em PDF**:
  - Catálogo de itens e preenchimento por cômodo com validação de integridade.
  - Upload e substituição segura de fotos por item vistoriado.
  - Submissão com travas de mutabilidade em estados posteriores a `em_preenchimento`.
  - Fluxo formal de aceite (`PATCH /aceitar`) e rejeição com motivo (`PATCH /rejeitar`) persistidos em tabela de histórico (`AceiteChecklist`).
  - **Geração de Laudo em PDF (Pure Python)**: Emissão de relatório estruturado completo (`GET /checklists/{id}/download`) com dados do imóvel, contrato, itens e assinaturas digitais.

- **🛠️ Registro de Problemas & Linha do Tempo**:
  - Abertura de chamados pelo locatário vinculados a contratos ativos e cômodos do imóvel, com suporte a upload de fotos.
  - Linha do tempo de atualizações cronológicas (`/problemas/{id}/atualizacoes`) com notas e anexos de reparo.
  - Notificações automáticas por e-mail/sistema para administradores e locatários (`NotificationService`).

- **📊 Dashboard & Auditoria Avançada**:
  - Métricas agregadas em tempo real (`/dashboard`): imóveis locados, checklists pendentes, problemas abertos e vistorias agendadas.
  - Central de auditoria (`GET /logs`) com rastreamento de IP, usuário, ação, entidade e payload JSON sanitizado (senhas e segredos são automaticamente ocultados).
  - Filtros avançados por data (`de`, `ate`), entidade e usuário.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| **Linguagem** | Python 3.12+ |
| **Framework** | FastAPI 0.115 + Uvicorn |
| **ORM & Banco** | SQLAlchemy 2.0 + SQLite (desenvolvimento/testes) / PostgreSQL (produção) |
| **Autenticação** | `python-jose` (JWT) + `pyotp` (TOTP MFA) + `bcrypt` |
| **Geocoding** | Nominatim (OpenStreetMap) + ViaCEP via `httpx` |
| **Geração de PDF** | Motor PDF 1.4 Pure Python (sem dependências binárias C externas) |
| **Testes Automatizados** | `pytest` + `pytest-cov` + `httpx` (448 testes, 93% de cobertura) |
| **CI / CD** | GitHub Actions |

---

## 🔒 Perfis de Acesso (RBAC)

| Role | Permissões Principais |
|---|---|
| `admin` | Acesso administrativo completo a todas as entidades, logs, relatórios e métricas. |
| `gestor` | Gestão operacional de imóveis, contratos, checklists e atendimento a problemas. |
| `vistoriador` | Execução técnica e submissão de checklists de vistorias agendadas. |
| `locatario` | Consulta exclusiva dos seus próprios imóveis/contratos, aceite de vistoria e abertura de problemas. |

---

## 📡 Mapa de Endpoints da API (`/api/v1`)

### 🔐 Autenticação & MFA
```http
POST   /api/v1/auth/login                  # Login (retorna token ou mfa_required)
POST   /api/v1/auth/mfa/verify             # Verificação de código TOTP
POST   /api/v1/auth/mfa/setup-login        # Setup de MFA durante login inicial
POST   /api/v1/auth/mfa/activate-login     # Ativação de MFA durante login inicial
POST   /api/v1/auth/refresh                # Renovação de access token
POST   /api/v1/auth/logout                 # Logout e revogação de refresh token
GET    /api/v1/auth/mfa/setup              # Obter segredo e URI de QR Code
POST   /api/v1/auth/mfa/activate           # Ativar MFA autenticado
POST   /api/v1/auth/mfa/disable            # Desativar MFA (admin)
POST   /api/v1/auth/mfa/habilitar          # Auto-habilitação de MFA
POST   /api/v1/auth/mfa/desabilitar        # Auto-desabilitação de MFA
```

### 👥 Usuários
```http
GET    /api/v1/usuarios/me                 # Dados do usuário logado
PATCH  /api/v1/usuarios/me                 # Atualizar dados próprios
PUT    /api/v1/usuarios/me/senha           # Alteração de senha
GET    /api/v1/usuarios                    # Listar usuários (admin/gestor)
POST   /api/v1/usuarios                    # Criar usuário (admin)
GET    /api/v1/usuarios/{id}               # Detalhes de usuário
PUT    /api/v1/usuarios/{id}               # Atualizar usuário
DELETE /api/v1/usuarios/{id}               # Exclusão lógica (soft delete)
POST   /api/v1/usuarios/{id}/mfa/habilitar # Habilitar MFA de usuário (admin)
POST   /api/v1/usuarios/{id}/mfa/desabilitar # Desabilitar MFA de usuário (admin)
```

### 🏠 Imóveis & Cômodos
```http
GET    /api/v1/imoveis                     # Listar imóveis
POST   /api/v1/imoveis                     # Criar imóvel (com endereço e geocoding)
GET    /api/v1/imoveis/{id}                # Detalhes do imóvel
PUT    /api/v1/imoveis/{id}                # Atualizar imóvel e endereço
DELETE /api/v1/imoveis/{id}                # Excluir imóvel (soft delete)
POST   /api/v1/imoveis/{id}/endereco       # Salvar/atualizar endereço com geocoding
GET    /api/v1/imoveis/{id}/endereco       # Consultar endereço
GET    /api/v1/imoveis/{id}/comodos        # Listar cômodos
POST   /api/v1/imoveis/{id}/comodos        # Adicionar cômodo
PUT    /api/v1/imoveis/{id}/comodos/{cid}  # Atualizar cômodo
DELETE /api/v1/imoveis/{id}/comodos/{cid}  # Excluir cômodo
```

### 📄 Contratos & Agendamentos
```http
GET    /api/v1/contratos                   # Listar contratos
POST   /api/v1/contratos                   # Criar contrato de locação
GET    /api/v1/contratos/{id}              # Detalhes do contrato
PATCH  /api/v1/contratos/{id}/encerrar     # Encerrar contrato e liberar imóvel
PATCH  /api/v1/contratos/{id}/cancelar     # Cancelar contrato e liberar imóvel
GET    /api/v1/contratos/{id}/agendamentos # Listar agendamentos do contrato
POST   /api/v1/contratos/{id}/agendamentos # Agendar vistoria
PUT    /api/v1/agendamentos/{id}           # Atualizar agendamento
DELETE /api/v1/agendamentos/{id}           # Cancelar/excluir agendamento
```

### 📋 Checklists, Fotos & Laudos
```http
GET    /api/v1/itens-vistoria              # Catálogo de itens inspecionáveis
GET    /api/v1/contratos/{id}/checklists   # Listar checklists do contrato
POST   /api/v1/contratos/{id}/checklists   # Iniciar checklist de vistoria
GET    /api/v1/checklists/{id}             # Detalhes do checklist
POST   /api/v1/checklists/{id}/itens       # Adicionar item ao checklist
PUT    /api/v1/checklists/{id}/itens/{iid} # Atualizar estado/observação do item
POST   /api/v1/checklists/{id}/itens/{iid}/fotos # Upload de foto do item
DELETE /api/v1/checklists/{id}/itens/{iid}/fotos/{fid} # Excluir foto
PATCH  /api/v1/checklists/{id}/submeter    # Submeter vistoria (vistoriador)
PATCH  /api/v1/checklists/{id}/enviar-para-aceite # Enviar para aceite
PATCH  /api/v1/checklists/{id}/aceitar     # Aceite formal da vistoria (locatário)
PATCH  /api/v1/checklists/{id}/rejeitar    # Rejeição com motivo (locatário)
GET    /api/v1/checklists/{id}/download    # Download do Laudo de Vistoria em PDF
```

### 🛠️ Problemas & Linha do Tempo
```http
GET    /api/v1/contratos/{id}/problemas    # Listar problemas do contrato
POST   /api/v1/contratos/{id}/problemas    # Registrar ocorrência (locatário/admin)
GET    /api/v1/problemas/{id}              # Detalhes da ocorrência
PATCH  /api/v1/problemas/{id}/status       # Atualizar status (admin/gestor)
GET    /api/v1/problemas/{id}/atualizacoes # Linha do tempo de atualizações
POST   /api/v1/problemas/{id}/atualizacoes # Adicionar atualização com foto
```

### 📊 Dashboard, Logs & Sistema
```http
GET    /api/v1/dashboard                   # Métricas consolidadas em tempo real
GET    /api/v1/logs                        # Logs de auditoria (com filtros e paginação)
GET    /api/v1/health                      # Health check da API
GET    /api/v1/uploads/{filename}          # Servir arquivos estáticos/fotos
```

---

## 💻 Executando o Projeto Localmente

### 1. Clonar e Acessar o Diretório
```bash
git clone <url-do-seu-repositorio>
cd trabalho_kleber_api_python
```

### 2. Configurar o Ambiente Virtual
```bash
python3 -m venv .venv

# No Linux / macOS:
source .venv/bin/activate

# No Windows:
.venv\Scripts\activate
```

### 3. Instalar as Dependências
```bash
pip install -r requirements.txt
```

### 4. Configurar Variáveis de Ambiente (`.env`)
Crie um arquivo `.env` na raiz do projeto (opcional em desenvolvimento):
```env
JWT_SECRET=sua_chave_secreta_jwt_super_segura
SEED_SECRET=sua_chave_secreta_para_admin_seed
# DATABASE_URL=postgresql://usuario:senha@localhost:5432/onecheck
```

### 5. Iniciar a API
```bash
uvicorn app.main:app --reload
```
A API estará rodando em: `http://localhost:8000`  
Documentação Swagger interativa: `http://localhost:8000/docs`

---

## 🧪 Executando os Testes Automatizados

A suíte de testes cobre 100% dos fluxos de negócio com **448 testes automatizados** e **93% de cobertura**:

```bash
# Executar todos os testes
.venv/bin/pytest

# Executar com relatório detalhado de cobertura linha por linha
.venv/bin/pytest --cov=app --cov-report=term-missing

# Executar testes em modo verboso
.venv/bin/pytest -v
```

---

## 📁 Estrutura do Repositório

```
├── app/
│   ├── auth.py                  # Autenticação JWT, Bcrypt, TOTP MFA
│   ├── config.py                # Configurações e variáveis de ambiente
│   ├── database.py              # Conexão SQLAlchemy e migração incremental
│   ├── deps.py                  # Injeção de dependências e controle de roles (RBAC)
│   ├── geocoding.py             # Módulo de integração OpenStreetMap e ViaCEP
│   ├── main.py                  # Inicialização da aplicação FastAPI e CORS
│   ├── models.py                # Modelagem ORM relacional do banco de dados
│   ├── notification_service.py  # Serviço de notificações para admins e locatários
│   ├── pdf_generator.py         # Motor de renderização de Laudos em PDF (Pure Python)
│   ├── schemas.py               # Schemas Pydantic, DTOs e envelopes de resposta
│   ├── seed_service.py          # Serviço de carga e recriação de dados de demonstração
│   ├── serializers.py           # Serializadores de dados e registro de auditoria
│   └── routers/                 # Roteadores modulares organizados por recurso
│       ├── admin.py
│       ├── agendamentos.py
│       ├── auth_router.py
│       ├── checklists.py
│       ├── contratos.py
│       ├── dashboard.py
│       ├── health.py
│       ├── imoveis.py
│       ├── problemas.py
│       └── usuarios.py
├── docs/                        # Documentação de arquitetura e segurança (ISG-022)
│   ├── architecture/            # Diagramas e arquitetura da aplicação
│   └── security/                # Baseline de segurança e análise de riscos
└── tests/
    ├── conftest.py              # Fixtures globais do pytest e clientes de teste
    ├── unit/                    # Testes unitários (auth, pdf, geocoding, schemas, serializers)
    └── integration/             # Testes de integração de todas as rotas da API
```
