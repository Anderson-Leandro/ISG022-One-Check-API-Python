# Relatório de Segurança — OneCheck API

- **Data:** 2026-10-25
- **Modo:** full · **Commit:** `f081c60` (branch `dev`)
- **Escopo:** repositório inteiro: `app/`, `scripts/`, `start.sh`/`start.ps1`, `Dockerfile`, `render.yaml`, `.github/workflows/`, dependências, histórico git, arquivos versionados. `docker-compose.yml` não é versionado, mas foi lido.
- **Stack:** Python 3.12, FastAPI 0.115.6 (Starlette 0.41.3), SQLAlchemy 2.0, PostgreSQL 16 / SQLite, python-jose (JWT HS256), bcrypt, pyotp, Pillow. Deploy no Render (repositório **público**) e Docker Compose.
- **Ferramentas:** revisão manual guiada (Claude) + semgrep 1.95.0 · bandit 1.7.10 · gitleaks v8.21.2 (working tree e histórico) · trivy 0.56.2 (fs + config) · osv-scanner v1.9.1. **Todos executaram sem falha.**

> **Atualização:** SEC-001 a SEC-009 e SEC-016 foram corrigidos depois desta auditoria. Ver as correções [SEC-001 a 003](correcao-sec-001-002-003-2026-10-25.md), [SEC-004 e 005](correcao-sec-004-005-2026-10-25.md), [SEC-006 e 007](correcao-sec-006-007-2026-10-25.md) e [SEC-008, 009 e 016](correcao-sec-008-009-016-2026-10-26.md). As contas do seed antigo em produção ainda precisam ser rotacionadas.

Esta auditoria vem depois das correções N1–N8 e dos itens 1, 2, 3 e 6 do `PENDENCIAS_API.md` (commits `0e164b8`, `8e4d12d`, `648518e` e `f081c60`). Os pontos já corrigidos foram conferidos e aparecem em **Pontos positivos**.

## 1. Sumário executivo
Falta resolver um problema crítico, que **independe do código das rotas**. O `start.sh` roda o seed em todo start. Em banco vazio, o seed cria `admin@onecheck.local` com a senha e o segredo MFA que estão no repositório público. Qualquer pessoa entra como admin em um ambiente assim (SEC-001). **A primeira ação é verificar o ambiente de produção** e tirar o seed do start.

Os outros dois riscos altos estão nas dependências e na forma de uso:
- **Pillow 11.1.0:** tem CVEs de execução de código, e os uploads abrem o arquivo com todos os formatos habilitados (SEC-002).
- **Corpo das requisições:** a API processa uploads multipart de qualquer tamanho **antes** de checar o token, o que permite derrubá-la sem conta (SEC-003).

Os demais achados são de autorização por ID (SEC-004), sessões que sobrevivem à troca de senha (SEC-005) e hardening.

| Crítica | Alta | Média | Baixa | Info |
|---|---|---|---|---|
| 1 | 2 | 3 | 9 | 1 |

**Scanners:**
- **Código e configuração:** 18 resultados brutos. 8 foram confirmados, agrupados nos achados SEC-001 e SEC-008. Os outros 10 são falsos positivos descartados. Nenhum foi suprimido (não existe `.security-audit-ignore.json`).
- **Dependências:** 6 pacotes com 75 vulnerabilidades. A alcançabilidade de cada um está analisada na seção 6.

**Falsos positivos descartados (10):**
- bandit B310 e semgrep `dynamic-urllib` em `app/geocoding.py:25,56`: as URLs são fixas, `https://`, e o CEP passa por um filtro que só deixa dígitos.
- bandit B310 e semgrep em `scripts/populate_and_test.py:32`: script manual, a URL vem do operador.
- bandit B110 em `app/routers/dashboard.py:64,70`: `except: pass` só ignora um filtro de data inválido em `/logs`, rota restrita a admin/gestor; não libera acesso.
- semgrep `logger-credential` em `app/config.py:33`: o log contém só a mensagem, não o segredo.
- gitleaks em `.env:1`: o arquivo está no `.gitignore`, não é versionado e não aparece no histórico.

## 2. Pilares de segurança
| Pilar | Achados | Avaliação |
|---|---|---|
| Confidencialidade | SEC-001, 002, 004, 007, 009, 012, 013, 014 | **crítico** enquanto as credenciais do seed puderem existir em produção; o restante é vazamento limitado |
| Integridade | SEC-001, 002, 006, 008, 012, 016 | atenção: o parser de imagem vulnerável recebe arquivos de usuários |
| Disponibilidade | SEC-002, 003 | **atenção**: DoS anônimo pelo corpo multipart |
| Autenticidade | SEC-001, 005, 011, 015 | crítico (SEC-001); o fluxo de MFA e JWT em si ficou sólido após N1, N5, N6 e N8 |
| Não-repúdio / Auditoria | SEC-010, 015 | atenção: o `security-baseline.md` afirma que o IP é registrado, mas ele nunca é gravado |

## 3. Princípios de design
| Princípio | Achados | Avaliação |
|---|---|---|
| Menor privilégio | SEC-004, 008, 014 | container como root; leitura por ID mais ampla que a listagem |
| Secure by default | SEC-001, 007, 011 | o seed com credenciais públicas roda por padrão; CORS `*` |
| Fail secure | SEC-003, 005, 013 | o corpo é processado antes da autenticação; a sessão sobrevive à troca de credencial |
| Mediação completa | SEC-004, 012 | lista e acesso por ID com regras diferentes em contratos e imóveis |
| Defesa em profundidade | SEC-002, 003, 006 | sem limite de corpo; Pillow sem restrição de formato |
| Superfície de ataque mínima | SEC-002, 007, 009, 016 | `/docs` público; banco e código antigo versionados |
| Separação de privilégios | SEC-015 | o admin consegue definir o MFA de outro usuário |

## 4. STRIDE
| Categoria | Ameaças identificadas | Mitigadas | Achados |
|---|---|---|---|
| S — Spoofing | 6 (T-01 a T-06) | 3 | SEC-001, 005, 011, 013 |
| T — Tampering | 4 (T-08, 12, 13, 17) | 2 | SEC-002, 012 |
| R — Repudiation | 2 (T-18, 19) | 0 | SEC-010, 015 |
| I — Information disclosure | 6 (T-09, 10, 11, 14, 21, 22) | 1 | SEC-004, 007, 009, 014 |
| D — Denial of service | 2 (T-15, 16) | 0 (T-16 aceita) | SEC-003 |
| E — Elevation of privilege | 4 (T-07, 08, 20, 23) | 2 | SEC-002, 008 |

Detalhes no [modelo de ameaças](threat-model.md).

## 5. Achados

### SEC-001 — Seed automático cria admin com senha e segredo MFA públicos · Crítica
| | |
|---|---|
| **Pilar** | Autenticidade, Confidencialidade, Integridade |
| **Princípio violado** | Secure by default |
| **STRIDE** | S, E |
| **CWE / OWASP** | CWE-798 / A07:2021 |
| **Local** | `start.sh:8`, `scripts/seed.py:25,36`, `app/seed_service.py:25,290,364` |
| **Fonte** | Claude, bandit (B105) |

**Evidência**
```bash
# start.sh:8 — roda em todo start do container (Dockerfile CMD e render.yaml startCommand)
python scripts/seed.py 2>/dev/null || true
```
```python
# scripts/seed.py
MFA_SECRET = "JBSW****"                    # :25, o mesmo para todos os usuários com MFA
senha_hash=hash_password("admi****"),       # :36, admin@onecheck.local
```
**Cenário de exploração:**
1. Um ambiente sobe com banco vazio: o primeiro deploy no Render, um banco recriado ou um `docker compose up` novo.
2. O seed cria o admin, o gestor e os vistoriadores com as senhas do código e o mesmo `mfa_secret`.
3. O atacante lê o repositório público, faz `POST /auth/login`, gera o TOTP com o segredo e chama `/auth/mfa/verify`. Sai com o token de admin.

O `/admin/seed` (agora protegido por N2) também devolve as senhas e o segredo no corpo da resposta.

**Impacto:** tomada total da API por qualquer pessoa na internet. **A confirmar em produção:** se as contas de seed ainda existem com a senha original. Não testei contra o ambiente real.

**Correção recomendada:**
- **Imediato:** no Render, verificar se `admin@onecheck.local` e as demais contas `@onecheck.local` existem. Se existirem: trocar as senhas, resetar o MFA (o usuário reconfigura no próximo login), revogar os refresh tokens e revisar `log_operacao` em busca de logins inesperados.
- **No código:** remover a linha 8 do `start.sh`, porque o bootstrap já existe via `/admin/seed` com `SEED_SECRET`. Para produção, gerar a senha inicial com `secrets.token_urlsafe` e exibi-la uma única vez, sem definir `mfa_secret`.

### SEC-002 — Pillow 11.1.0 com CVEs críticas e `Image.open` aceita qualquer formato · Alta
| | |
|---|---|
| **Pilar** | Integridade, Disponibilidade |
| **Princípio violado** | Superfície de ataque mínima |
| **STRIDE** | E, D |
| **CWE / OWASP** | CWE-1395 / A06:2021 |
| **Local** | `app/uploads.py:25`, `requirements.txt:11` |
| **Fonte** | Claude, trivy, osv-scanner |

**Evidência**
```python
with Image.open(io.BytesIO(content)) as im:   # todos os plugins de formato habilitados
    formato = im.format
    im.verify()
```
**Cenário de exploração:** um locatário envia como foto de problema um PSD, TIFF, FITS ou JPEG2000 malicioso. O `Image.open` identifica e decodifica o arquivo com o plugin correspondente **antes** de a checagem JPEG/PNG/WebP recusá-lo. Exemplos de CVEs da 11.1.0: CVE-2026-42311 (execução de código via PSD), CVE-2026-25990 (escrita fora dos limites em PSD), CVE-2026-59197 (heap) e 5 críticas corrigidas na 13.0.0.

**Impacto:** execução de código ou queda da API por qualquer usuário que possa enviar foto. Vale anotar que a validação criada em N7 é o ponto em que o Pillow passou a ler arquivos de usuários.

**Correção recomendada:**
```python
# requirements.txt: pillow>=13.0.0
with Image.open(io.BytesIO(content), formats=["JPEG", "PNG", "WEBP"]) as im:
```
Conferir também a assinatura (magic bytes) antes de abrir.

### SEC-003 — DoS anônimo: multipart processado antes da autenticação · Alta
| | |
|---|---|
| **Pilar** | Disponibilidade |
| **Princípio violado** | Fail secure, defesa em profundidade |
| **STRIDE** | D |
| **CWE / OWASP** | CWE-770 / API4:2023 |
| **Local** | `app/routers/checklists.py:217,244`, `requirements.txt:1,8` |
| **Fonte** | Claude (verificado em execução), trivy, osv-scanner |

**Evidência**
```python
foto: UploadFile = File(...),        # :217 — o FastAPI lê e grava o corpo antes de resolver Depends(get_current_user)
content = await foto.read()          # :244 — o arquivo inteiro vai para a memória
```
Verificado com o TestClient: um `POST` anônimo de 5 MB para `/checklists/x/itens/y/fotos` passou pelo parser multipart e só então recebeu `401`.

**Cenário de exploração:** sem conta, o atacante envia em paralelo vários corpos multipart grandes (ou com milhares de partes). Isso enche o disco temporário e ocupa o único worker. Somam-se a esse vetor:
- as CVEs de DoS do python-multipart 0.0.20 (CVE-2026-42561, CVE-2026-53539);
- a do Starlette 0.41.3 no `FileResponse` com `Range` (CVE-2025-62727), alcançável no `GET /uploads/...` público. Esta foi identificada manualmente: sem lockfile, os scanners não analisam o Starlette.

**Impacto:** indisponibilidade sem autenticação.

**Correção recomendada:**
- Middleware que recusa `Content-Length` acima de `MAX_UPLOAD_MB` e corta corpos em streaming.
- Limite de corpo também no proxy.
- `python-multipart>=0.0.31` e FastAPI com Starlette `>=0.49.1`.
- Ler o upload em blocos, interrompendo ao passar do limite.

### SEC-004 — Leitura por ID ignora o vínculo do vistoriador · Média
| | |
|---|---|
| **Pilar** | Confidencialidade |
| **Princípio violado** | Mediação completa |
| **STRIDE** | I |
| **CWE / OWASP** | CWE-639 / API1:2023 |
| **Local** | `app/routers/contratos.py:129,209`, `app/routers/imoveis.py:134,210,257` |
| **Fonte** | Claude |

**Evidência**
```python
# contratos.py:129 — só o locatário é restringido; a listagem (:51-58) também filtra o vistoriador
if user.role == "locatario" and ct.locatario_id != user.id:
    raise HTTPException(status_code=403, ...)
```
**Cenário de exploração:** um vistoriador chama `GET /contratos/{id}`, `/contratos/{id}/agendamentos`, `/imoveis/{id}`, `/imoveis/{id}/endereco` e `/imoveis/{id}/comodos` com IDs de contratos em que não atua. Recebe valor do aluguel, id do locatário, datas e endereço.

**Impacto:** vazamento limitado de dados de negócio e de endereço. É o mesmo padrão do item 6, já corrigido em problemas.

**Correção recomendada:** um helper por recurso, aplicado igualmente à lista e ao acesso por ID (como `assert_acesso_problemas`). Definir com o negócio o alcance do perfil `visualizador`, que hoje lê todos os checklists e PDFs.

### SEC-005 — Troca de senha e reset de MFA não revogam sessões · Média
| | |
|---|---|
| **Pilar** | Autenticidade |
| **Princípio violado** | Fail secure |
| **STRIDE** | S |
| **CWE / OWASP** | CWE-613 / A07:2021 |
| **Local** | `app/routers/usuarios.py:76,98,226`, `app/auth.py:80` |
| **Fonte** | Claude |

**Evidência**
```python
user.senha_hash = hash_password(body.nova_senha)   # usuarios.py:98 — os refresh tokens do usuário continuam válidos
```
**Cenário de exploração:** o atacante tem a sessão da vítima. A vítima (ou o admin) troca a senha e reseta o MFA, mas o refresh token do atacante continua emitindo access tokens por até 30 dias.

**Impacto:** a resposta a incidente não corta o acesso do atacante.

**Correção recomendada:**
- Apagar todos os `RefreshToken` do usuário ao trocar a senha, resetar o MFA ou mudar o perfil.
- Incluir no JWT uma versão de credencial (`token_version`) e conferi-la em `get_current_user`.

### SEC-006 — Outras dependências com CVEs e sem lockfile · Média
| | |
|---|---|
| **Pilar** | Integridade |
| **Princípio violado** | Defesa em profundidade |
| **STRIDE** | T |
| **CWE / OWASP** | CWE-1104 / A06:2021 |
| **Local** | `requirements.txt:6,10,12` |
| **Fonte** | trivy, osv-scanner, Claude |

**Evidência:** `python-jose[cryptography]==3.3.0`, `cryptography==44.0.0`, `python-dotenv==1.0.1`, `pytest==8.3.4`. Não há lockfile.

**Cenário de exploração:**
- As CVEs críticas do python-jose (CVE-2024-33663, CVE-2026-85394) exigem chave assimétrica. A API usa só HS256 com `algorithms=[...]` fixo (`app/auth.py:59`), então **não são alcançáveis hoje**.
- As do cryptography (PKCS#7, curvas SECT, X.509) também não estão no caminho de uso.
- Sem lockfile, as dependências transitivas (Starlette, uvicorn, h11…) ficam fora dos scanners.

**Impacto:** sem exploração no uso atual, mas com risco de regressão silenciosa.

**Correção recomendada:**
- Migrar para PyJWT.
- Atualizar `cryptography>=50`, `python-dotenv>=1.2.2` e `pytest`.
- Gerar um lockfile com hashes e rodar SCA no CI.

### SEC-007 — Hardening HTTP: CORS `*` com credenciais, `/docs` público, sem cabeçalhos · Baixa
| | |
|---|---|
| **Pilar** | Confidencialidade |
| **Princípio violado** | Secure by default |
| **STRIDE** | I |
| **CWE / OWASP** | CWE-942 / API8:2023 |
| **Local** | `app/main.py:40`, `app/config.py:65`, `render.yaml:30` |
| **Fonte** | Claude |

**Evidência:** `allow_origins=["*"]` com `allow_credentials=True`; `FastAPI(...)` sem `docs_url=None`.

**Cenário de exploração:** qualquer site lê as respostas da API pelo navegador do usuário. Hoje o efeito é limitado, porque a autenticação usa Bearer. Se algum dia a API passar a usar cookies, isso vira roubo de dados imediato. `/docs` entrega o mapa completo da API.

**Impacto:** baixo hoje.

**Correção recomendada:**
- Lista explícita de origens e `allow_credentials=False`.
- `/docs` e `/openapi.json` desligados em produção.
- HSTS e `Cache-Control: no-store` nas respostas autenticadas.

### SEC-008 — Container como root; CI com actions por tag mutável · Baixa
| | |
|---|---|
| **Pilar** | Integridade |
| **Princípio violado** | Menor privilégio |
| **STRIDE** | E, T |
| **CWE / OWASP** | CWE-250 / A05:2021 |
| **Local** | `Dockerfile:22`, `.github/workflows/tests.yml:34,37` |
| **Fonte** | semgrep, trivy (DS002, DS026) |

**Evidência:** o Dockerfile não define `USER`, e a imagem final mantém `gcc` e as libs de build. O workflow usa `actions/checkout@v4` e `actions/setup-python@v5` e não declara `permissions:`.

**Impacto:** amplifica outras falhas. Uma execução de código como a do SEC-002 roda como root, com compilador disponível.

**Correção recomendada:**
- Build multi-stage e `USER app`.
- No workflow, `permissions: contents: read` e as actions fixadas por SHA.

### SEC-009 — Banco SQLite versionado em repositório público · Baixa
| | |
|---|---|
| **Pilar** | Confidencialidade |
| **Princípio violado** | Superfície de ataque mínima |
| **STRIDE** | I |
| **CWE / OWASP** | CWE-538 / A05:2021 |
| **Local** | `onecheck.db` |
| **Fonte** | Claude (`sensitive-files.txt`) |

**Evidência:** `onecheck.db` está versionado. Verifiquei: hoje tem só os 7 usuários `@onecheck.local` do seed, com hashes e `mfa_secret`. A cópia local está **modificada e não commitada**.

**Impacto:** baixo com o conteúdo atual. Se dados reais forem commitados, ficam no histórico público para sempre.

**Correção recomendada:** `git rm --cached onecheck.db` e incluir o arquivo no `.gitignore`.

### SEC-010 — Trilha de auditoria incompleta · Baixa
| | |
|---|---|
| **Pilar** | Não-repúdio |
| **Princípio violado** | Responsabilização |
| **STRIDE** | R |
| **CWE / OWASP** | CWE-778 / A09:2021 |
| **Local** | `app/serializers.py:230`, `app/routers/usuarios.py:230`, `app/notification_service.py:17` |
| **Fonte** | Claude |

**Evidência**
```python
log_operacao(db, current.id, "update", "usuario", user.id)   # sem o que mudou; o parâmetro ip nunca é passado em app/
```
**Cenário de exploração:** um admin troca a senha ou o perfil de alguém, e o log só diz "update usuario". Nenhum evento tem IP. Ao mesmo tempo, o logger de notificações grava e-mail e corpo da mensagem.

**Impacto:** investigação de incidentes sem base. Há também PII em log de aplicação.

**Correção recomendada:**
- Passar `request.client.host` para o log.
- Registrar os campos alterados, sem valores sensíveis.
- Tirar a PII do logger de notificações.
- Corrigir o `security-baseline.md`, que afirma que o IP é registrado.

### SEC-011 — Política de senha fraca · Baixa
| | |
|---|---|
| **Pilar** | Autenticidade |
| **Princípio violado** | Secure by default |
| **STRIDE** | S |
| **CWE / OWASP** | CWE-521 / A07:2021 |
| **Local** | `app/schemas.py:106` (e `:114`, `:119`, `:126`) |
| **Fonte** | Claude |

**Evidência:** `senha: str = Field(min_length=6)`. Senhas comuns são aceitas, e o bcrypt ignora o que passa de 72 bytes.

**Impacto:** baixo, por causa do rate limit e do MFA nos perfis privilegiados. Os locatários continuam expostos a credential stuffing.

**Correção recomendada:** mínimo de 10–12 caracteres, recusar senhas vazadas ou comuns e limitar a 72 bytes.

### SEC-012 — Regras de negócio sem validação no servidor e dashboard global · Baixa
| | |
|---|---|
| **Pilar** | Integridade, Confidencialidade |
| **Princípio violado** | Mediação completa |
| **STRIDE** | T, I |
| **CWE / OWASP** | CWE-915 / API3:2023 |
| **Local** | `app/routers/contratos.py:429`, `app/routers/dashboard.py:23` |
| **Fonte** | Claude |

**Evidência:** o locatário escolhe o `status` inicial do problema, que pode ser `fechado` (item 9). O `/dashboard` mostra totais globais a qualquer perfil (item 4).

**Impacto:** baixo.

**Correção recomendada:** criar o problema sempre com status `aberto`. No dashboard, aplicar os filtros das listagens ou restringi-lo a admin/gestor.

### SEC-013 — Enumeração de e-mails pelo tempo do login · Baixa
| | |
|---|---|
| **Pilar** | Confidencialidade |
| **Princípio violado** | Fail secure |
| **STRIDE** | I |
| **CWE / OWASP** | CWE-208 / A07:2021 |
| **Local** | `app/routers/auth_router.py:53` |
| **Fonte** | Claude |

**Evidência:** `if not user or not verify_password(...)`. Quando o e-mail não existe, o bcrypt não roda, e a resposta é mais rápida.

**Impacto:** baixo; facilita ataques direcionados.

**Correção recomendada:** quando o usuário não existir, conferir a senha contra um hash fixo de mesmo custo.

### SEC-014 — CPF em texto puro e devolvido em toda resposta de usuário · Baixa
| | |
|---|---|
| **Pilar** | Confidencialidade (LGPD) |
| **Princípio violado** | Menor privilégio |
| **STRIDE** | I |
| **CWE / OWASP** | CWE-359 / API3:2023 |
| **Local** | `app/serializers.py:188`, `app/models.py:33` |
| **Fonte** | Claude |

**Evidência:** `serialize_usuario` sempre inclui `"cpf"`. O campo não tem validação, e não há política de retenção para `log_operacao` nem para os refresh tokens expirados.

**Impacto:** LGPD, minimização (art. 6º III) e segurança (art. 46).

**Correção recomendada:**
- `response_model` por contexto: CPF mascarado nas listagens.
- Validação de formato.
- Rotina de limpeza de logs e tokens expirados.

### SEC-015 — Admin escolhe e conhece o TOTP de outro usuário · Baixa
| | |
|---|---|
| **Pilar** | Não-repúdio, Autenticidade |
| **Princípio violado** | Separação de privilégios |
| **STRIDE** | R, S |
| **CWE / OWASP** | CWE-284 / API5:2023 |
| **Local** | `app/routers/usuarios.py:254,268` |
| **Fonte** | Claude |

**Evidência:** `POST /usuarios/{id}/mfa/setup` devolve o segredo ao admin, e `.../mfa/enable` grava um segredo escolhido por ele.

**Impacto:** um admin consegue agir em nome do usuário, e a trilha registra a ação como do usuário. Exige conta admin.

**Correção recomendada:** o admin apenas reseta, e o próprio usuário configura o MFA no próximo login.

### SEC-016 — Cópias antigas do código na raiz · Info
| | |
|---|---|
| **Pilar** | Integridade |
| **Princípio violado** | Superfície de ataque mínima |
| **STRIDE** | — |
| **CWE / OWASP** | CWE-1164 / — |
| **Local** | `auth.py`, `routers/*.py` (raiz) |
| **Fonte** | Claude |

**Evidência:** esses arquivos contêm as versões anteriores às correções N1–N8. A aplicação não os carrega (`app/main.py` importa `app.routers`).

**Impacto:** confundem revisões e scanners. Um import errado reativaria as falhas já corrigidas.

**Correção recomendada:** apagar os arquivos.

## 6. Dependências e componentes
| Pacote | Versão | CVE / ID (exemplos) | Severidade | Versão corrigida | Alcançável? |
|---|---|---|---|---|---|
| pillow | 11.1.0 | CVE-2026-42311, CVE-2026-25990, CVE-2026-112393 (+52) | 5 Críticas, 35 Altas | 13.0.0 | **Sim**: `Image.open` em todo upload, sem restrição de formato → SEC-002 |
| python-multipart | 0.0.20 | CVE-2026-42561, CVE-2026-53539, CVE-2026-24486 (+4) | 3 Altas | 0.0.31 | **Sim (DoS)**: parser executado antes da auth → SEC-003. Escrita arbitrária (CVE-2026-24486): não, o Starlette não usa o modo que mantém o nome do arquivo |
| starlette (transitiva) | 0.41.3 | CVE-2025-62727 | Alta | 0.49.1 | **Sim**: `FileResponse` com `Range` no `/uploads` público → SEC-003 (identificada manualmente, fora dos scanners) |
| python-jose | 3.3.0 | CVE-2024-33663, CVE-2026-85394, CVE-2024-33664 | 2 Críticas | 3.4.0 / sem correção | Não: só HS256 com `algorithms` fixo → SEC-006 |
| cryptography | 44.0.0 | CVE-2026-26007, CVE-2026-69247, GHSA-537c-gmf6-5ccf | 4 Altas | 50.0.0 | Não: a API não usa PKCS#7, X.509 nem curvas SECT → SEC-006 |
| python-dotenv | 1.0.1 | CVE-2026-28684 | Média | 1.2.2 | Baixa: só lê o `.env` local |
| pytest | 8.3.4 | CVE-2025-71176 | — | — | Não: só dependência de teste |

## 7. Pontos positivos
- **Autenticação:**
  - bcrypt para senhas;
  - refresh tokens aleatórios (`secrets.token_urlsafe(48)`), guardados como SHA-256 e rotacionados;
  - JWT com `algorithms` fixo e `type` conferido (`app/deps.py:19`);
  - o papel vem do banco, não do token.
- **MFA:**
  - tokens separados para verificação e setup (N1);
  - segredo pendente até a confirmação (item 1);
  - troca de autenticador exige o código atual;
  - perfis obrigatórios não conseguem desativar o MFA (N5).
- **Autorização:**
  - `require_roles` em todas as escritas administrativas;
  - limites de gestão entre admin e gestor (N4);
  - separação de deveres no aceite (N3);
  - regra única em problemas (item 6).
- **Limite de tentativas** em login, MFA e reautenticação (N6).
- **Uploads:**
  - tipo detectado pelo conteúdo e nome aleatório;
  - proteção contra travessia de diretório;
  - `nosniff` e CSP `sandbox` no download (N7).
- **Configuração secure by default:**
  - a API não sobe sem `JWT_SECRET` forte (N8);
  - `/admin/*` desligado sem `SEED_SECRET`, e as operações destrutivas exigem opt-in (N2).
- **Sem SQL dinâmico:** todo acesso passa pelo ORM, e o DDL em `database.py` é estático. As chamadas externas usam URL fixa HTTPS e timeout.
- **Histórico limpo:** o gitleaks não encontrou segredos em 43 commits.
- **Testes:** 624 testes, incluindo uma suíte de regressão de segurança para cada correção.

## 8. Limitações
- Todos os scanners executaram (`status.txt` sem falhas).
- **Sem lockfile:** trivy e osv analisaram só os pacotes listados em `requirements*.txt`. As dependências transitivas não foram verificadas por ferramenta; o Starlette foi conferido manualmente.
- **Não testei o ambiente de produção:** a existência das contas de seed no Render (SEC-001) precisa ser verificada pela equipe.
- **Comportamento do proxy:** não foi verificado se o Render sobrescreve o `X-Forwarded-For` (premissa do limite por IP de N6).
- **CVEs de 2026:** muitas descrições citadas são posteriores ao conhecimento do analisador. A alcançabilidade foi avaliada pelo título e pelo componente afetado, não por PoC.
- **Natureza da análise:** é estática e não substitui teste dinâmico (DAST) nem pentest. O front web/mobile ficou fora do escopo.

## 9. Plano de ação sugerido
1. **Imediato:**
   - Verificar e neutralizar as contas de seed em produção, e remover o seed do `start.sh` (SEC-001).
   - Atualizar o Pillow e restringir os formatos no `Image.open` (SEC-002).
   - Limitar o tamanho do corpo antes da autenticação e atualizar python-multipart e FastAPI/Starlette (SEC-003).
2. **Curto prazo (Média):**
   - Mediação completa em contratos e imóveis (SEC-004).
   - Revogação de sessões na troca de credencial (SEC-005).
   - Migração de python-jose para PyJWT e lockfile com hashes (SEC-006).
3. **Melhoria contínua:**
   - Hardening de CORS, docs e cabeçalhos (SEC-007).
   - Container não root e CI fixado por SHA (SEC-008).
   - Remover `onecheck.db` e o código antigo do repositório (SEC-009, SEC-016).
   - Auditoria com IP e campos alterados (SEC-010).
   - Política de senha (SEC-011), regras de negócio e LGPD (SEC-012, SEC-014), MFA por terceiros (SEC-015), timing no login (SEC-013).
   - Rodar `/security-audit diff` a cada PR e osv-scanner/trivy no CI.
