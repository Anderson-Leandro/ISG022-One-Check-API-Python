# OneCheck API (Python)

API REST de alta performance para o ecossistema **OneCheck** — gestão completa de vistorias imobiliárias, contratos de locação, agendamentos, vistorias técnicas com catálogo de itens e fotos, emissão de laudos em PDF, linha do tempo de ocorrências e auditoria detalhada.

---

## 🚀 Funcionalidades Principais

- **🔐 Autenticação & MFA (TOTP)**:
  - Autenticação JWT com access token e refresh token rotativo/revogável.
  - Segundo fator (MFA via TOTP / Google Authenticator) obrigatório para `admin`, `gestor` e `vistoriador`, com configuração no primeiro login.
  - Troca de autenticador com prova de posse do atual; desativação do próprio MFA com senha e código.
  - Limite de tentativas no login, no MFA e nas telas que pedem senha ou código.
  - Troca de senha, de autenticador ou de perfil encerra todas as sessões do usuário.

- **👥 Gestão de Usuários & Perfis (RBAC)**:
  - Perfis de acesso: `admin`, `gestor`, `vistoriador`, `locatario`, `visualizador`.
  - Só `admin` atribui ou gerencia os perfis `admin` e `gestor`; a própria conta só muda por `/usuarios/me`.
  - Endpoint dedicado para alteração de senha (`PUT /usuarios/me/senha`).
  - Soft delete de usuários com bloqueio de auto-exclusão e proteção de integridade.

- **🏠 Imóveis, Endereços & Geolocalização Automática**:
  - Cadastro atômico de imóvel com endereço aninhado.
  - Geocoding automático de latitude e longitude via **OpenStreetMap / Nominatim** e busca de CEP via **ViaCEP**.
  - CRUD completo e isolamento de cômodos (`/imoveis/{id}/comodos`).
  - Soft delete protegido (bloqueio de exclusão para imóveis com locação ativa).

- **📄 Contratos de Locação & Ciclo de Vida**:
  - Vínculo de imóvel a locatário com validação de datas e disponibilidade.
  - Consulta individual restrita por perfil: o locatário vê só os próprios contratos, e o vistoriador só aqueles em que tem vistoria.
  - Encerramento (`/encerrar`) e cancelamento (`/cancelar`) com liberação atômica do status do imóvel para `disponivel`.

- **📅 Agendamentos de Vistoria**:
  - Agendamento de vistorias iniciais e de encerramento vinculadas a contratos ativos.
  - CRUD dedicado com validação de datas futuras e controle de acesso RBAC (`/agendamentos/{id}`).

- **📋 Checklists de Vistoria, Fotos & Emissão de Laudos em PDF**:
  - Criação da vistoria por `admin`/`gestor`, atribuída a um usuário com perfil `vistoriador`, em contrato ativo.
  - Catálogo de itens e preenchimento por cômodo com validação de integridade.
  - Upload de fotos validado pelo conteúdo (só JPEG, PNG e WebP).
  - Submissão com travas de mutabilidade em estados posteriores a `em_preenchimento`.
  - Fluxo formal de aceite (`PATCH /aceitar`) e rejeição com motivo (`PATCH /rejeitar`) persistidos em tabela de histórico (`AceiteChecklist`). Quem fez a vistoria não a aprova.
  - **Geração de Laudo em PDF (Pure Python)**: relatório estruturado completo (`GET /checklists/{id}/download`) com dados do imóvel, contrato, itens e assinaturas digitais.

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
| **Framework** | FastAPI 0.162 + Starlette 1.10 + Uvicorn |
| **ORM & Banco** | SQLAlchemy 2.0 + SQLite (desenvolvimento/testes) / PostgreSQL (produção) |
| **Autenticação** | `PyJWT` (JWT HS256) + `pyotp` (TOTP MFA) + `bcrypt` |
| **Imagens** | `Pillow` 13 (validação de uploads) |
| **Geocoding** | Nominatim (OpenStreetMap) + ViaCEP via `httpx` |
| **Geração de PDF** | Motor PDF 1.4 Pure Python (sem dependências binárias C externas) |
| **Dependências** | `requirements.txt` (diretas) + `requirements.lock` (todas, com hash) |
| **Testes Automatizados** | `pytest` + `pytest-cov` + `httpx` (733 testes, 94% de cobertura) |
| **CI / CD** | GitHub Actions (testes em PostgreSQL + auditoria de dependências com `pip-audit`) |

---

## 🔒 Perfis de Acesso (RBAC)

| Role | MFA | Permissões Principais |
|---|---|---|
| `admin` | Obrigatório | Acesso administrativo completo; único que atribui ou gerencia `admin` e `gestor`. |
| `gestor` | Obrigatório | Gestão operacional de imóveis, contratos, agendamentos, vistorias, problemas e usuários `vistoriador`, `locatario` e `visualizador`. |
| `vistoriador` | Obrigatório | Preenchimento e submissão das vistorias atribuídas a ele; leitura dos contratos e imóveis dessas vistorias. |
| `locatario` | Opcional | Consulta dos próprios contratos e imóveis, aceite ou rejeição de vistoria e abertura de problemas. |
| `visualizador` | Opcional | Leitura de imóveis, contratos e vistorias, sem acesso a problemas e usuários. |

### Quem acessa cada recurso

| Recurso | admin, gestor | visualizador | vistoriador | locatário |
|---|---|---|---|---|
| Contratos e imóveis (lista e por ID, endereço, cômodos) | Todos | Todos (leitura) | Só os com vistoria dele | Só os próprios (imóvel com contrato ativo) |
| Agendamentos do contrato | Todos | Todos (leitura) | Só os contratos com vistoria dele | Sem acesso |
| Vistorias (checklists) | Todas | Todas (leitura) | Só as atribuídas a ele | Só as dos próprios contratos |
| Problemas | Todos | Sem acesso | Sem acesso | Só os dos próprios contratos |
| Usuários (`/usuarios`) | Sim (gestor: exceto admin/gestor) | Sem acesso | Sem acesso | Sem acesso |
| Logs de auditoria | Sim | Sem acesso | Sem acesso | Sem acesso |

---

## 📐 Convenções da API

### Respostas
- Sucesso e erros de regra de negócio usam o envelope `{"sucesso": bool, "dados": ..., "erro": "mensagem" | null}`. Erros de negócio respondem `200` (alguns de validação, `422`, com `erros: {campo: mensagem}`).
- Falhas de acesso e de protocolo usam `{"detail": "mensagem"}`:

| Status | Quando |
|---|---|
| `400` | `Content-Length` inválido; mais de um arquivo no upload |
| `401` | Token ausente, inválido ou expirado; sessão encerrada por troca de credencial (`"Sessão encerrada; faça login novamente"`) |
| `403` | Perfil sem permissão ou recurso fora do escopo do usuário |
| `404` | Rota ou arquivo inexistente; `/admin/*` sem `SEED_SECRET` |
| `409` | Setup de MFA de primeiro acesso para quem já tem MFA |
| `413` | Corpo acima do limite (`MAX_UPLOAD_MB` + 1 MB para multipart, `MAX_BODY_KB` para o resto) |
| `429` | Muitas tentativas falhas; o header `Retry-After` traz a espera em segundos |

### Sessão e tokens
- `Authorization: Bearer <access_token>` em todas as rotas autenticadas. A API não usa cookies; o front não deve enviar credenciais de navegador (`credentials: "include"` / `withCredentials`).
- Access token: 60 min (`JWT_ACCESS_MINUTES`). Refresh token: 30 dias (`JWT_REFRESH_DAYS`), trocado a cada `POST /auth/refresh`.
- Trocar senha, autenticador, perfil ou MFA, ou desativar a conta, encerra **todas** as sessões do usuário. Quando a troca é feita pelo próprio usuário, a resposta traz o par novo em `dados.sessao = {access_token, refresh_token}`.

### Login com MFA
1. `POST /auth/login` → tokens direto (usuário sem MFA), ou `mfa_required` / `mfa_setup_required` com um `temp_token` (10 min) que só vale para o passo seguinte.
2. `mfa_required` → `POST /auth/mfa/verify` com `{temp_token, codigo}`.
3. `mfa_setup_required` → `GET /auth/mfa/setup-login` (segredo e QR code) e `POST /auth/mfa/activate-login` com o código. O segredo só passa a valer depois da ativação.

### Limite de tentativas
5 falhas por conta ou 20 por IP em 15 minutos → `429`. Vale para login, MFA (`verify`, `activate-login`, `activate`, `desabilitar`) e para as rotas de `/usuarios/me` que pedem senha ou código.

### Uploads
- Multipart, um arquivo por requisição. Só JPEG, PNG e WebP, verificados pelo conteúdo, até 10 MB (`MAX_UPLOAD_MB`) e 50 megapixels.
- O arquivo é gravado com nome aleatório; use a URL devolvida (`/api/v1/uploads/<nome>`). `foto_url` em JSON só aceita um upload existente desta API.

### Cabeçalhos e CORS
- Todas as respostas levam `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` e `Referrer-Policy: no-referrer`; as da API (exceto fotos) levam `Cache-Control: no-store`; fora de desenvolvimento, `Strict-Transport-Security`.
- CORS só para as origens de `CORS_ORIGINS`, sem credenciais. `Retry-After` e `Content-Disposition` ficam legíveis pelo front.
- `/docs`, `/redoc` e `/openapi.json` só existem em desenvolvimento ou com `DOCS_ENABLED=true`.

---

## 📡 Mapa de Endpoints da API (`/api/v1`)

Entre parênteses, os perfis exigidos. Sem indicação: qualquer usuário autenticado, com as restrições de escopo da tabela de perfis.

### 🔐 Autenticação & MFA
```http
POST   /api/v1/auth/login                  # Login: tokens, mfa_required ou mfa_setup_required (público)
POST   /api/v1/auth/mfa/verify             # Código TOTP com o temp_token de mfa_required (público)
GET    /api/v1/auth/mfa/setup-login        # Segredo e QR code no primeiro acesso (temp_token de mfa_setup_required)
POST   /api/v1/auth/mfa/activate-login     # Ativa o MFA do primeiro acesso e emite os tokens (temp_token)
POST   /api/v1/auth/refresh                # Renova o access token e troca o refresh token (público)
POST   /api/v1/auth/logout                 # Revoga o refresh token enviado
POST   /api/v1/auth/mfa/setup              # Novo segredo pendente (o autenticador atual continua valendo)
GET    /api/v1/auth/mfa/setup              # Obsoleto: use o POST
POST   /api/v1/auth/mfa/activate           # Confirma o segredo pendente; {codigo, codigo_atual} — devolve dados.sessao
POST   /api/v1/auth/mfa/habilitar          # Liga o MFA; o autenticador é configurado no próximo login
POST   /api/v1/auth/mfa/desabilitar        # Desliga o próprio MFA; {senha, codigo} — 403 em perfis obrigatórios; devolve dados.sessao
POST   /api/v1/auth/mfa/disable            # Reset do MFA de outro usuário; {usuario_id} (admin)
```

### 👥 Usuários
```http
GET    /api/v1/usuarios/me                 # Dados do usuário logado
PATCH  /api/v1/usuarios/me                 # Atualizar dados próprios; com senha_nova exige senha_atual e devolve dados.sessao
PUT    /api/v1/usuarios/me/senha           # Alteração de senha; {senha_atual, nova_senha} — devolve dados.sessao
POST   /api/v1/usuarios/me/mfa/setup       # Gera um segredo e o QR code
POST   /api/v1/usuarios/me/mfa/enable      # Ativa/troca o autenticador; {secret, codigo, codigo_atual} — devolve dados.sessao
DELETE /api/v1/usuarios/me/mfa             # Desliga o próprio MFA; {senha, codigo} — devolve dados.sessao
GET    /api/v1/usuarios                    # Listar usuários; ?role= (admin, gestor)
POST   /api/v1/usuarios                    # Criar usuário (admin, gestor; só admin cria admin/gestor)
GET    /api/v1/usuarios/{id}               # Detalhes de usuário (admin, gestor)
PUT    /api/v1/usuarios/{id}               # Atualizar usuário; não aceita o próprio id (admin, gestor)
DELETE /api/v1/usuarios/{id}               # Exclusão lógica (admin, gestor)
POST   /api/v1/usuarios/{id}/mfa/setup     # Gera segredo para o usuário (admin, gestor)
POST   /api/v1/usuarios/{id}/mfa/enable    # Define o segredo do usuário; também /habilitar (admin, gestor)
DELETE /api/v1/usuarios/{id}/mfa           # Reset do MFA; também POST /desabilitar (admin, gestor)
```
Gestor não age sobre contas `admin`/`gestor`. Toda mudança de credencial feita aqui encerra as sessões do usuário afetado.

### 🏠 Imóveis & Cômodos
```http
GET    /api/v1/imoveis                     # Listar imóveis; ?com_endereco=true
POST   /api/v1/imoveis                     # Criar imóvel com endereço e geocoding (admin, gestor)
GET    /api/v1/imoveis/{id}                # Detalhes do imóvel
PUT    /api/v1/imoveis/{id}                # Atualizar imóvel e endereço (admin, gestor)
DELETE /api/v1/imoveis/{id}                # Excluir imóvel, soft delete (admin, gestor)
GET    /api/v1/imoveis/{id}/endereco       # Consultar endereço
POST   /api/v1/imoveis/{id}/endereco       # Salvar endereço com geocoding; também PUT/PATCH (admin, gestor)
GET    /api/v1/imoveis/{id}/comodos        # Listar cômodos
POST   /api/v1/imoveis/{id}/comodos        # Adicionar cômodo (admin, gestor)
PUT    /api/v1/imoveis/{id}/comodos/{cid}  # Atualizar cômodo (admin, gestor)
DELETE /api/v1/imoveis/{id}/comodos/{cid}  # Excluir cômodo (admin, gestor)
```

### 📄 Contratos & Agendamentos
```http
GET    /api/v1/contratos                   # Listar contratos
POST   /api/v1/contratos                   # Criar contrato de locação (admin, gestor)
GET    /api/v1/contratos/{id}              # Detalhes do contrato
PATCH  /api/v1/contratos/{id}/encerrar     # Encerrar e liberar o imóvel; também POST (admin, gestor)
PATCH  /api/v1/contratos/{id}/cancelar     # Cancelar e liberar o imóvel; também POST (admin, gestor)
GET    /api/v1/contratos/{id}/agendamentos # Agendamentos do contrato (exceto locatário)
POST   /api/v1/contratos/{id}/agendamentos # Agendar vistoria (admin, gestor)
PUT    /api/v1/agendamentos/{id}           # Atualizar agendamento (admin, gestor)
DELETE /api/v1/agendamentos/{id}           # Cancelar/excluir agendamento (admin, gestor)
```

### 📋 Checklists, Fotos & Laudos
```http
GET    /api/v1/itens-vistoria              # Catálogo de itens inspecionáveis
GET    /api/v1/contratos/{id}/checklists   # Listar checklists do contrato
POST   /api/v1/contratos/{id}/checklists   # Iniciar vistoria; vistoriador_id com perfil vistoriador, contrato ativo (admin, gestor)
GET    /api/v1/checklists/{id}             # Detalhes do checklist
POST   /api/v1/checklists/{id}/itens       # Adicionar item (vistoriador do checklist, admin)
PUT    /api/v1/checklists/{id}/itens/{iid} # Atualizar estado/observação do item (vistoriador do checklist, admin)
POST   /api/v1/checklists/{id}/itens/{iid}/fotos # Upload da foto, multipart campo "foto" (vistoriador do checklist, admin)
DELETE /api/v1/checklists/{id}/itens/{iid}/fotos/{fid} # Excluir foto (vistoriador do checklist, admin)
PATCH  /api/v1/checklists/{id}/submeter    # Submeter vistoria (vistoriador do checklist, admin)
PATCH  /api/v1/checklists/{id}/enviar-para-aceite # Enviar para aceite (admin, gestor)
PATCH  /api/v1/checklists/{id}/aceitar     # Aceite formal (locatário do contrato, admin, gestor; nunca o vistoriador)
PATCH  /api/v1/checklists/{id}/rejeitar    # Rejeição com motivo (mesma regra do aceite)
GET    /api/v1/checklists/{id}/download    # Laudo em PDF; também /pdf e /download-pdf
```

### 🛠️ Problemas & Linha do Tempo
```http
GET    /api/v1/contratos/{id}/problemas    # Listar problemas (admin, gestor, locatário do contrato)
POST   /api/v1/contratos/{id}/problemas    # Registrar ocorrência, JSON ou multipart com foto (admin, gestor, locatário do contrato)
GET    /api/v1/problemas/{id}              # Detalhes da ocorrência (admin, gestor, locatário do contrato)
PATCH  /api/v1/problemas/{id}/status       # Atualizar status (admin, gestor)
GET    /api/v1/problemas/{id}/atualizacoes # Linha do tempo (admin, gestor, locatário do contrato)
POST   /api/v1/problemas/{id}/atualizacoes # Adicionar atualização com foto (admin, gestor)
```

### 📊 Dashboard, Logs & Sistema
```http
GET    /api/v1/dashboard                   # Métricas consolidadas em tempo real
GET    /api/v1/logs                        # Logs de auditoria, com filtros e paginação (admin, gestor)
GET    /api/v1/health                      # Health check da API (público)
GET    /api/v1/uploads/{filename}          # Fotos enviadas (público, nome aleatório)
```

### ⚙️ Administração (seed)
Desabilitadas (`404`) sem `SEED_SECRET`. Exigem o header `X-Seed-Secret` e, com o banco já populado, também token de `admin`.
```http
POST   /api/v1/admin/seed                  # Carga de dados; force=true e mode=refresh_data exigem SEED_ALLOW_DESTRUCTIVE=true
GET    /api/v1/admin/data/status           # Totais do banco, sem alterar dados
POST   /api/v1/admin/refresh-data          # Recria os dados de demonstração; exige SEED_ALLOW_DESTRUCTIVE=true
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
# Versões exatas e hashes conferidos (mesmo conjunto do Render, do Docker e do CI)
pip install --require-hashes -r requirements.lock
# Para rodar os testes
pip install -r requirements-test.txt
```

Para adicionar ou mudar uma dependência, edite `requirements.txt` e regenere o lockfile com o comando do cabeçalho de `requirements.lock` (usa o [`uv`](https://docs.astral.sh/uv/)). O teste `test_lockfile_coerente_com_requirements` falha se os dois arquivos divergirem.

### 4. Configurar Variáveis de Ambiente (`.env`)
Crie um arquivo `.env` na raiz do projeto:
```env
# Sem APP_ENV, vale a regra de produção: a API não sobe sem JWT_SECRET forte.
# Em desenvolvimento, APP_ENV=development dispensa o JWT_SECRET (gera um aleatório por execução).
APP_ENV=development
# Obrigatório em produção, 32+ caracteres. Gere com:
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_SECRET=
# Docker Compose: obrigatório (sem valor padrão)
POSTGRES_PASSWORD=
# Origens do front, separadas por vírgula (ex.: https://onecheck-web.onrender.com).
# Sem valor: em produção nenhum navegador em outra origem chama a API; em desenvolvimento, todas
# CORS_ORIGINS=
# /docs, /redoc e /openapi.json: padrão ligado só em desenvolvimento
# DOCS_ENABLED=false
# Opcional. Vazio = rotas /admin/* desabilitadas. Com banco já populado,
# as rotas também exigem token de admin (Authorization: Bearer ...)
# Com valor, precisa ter 32+ caracteres fora de desenvolvimento
SEED_SECRET=
# Necessário para /admin/seed com force=true e para /admin/refresh-data (apagam dados)
# SEED_ALLOW_DESTRUCTIVE=true
# DATABASE_URL=postgresql://usuario:senha@localhost:5432/onecheck
# Validade dos tokens (padrões abaixo)
# JWT_ACCESS_MINUTES=60
# JWT_REFRESH_DAYS=30
# Limite de tentativas falhas de login/MFA/reautenticação (padrões abaixo)
# RATE_LIMIT_FALHAS_CONTA=5
# RATE_LIMIT_FALHAS_IP=20
# RATE_LIMIT_JANELA_MIN=15
# Tamanho máximo do corpo: uploads (MB) e demais requisições, como JSON (KB)
# MAX_UPLOAD_MB=10
# MAX_BODY_KB=1024
```

No Render, defina `CORS_ORIGINS` com a URL do front (o `render.yaml` deixa o valor para o painel).

### Dados de demonstração (seed)
- Em `APP_ENV=development`, o `start.sh` popula o banco vazio com as contas `@onecheck.local` e credenciais fixas, exibidas pelo `python scripts/seed.py`.
- Fora de desenvolvimento não há seed automático. O primeiro carregamento é feito por `POST /api/v1/admin/seed` (com `SEED_SECRET`), que gera senhas aleatórias, devolvidas uma única vez na resposta; os perfis com MFA configuram o autenticador no primeiro login.
- Bancos criados pelo seed antigo (senhas e segredo TOTP públicos) geram um alerta `SEGURANÇA:` no log ao iniciar. Para corrigir, aponte `DATABASE_URL` para o banco e rode `python scripts/rotacionar_credenciais_demo.py` (lista as contas) e depois com `--aplicar` (troca a senha, reseta o MFA e revoga as sessões).

### 5. Iniciar a API
```bash
uvicorn app.main:app --reload
```
A API estará rodando em: `http://localhost:8000`  
Documentação Swagger interativa (desenvolvimento ou `DOCS_ENABLED=true`): `http://localhost:8000/docs`

---

## 🧪 Executando os Testes Automatizados

A suíte cobre os fluxos de negócio e as correções de segurança com **733 testes automatizados** e **94% de cobertura**:

```bash
# Executar todos os testes
.venv/bin/pytest

# Executar com relatório detalhado de cobertura linha por linha
.venv/bin/pytest --cov=app --cov-report=term-missing

# Executar testes em modo verboso
.venv/bin/pytest -v

# Contra PostgreSQL (como no CI)
TEST_DATABASE_URL=postgresql://usuario:senha@localhost:5432/onecheck_test .venv/bin/pytest
```

---

## 📁 Estrutura do Repositório

```
├── app/
│   ├── auth.py                  # JWT, Bcrypt, TOTP MFA e revogação de sessões
│   ├── cabecalhos.py            # Cabeçalhos de segurança em todas as respostas
│   ├── config.py                # Configurações e variáveis de ambiente
│   ├── database.py              # Conexão SQLAlchemy e migração incremental
│   ├── deps.py                  # Autenticação, roles (RBAC) e regras de acesso por recurso
│   ├── geocoding.py             # Módulo de integração OpenStreetMap e ViaCEP
│   ├── limite_corpo.py          # Limite de tamanho do corpo antes do roteamento
│   ├── main.py                  # Inicialização da aplicação FastAPI, CORS e middlewares
│   ├── models.py                # Modelagem ORM relacional do banco de dados
│   ├── notification_service.py  # Serviço de notificações para admins e locatários
│   ├── pdf_generator.py         # Motor de renderização de Laudos em PDF (Pure Python)
│   ├── rate_limit.py            # Limite de tentativas falhas por conta e por IP
│   ├── schemas.py               # Schemas Pydantic, DTOs e envelopes de resposta
│   ├── seed_service.py          # Carga de dados de demonstração e rotação de credenciais
│   ├── serializers.py           # Serializadores de dados e registro de auditoria
│   ├── uploads.py               # Validação e gravação segura de imagens
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
├── docs/
│   ├── architecture/            # Arquitetura e fronteiras de confiança
│   └── security/                # Auditoria, modelo de ameaças e relatórios de correção
├── scripts/                     # Seed, rotação de credenciais e utilitários de carga
├── requirements.txt             # Dependências diretas
├── requirements.lock            # Todas as dependências, com hash (instalação)
└── tests/
    ├── conftest.py              # Fixtures globais do pytest e clientes de teste
    ├── unit/                    # Testes unitários (auth, config, pdf, geocoding, schemas, serializers)
    └── integration/             # Testes de integração de todas as rotas da API
```
