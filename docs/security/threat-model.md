# Modelo de Ameaças — OneCheck API

_Última atualização: 2026-11-07 ([auditoria diff](relatorio-2026-11-07.md) sobre `ed36a41`: status HTTP dos erros (ADR-0003), SEC-035 a SEC-037 só informativos). Antes: 2026-11-02 ([auditoria diff](relatorio-2026-11-02.md) sobre `d0b5f35`: SEC-017 a SEC-020 abertos; auditoria completa de 2026-10-25 sobre `f081c60`; SEC-001 a SEC-016 corrigidos em seguida, ver correções [001–003](correcao-sec-001-002-003-2026-10-25.md), [004–005](correcao-sec-004-005-2026-10-25.md), [006–007](correcao-sec-006-007-2026-10-25.md), [008, 009 e 016](correcao-sec-008-009-016-2026-10-26.md), [010 e 013](correcao-sec-010-013-2026-10-26.md), [011 e 012](correcao-sec-011-012-2026-10-30.md) e [014 e 015](correcao-sec-014-015-2026-10-30.md))_

## 1. Visão geral
API REST (FastAPI + SQLAlchemy) para vistorias de locação: cadastro de imóveis e contratos, checklists de vistoria com fotos, aceite pelo locatário, registro e acompanhamento de problemas e geração de PDF do laudo.
- **Clientes:** front web e mobile.
- **Deploy:** Render (plano free: 1 instância, Postgres gerenciado, TLS terminado no proxy) e Docker Compose local.
- **Repositório:** **público** no GitHub.

## 2. Ativos
| Ativo | Tipo | Pilar mais crítico | Onde fica |
|---|---|---|---|
| Credenciais (hash bcrypt, segredo TOTP, refresh tokens) | Dado | Autenticidade | `usuarios`, `auth_refresh_tokens` |
| `JWT_SECRET` e `SEED_SECRET` | Chave | Confidencialidade | variáveis de ambiente (Render / `.env`) |
| Dados pessoais (nome, e-mail, CPF) | Dado | Confidencialidade (LGPD) | `usuarios` |
| Endereços de imóveis e coordenadas | Dado | Confidencialidade | `enderecos` |
| Contratos (valor, locatário, datas) | Dado | Integridade | `contratos` |
| Laudos, fotos e aceites | Evidência | Integridade, Não-repúdio | `checklists`, `checklist_itens`, `aceite_checklists`, `UPLOAD_DIR` |
| Trilha de auditoria | Dado | Não-repúdio | `log_operacao` |
| Disponibilidade da API | Serviço | Disponibilidade | processo uvicorn (1 worker) |

## 3. Atores
| Ator | Confiança | Acesso |
|---|---|---|
| Anônimo / atacante externo | Nenhuma | `/auth/login`, `/auth/mfa/*` com temp token, `/health`, `/uploads/{arquivo}`, `/docs` (só com `DOCS_ENABLED`), `/admin/*` (com `SEED_SECRET`) |
| Locatário | Baixa | os próprios contratos, problemas, aceites; uploads de foto de problema |
| Visualizador | Baixa | leitura de checklists e PDFs (global, por decisão a confirmar) |
| Vistoriador | Média | checklists atribuídos (escrita), leitura de contratos/imóveis vinculados |
| Gestor | Alta | gestão de imóveis, contratos, usuários não privilegiados, logs |
| Administrador | Total | tudo, inclusive contas admin/gestor e `/admin/*` |
| Mantenedor / CI | Alta | repositório, GitHub Actions, painel do Render |
| Serviços externos | Baixa | ViaCEP e Nominatim (respostas consumidas pela API) |

## 4. Diagrama de fluxo de dados
```mermaid
flowchart LR
  A[Anônimo / Atacante] -->|HTTPS| P
  U[Usuários: locatário, vistoriador, gestor, admin] -->|HTTPS + Bearer JWT| P
  subgraph Render["Fronteira: provedor (Render)"]
    P[Proxy TLS do Render] -->|HTTP + X-Forwarded-For| API
    subgraph App["Fronteira: processo da API"]
      API[FastAPI / uvicorn<br/>auth, RBAC, rate limit em memória]
    end
    API -->|SQL| DB[(Postgres<br/>usuarios, contratos, laudos, logs)]
    API -->|arquivos| FS[(UPLOAD_DIR<br/>fotos)]
  end
  API -->|HTTPS| VIA[ViaCEP]
  API -->|HTTPS| NOM[Nominatim]
  GH[GitHub público<br/>código e seed] -->|build| Render
  CI[GitHub Actions] -->|testes| GH
```

## 5. Fronteiras de confiança
| Fronteira | Fluxos que cruzam | Controles |
|---|---|---|
| Internet ↔ API | todas as rotas | TLS no proxy; JWT HS256 com `type` verificado (`app/deps.py:19`); RBAC `require_roles`; rate limit de auth (`app/rate_limit.py`); validação de upload (`app/uploads.py`); limite de corpo antes do roteamento (`app/limite_corpo.py`); CORS só para as origens configuradas, sem credenciais, e cabeçalhos de segurança (`app/main.py`, `app/cabecalhos.py`) |
| API ↔ Banco | ORM SQLAlchemy | consultas parametrizadas; DDL estático (`app/database.py`). **Falta:** credencial dedicada de menor privilégio |
| API ↔ Disco (uploads) | gravação e download de fotos | nome aleatório, assinatura conferida antes do Pillow, parser restrito a JPEG/PNG/WebP, `caminho_seguro`, `nosniff` + CSP. **Falta:** autenticação no download |
| API ↔ serviços externos | CEP e geocoding | URL fixa HTTPS, CEP só com dígitos, timeout 5 s |
| Repositório público ↔ deploy | build e start | seed automático só em desenvolvimento; fora dele, credenciais aleatórias (SEC-001). nenhum banco versionado (SEC-009). **Falta:** rotacionar contas antigas em produção |
| Container ↔ host | execução | usuário `app` sem privilégio, código só leitura, sem compilador na imagem; CI com token só leitura e actions fixadas por SHA (SEC-008) |

## 6. Ameaças (STRIDE por elemento)
| ID | Elemento | STRIDE | Ameaça | Pilar | Mitigação existente | Status | Achado |
|---|---|---|---|---|---|---|---|
| T-01 | Login | S | Entrar como admin com as credenciais públicas do seed | Autenticidade | seed sem credenciais fixas fora de dev; alerta e script de rotação para contas antigas (`app/seed_service.py`) | Mitigada no código (rotação em produção pendente) | SEC-001 |
| T-02 | Login / MFA | S | Força bruta de senha e TOTP; credential stuffing com senhas comuns | Autenticidade | `Tentativas` por conta e IP (`auth_router.py:47-58`); senhas novas com 10+ caracteres, até 72 bytes e sem padrões comuns (`app/senhas.py`) | Mitigada (por processo; senhas antigas seguem valendo) | SEC-011 |
| T-03 | MFA | S | Login só com senha usando token de setup | Autenticidade | tipos `mfa` × `mfa_setup` (N1) | Mitigada | — |
| T-04 | JWT | S | Forjar token com segredo padrão | Autenticidade | `JWT_SECRET` obrigatório e forte fora de dev (`config.py`) | Mitigada | — |
| T-05 | Sessões | S | Token roubado continua válido após troca de senha/reset de MFA | Autenticidade | `token_version` nos JWT + refresh tokens apagados (`encerrar_sessoes`, `app/auth.py`) | Mitigada | SEC-005 |
| T-06 | Login | I | Enumerar e-mails pelo tempo de resposta | Confidencialidade | mensagem genérica; bcrypt contra hash fictício de mesmo custo quando a conta não existe (`conferir_credenciais`, `app/auth.py`) | Mitigada | SEC-013 |
| T-07 | Usuários | E | Gestor se promove ou gerencia admins | Autorização | `_assert_pode_gerenciar` / `_assert_pode_atribuir` (N4) | Mitigada | — |
| T-08 | Checklists | E/T | Locatário cria e aprova a própria vistoria | Integridade | criação só admin/gestor; separação de deveres (N3) | Mitigada | — |
| T-09 | Contratos / Imóveis | I | Vistoriador lê qualquer contrato/imóvel pelo ID | Confidencialidade | `assert_acesso_contrato` / `assert_acesso_imovel` (`app/deps.py`) | Mitigada (visualizador com leitura global, a decidir) | SEC-004 |
| T-10 | Problemas | I | BOLA por ID | Confidencialidade | `assert_acesso_problemas` (item 6) | Mitigada | — |
| T-11 | Usuários | I | Listagem de usuários com CPF para qualquer perfil | Confidencialidade (LGPD) | restrito a admin/gestor (item 2); CPF mascarado fora de `/me` e do detalhe (`app/cpf.py`); retenção de logs e tokens (`app/retencao.py`) | Mitigada (CPF em texto no banco) | SEC-014 |
| T-12 | Uploads | T/E | Arquivo malicioso explora o decoder de imagem | Integridade | Pillow 13; assinatura antes do parser; `formats` restrito; limite de pixels (`app/uploads.py`) | Mitigada | SEC-002 |
| T-13 | Uploads | T | XSS armazenado via HTML/SVG servido pela API | Integridade | validação de conteúdo + `nosniff` + CSP (N7) | Mitigada | — |
| T-14 | Uploads / download | I | Fotos de vistoria acessíveis sem login | Confidencialidade (LGPD) | nomes aleatórios de 128 bits | Aceita? (decisão pendente) | — |
| T-15 | API | D | Corpo multipart gigante processado antes da auth | Disponibilidade | `LimiteCorpoMiddleware`; formulário lido após a auth | Mitigada | SEC-003 |
| T-16 | API | D | Limite de tentativas usado para bloquear contas de terceiros | Disponibilidade | janela de 15 min | Aceita (custo do T-02) | — |
| T-17 | Problemas | T | Locatário abre problema já "fechado" | Integridade | o problema nasce `aberto`; outro status no corpo dá `422` (`contratos.py`) | Mitigada | SEC-012 |
| T-24 | Dashboard | I | Qualquer perfil vê totais de toda a operação | Confidencialidade | mesmo recorte das listagens por perfil; `null` no que o perfil não acessa (`dashboard.py`) | Mitigada | SEC-012 |
| T-18 | Auditoria | R | Ações sem IP e sem os campos alterados | Não-repúdio | `log_operacao` em todas as escritas, com IP de origem (`app/auditoria.py`) e nomes dos campos alterados | Mitigada (log não é append-only) | SEC-010 |
| T-19 | MFA por admin | R | Admin define o TOTP de outro usuário e age em nome dele | Não-repúdio | sem setup de MFA para terceiros; o segredo é gerado no login do próprio usuário; admin só exige ou reseta (`usuarios.py`) | Mitigada (admin ainda define a senha de outro usuário) | SEC-015 |
| T-20 | Dependências | T/E | CVE em pacote (Pillow, python-multipart, python-jose) | Integridade | PyJWT no lugar do python-jose; `requirements.lock` com hashes, instalado com `--require-hashes`; `pip-audit` no CI | Mitigada | SEC-006 |
| T-21 | Repositório | I | Banco e seed publicados no GitHub | Confidencialidade | `onecheck.db` fora do índice (o histórico só tem dados de seed); credenciais do seed só em desenvolvimento | Mitigada (falta a rotação em produção) | SEC-001, SEC-009 |
| T-22 | Navegador | I | Site de terceiro lê respostas da API (CORS `*`) | Confidencialidade | auth por Bearer (sem cookie); CORS só para `CORS_ORIGINS`, sem credenciais; `/docs` desligado em produção; `no-store`, `nosniff`, HSTS | Mitigada (depende de `CORS_ORIGINS` no Render) | SEC-007 |
| T-23 | Container / CI | E | Código executado como root; action repontada | Integridade | `USER app`, `--only-binary`, `permissions: contents: read`, actions por SHA; compose com `cap_drop: ALL` e `no-new-privileges` | Mitigada | SEC-008 |
| T-25 | Proxy / IP de origem | S/R | Cliente forja o `X-Forwarded-For` para escapar do limite por IP e gravar IP falso na auditoria | Não-repúdio, Disponibilidade | limite por conta independe do IP; `FORWARDED_ALLOW_IPS=*` usa o primeiro item do cabeçalho (`render.yaml:18`) | **Aberta** (a confirmar no Render) | SEC-017 |
| T-26 | Auditoria (`GET /logs`) | I | Gestor consulta IP e padrão de acesso de todas as contas, inclusive admins | Confidencialidade (LGPD) | rota restrita a admin/gestor; retenção de `LOG_RETENCAO_DIAS` | **Aberta** | SEC-018, SEC-019 |
| T-27 | Monitoramento | R | Falhas de login, MFA e acesso negado invisíveis nos logs por responderem 200 | Não-repúdio | status de erro em todo `fail()` e guarda na suíte (ADR-0003, `tests/conftest.py`) | Mitigada | — |

Status: **Mitigada** · **Parcial** · **Aberta** · **Aceita**

## 7. Riscos aceitos
_Seção mantida manualmente pela equipe — preservar entre execuções._
| ID | Risco | Justificativa | Responsável | Revisar em |
|---|---|---|---|---|

## 8. Premissas
- TLS é terminado pelo proxy do Render, e o banco gerenciado não fica exposto à internet.
- O deploy roda com **uma instância e um worker**; o limite de tentativas em memória depende disso.
- O proxy do Render sobrescreve o `X-Forwarded-For` (não verificado). Com `FORWARDED_ALLOW_IPS=*`, o uvicorn usa o **primeiro** item do cabeçalho; se o proxy só acrescentar, o cliente escolhe o IP (T-25, SEC-017).
- A autenticação do front é só por header Bearer; não há cookies de sessão.
- O perfil `visualizador` tem leitura global de checklists e PDFs por decisão de negócio (a confirmar).
