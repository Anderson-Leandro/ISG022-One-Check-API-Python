# Validação do PENDENCIAS_API.md

- **Data:** 2026-10-25 · **Branch:** `dev` (commit `db09944`)
- **Método:** leitura do código de cada rota citada, seguindo até os helpers de autorização, os serializers, os models e a configuração. Comparei os arquivos `.py` do container `onecheck-api` (o que o time do front usou nos testes) com `app/` do repositório: **são idênticos**. Portanto o comportamento relatado corresponde ao código atual.
- **Não executei chamadas HTTP** contra a API, para não alterar estado (o item 1, por exemplo, quebra o MFA do usuário).
- **Nenhum código foi alterado.**

## Resumo

| # | Item | Veredito | Severidade |
|---|---|---|---|
| 1 | `GET /auth/mfa/setup` sobrescreve o segredo TOTP ativo | ✅ Confirmado (e há variante crítica, ver N1) · corrigido ([relatório](correcao-itens-1-2-6-2026-10-25.md)) | Alta |
| 2 | Locatário lista todos os usuários | ✅ Confirmado (vaza também CPF) · corrigido ([relatório](correcao-itens-1-2-6-2026-10-25.md)) | Alta |
| 3 | Checklist com `vistoriador_id` inexistente → 500 | ✅ Confirmado (e a rota não tem autorização, ver N3) · corrigido com N3 | Média |
| 4 | `/dashboard` ignora o perfil | ✅ Confirmado | Média |
| 5 | Locatário recebe 403 nos agendamentos do próprio contrato | ✅ Confirmado: bloqueio explícito no código (decisão de negócio) | Baixa |
| 6 | Vistoriador: 403 na lista de problemas, 200 no problema por ID | ✅ Confirmado: o furo está no acesso por ID (BOLA) · corrigido ([relatório](correcao-itens-1-2-6-2026-10-25.md)) | Média |
| 7 | Atualizar problema só para admin/gestor | ✅ Confirmado: restrição intencional, não é falha | Info |
| 8 | `enviar-para-aceite` não exige item / `pendente_revisao` | ⚠️ Parcial: **falso positivo** na exigência de item; `pendente_revisao` sem uso confirmado | Baixa |
| 9 | Bodies não documentados no OpenAPI | ✅ Confirmado | Baixa |
| 10 | Respostas sem schema / nomes inconsistentes | ⚠️ Parcial: sem `response_model` confirmado; `role × perfil` é **falso positivo** na API | Baixa |
| 11 | Tipos de agendamento | ✅ Confirmado (decisão de negócio) | Info |
| 12 | Endpoints faltando / rotas MFA duplicadas | ⚠️ Parcial: duas das "duplicadas" têm semânticas diferentes, e uma é falha de segurança (N5) | Info / Alta |
| — | CORS só para `localhost:5173` | ❌ **Falso**: a configuração ativa é `*` com credenciais | Baixa |

Encontrei também **8 falhas novas** durante a validação (seção 3). Duas são **críticas**.

---

## 1. Itens de segurança do documento

### Item 1 — `GET /auth/mfa/setup` troca o segredo de quem já tem MFA · ✅ Confirmado · Alta · corrigido ([relatório](correcao-itens-1-2-6-2026-10-25.md))
- **Evidência:** `app/routers/auth_router.py:139-145`. Gera o segredo e grava direto em `user.mfa_secret`, com `db.commit()`, sem segredo pendente e sem exigir código atual. Basta chamar a rota para invalidar o autenticador configurado.
- **Pilares/princípios:** Disponibilidade (o usuário fica sem acesso) e Autenticidade. Viola fail secure e a semântica de GET (que não deveria alterar estado).
- **Rotas paralelas:**
  - `POST /usuarios/me/mfa/setup` (`usuarios.py:74-77`) e `POST /usuarios/{id}/mfa/setup` (`usuarios.py:190-200`) **não** gravam nada: devolvem o segredo, e o `enable` confirma com segredo + código (`usuarios.py:80-93`). Esse é o padrão correto e **não são afetadas**. Ressalva: em `/usuarios/{id}/mfa/setup`, o admin/gestor fica conhecendo o segredo TOTP do outro usuário.
  - `GET /auth/mfa/setup-login` (`auth_router.py:95-109`) **também grava direto**, e é pior: ver **N1**.
- **Correção:** guardar o segredo em `mfa_secret_pendente` e só promovê-lo a `mfa_secret` em `/mfa/activate` após validar o código. Trocar o método para POST e exigir o código TOTP atual (ou a senha) quando já houver MFA ativo.

### Item 2 — Locatário lista todos os usuários · ✅ Confirmado · Alta · corrigido ([relatório](correcao-itens-1-2-6-2026-10-25.md))
- **Evidência:** `app/routers/usuarios.py:109-122` usa só `get_current_user`. As demais rotas do recurso usam `require_roles("admin", "gestor")` (`:129`, `:142`, `:249`).
- **Agravante:** `serialize_usuario` (`app/serializers.py:182-193`) devolve **CPF**, e-mail e estado do MFA de todos. O filtro `?role=admin` lista exatamente as contas mais valiosas para um atacante.
- **Pilares:** Confidencialidade, LGPD (minimização, art. 6º III). OWASP API1/API3, CWE-862 / CWE-200.
- **Correção:** `require_roles("admin", "gestor")` na listagem. Se outro perfil precisar escolher usuários (ex.: gestor escolhendo locatário), criar uma rota com payload mínimo (`id`, `nome`), sem CPF.

---

## 2. Itens de comportamento, contrato e decisões

### Item 3 — 500 com `vistoriador_id` inexistente · ✅ Confirmado · Média
- **Evidência:** `app/routers/contratos.py:302-319` grava `body.vistoriador_id` sem verificar se o usuário existe nem se tem perfil `vistoriador`. A FK `models.py:141` estoura `IntegrityError` no commit (Postgres), que não é tratado.
- **Observação:** no SQLite local (padrão sem `DATABASE_URL`), FKs não são verificadas porque não há `PRAGMA foreign_keys` em `database.py`. Lá o checklist seria **criado com vistoriador órfão**, em silêncio.
- **Correção:** validar que existe um `Usuario` ativo com `role == "vistoriador"` e responder 422/404. Ver também **N3**: essa rota não tem autorização nenhuma.

### Item 4 — `/dashboard` com números globais · ✅ Confirmado · Média
- **Evidência:** `app/routers/dashboard.py:21-38`. Os quatro `count()` não filtram por perfil, enquanto `/imoveis` filtra (`imoveis.py:68-78`).
- **Pilar:** Confidencialidade (vazamento de agregados de negócio). Mediação completa inconsistente.
- **Correção:** aplicar os mesmos filtros das listagens ou restringir a admin/gestor.

### Item 5 — Locatário: 403 nos agendamentos do próprio contrato · ✅ Confirmado · Baixa
- **Evidência:** `app/routers/contratos.py:210-211` bloqueia **todo** locatário, mesmo o dono do contrato. É intencional no código, então ver ou não as datas é decisão de negócio.
- **Problema real na mesma rota:** para os outros perfis não há checagem de vínculo. Qualquer vistoriador ou visualizador lê os agendamentos de **qualquer** contrato (o mesmo vale para `GET /contratos/{id}`, `:120-133`).
- **Sugestão:** permitir ao locatário dono (`ct.locatario_id == user.id`) e restringir o vistoriador aos contratos em que atua.

### Item 6 — Vistoriador: 403 na lista, 200 por ID · ✅ Confirmado · Média · corrigido ([relatório](correcao-itens-1-2-6-2026-10-25.md))
- **Evidência:**
  - Na lista, `contratos.py:325-330` (`_assert_pode_problema`) libera só admin, gestor e locatário dono.
  - Por ID, `problemas.py:34-40` (`_assert_pode_acessar_problema`) só restringe **locatário**. Vistoriador e visualizador abrem **qualquer** problema e suas atualizações (`problemas.py:43-56` e `:173-198`), inclusive de contratos onde não atuam.
- **Conclusão:** a regra correta é a da lista. O acesso por ID é um BOLA (OWASP API1, CWE-639).
- **Correção:** unificar num único helper de autorização. Se o vistoriador deve ver problemas, que seja só dos contratos onde tem checklist.

### Item 7 — Atualizar problema só admin/gestor · ✅ Confirmado (intencional) · Info
- **Evidência:** `problemas.py:62` e `:98` usam `require_roles("admin", "gestor")`. Não é falha.
- **Se o locatário for comentar:** usar `_assert_pode_acessar_problema` corrigido (item 6) e manter o `PATCH /status` restrito.

### Item 8 — Fluxo do checklist · ⚠️ Parcialmente falso positivo · Baixa
- **"`enviar-para-aceite` não exige item" é falso positivo:** `checklists.py:349-355` exige ≥1 item com `estado` preenchido, com a mesma consulta do `submeter`. O container roda esse mesmo código. Provavelmente o checklist testado já tinha itens.
- **Diferenças reais entre as duas rotas:** `enviar-para-aceite` é só admin/gestor e **não** atualiza `data_vistoria`, que o `submeter` define em `:329`.
- **`pendente_revisao` sem uso:** confirmado. Só aparece em `data_status.py:34` e `dashboard.py:27`, e nenhuma rota faz a transição. `rejeitar` é estado final (`checklists.py:418`). Definir com o negócio se rejeitado deve voltar para revisão.

### Item 9 — Bodies não documentados · ✅ Confirmado · Baixa
- **Evidência:** `contratos.py:333-405`, `problemas.py:58-74` e `:92-147` leem `request.json()` / `request.form()` à mão. O `ProblemaCreate` existe (`schemas.py:362`) e é importado em `contratos.py:26`, mas **não é usado**.
- **Impacto de segurança:** sem Pydantic, a validação fica espalhada e incompleta.
  - Quem cria o problema escolhe o `status` inicial (`contratos.py:404`). O locatário pode abri-lo já como `resolvido` ou `fechado`.
  - O campo `foto_url` aceita qualquer string vinda do cliente (`contratos.py:405`, `problemas.py:132`), incluindo URL externa ou `javascript:`.

### Item 10 — Respostas sem schema · ⚠️ Parcial · Baixa
- **Sem `response_model`:** confirmado, há **0** ocorrências em `app/`. Além do problema de documentação, aumenta o risco de vazar campos (ver CPF no item 2).
- **`role × perfil` é falso positivo do lado da API:** a API só usa `role`. O nome `perfil` vem do front antigo.
- **`mfa_enabled × mfa_ativo`:** os dois existem de propósito, com significados diferentes (`serializers.py:189-191`). `mfa_enabled` é a exigência; `mfa_ativo` significa exigência + segredo configurado. Falta documentar.

### Item 11 — Tipos de agendamento · ✅ Confirmado · Info
- Validação consistente em `contratos.py:236`, `:291` e `agendamentos.py:40`. O enum não aparece no OpenAPI porque o campo é `str`.
- Decisão de negócio. Se mantido, usar `Literal["inicial", "encerramento"]` no schema.

### Item 12 — Endpoints faltando e rotas duplicadas · ⚠️ Parcial
- **DELETE inexistente:** confirmado para checklist, contrato e problema. Também não há rotas de anexos, assinatura ou histórico.
  - **Recomendação de segurança:** **não** criar hard delete de contrato ou checklist. São evidência da vistoria, e excluí-los destrói o não-repúdio. Prefira cancelamento ou soft delete restrito a admin, com log. Limpar dados de teste direto no banco local.
- **Duplicatas reais** (o mesmo handler com dois decorators): `/usuarios/{id}/mfa/enable` = `/habilitar` (`usuarios.py:203-204`); `DELETE /usuarios/{id}/mfa` = `POST /desabilitar` (`:227-228`).
- **Não são duplicatas:**
  - `/auth/mfa/disable` (`auth_router.py:167-182`) é o admin desativando o MFA de **outro** usuário.
  - `/auth/mfa/desabilitar` (`:197-207`) é o usuário desativando **o próprio** MFA, sem código nem senha. Isso é falha de segurança: **N5**.

### CORS · ❌ Falso
- O documento diz que só `http://localhost:5173` está liberado. Na prática:
  - o container ativo tem `CORS_ORIGINS=*`;
  - o padrão em `config.py:30-31`, `docker-compose.yml:18` e `render.yaml` também é `*`, com `allow_credentials=True` (`main.py:37-43`).
- O impacto é limitado porque a autenticação é por header Bearer, e não por cookie. Mesmo assim, não é secure by default: definir uma lista explícita de origens.

---

## 3. Falhas novas encontradas durante a validação

| ID | Falha | Severidade |
|---|---|---|
| N1 | Bypass do MFA usando só a senha | **Crítica** · ✅ corrigida ([relatório](correcao-n1-n2-2026-10-25.md)) |
| N2 | Reset do banco e tomada da conta admin com o `SEED_SECRET` padrão | **Crítica** · ✅ corrigida ([relatório](correcao-n1-n2-2026-10-25.md)) |
| N3 | Criação de checklist sem autorização, e locatário vistoriando e aceitando o próprio imóvel | Alta · ✅ corrigida ([relatório](correcao-n3-n4-n5-2026-10-25.md)) |
| N4 | Gestor consegue se promover a admin e assumir contas de admin | Alta · ✅ corrigida ([relatório](correcao-n3-n4-n5-2026-10-25.md)) |
| N5 | Desativar o próprio MFA sem reautenticação | Alta · ✅ corrigida ([relatório](correcao-n3-n4-n5-2026-10-25.md)) |
| N6 | Sem rate limit em login e verificação de MFA | Média |
| N7 | Uploads sem validação de tipo, servidos publicamente | Média |
| N8 | Segredos com valor padrão no código e no compose | Média |

### N1 — Bypass do MFA usando só a senha · Crítica
- **Fluxo:**
  1. `POST /auth/login` com a senha correta de um usuário com MFA devolve `temp_token` do tipo `"mfa"` (`auth_router.py:46-52`).
  2. `GET /auth/mfa/setup-login?temp_token=...` aceita esse mesmo tipo (`:98`), **gera um segredo novo, grava e devolve** (`:105-109`).
  3. O atacante calcula o código com esse segredo e chama `POST /auth/mfa/activate-login` (`:112-136`), recebendo `access_token` e `refresh_token`.
- **Impacto:** o segundo fator é anulado para admin, gestor e vistoriador. Quem tem só a senha entra, e de quebra troca o autenticador da vítima, deixando-a sem acesso.
- **STRIDE:** Spoofing + Elevation. **Pilar:** Autenticidade. CWE-308 / CWE-287.
- **Correção:** `setup-login` e `activate-login` só podem funcionar quando `mfa_setup_required(user)` é verdadeiro (MFA exigido e ainda sem segredo). Emitir um tipo de token distinto (`"mfa_setup"`) apenas nesse caso do login. Junto, aplicar a correção do segredo pendente do item 1.

### N2 — Reset do banco e tomada da conta admin com o `SEED_SECRET` padrão · Crítica
- **Evidência:**
  - `config.py:28` usa `SEED_SECRET = os.getenv("SEED_SECRET", "onecheck-seed-dev")`, valor que está público no repositório.
  - `render.yaml` **não define** `SEED_SECRET`, então em produção vale esse padrão. `docker-compose.yml:17` usa o mesmo valor.
  - `POST /api/v1/admin/seed` com `{"force": true}` e esse header, **sem login**, chama `_clear_all` e recria os usuários de seed com senhas e segredo TOTP conhecidos (`seed_service.py:276-294`).
- **Impacto:** qualquer pessoa na internet apaga todos os dados e entra como admin.
- **Pilares:** Integridade, Disponibilidade, Autenticidade. Viola secure by default. CWE-798 / CWE-1188.
- **Correção:**
  - sem `SEED_SECRET` definido, as rotas `/admin/*` ficam **desabilitadas** (fail secure), e o valor padrão no código deve ser removido;
  - desabilitar `force` fora do ambiente de desenvolvimento;
  - exigir também um usuário admin autenticado;
  - comparar o segredo com `hmac.compare_digest`.

### N3 — Criação de checklist sem autorização · Alta
- **Evidência:**
  - `POST /contratos/{id}/checklists` (`contratos.py:280-286`) usa só `get_current_user`, sem checar perfil, vínculo com o contrato ou status do contrato.
  - O vistoriador do checklist é o `vistoriador_id` enviado no corpo.
- **Cenário:** a locatária cria um checklist no próprio contrato e se informa como vistoriadora. Ela passa em `_assert_vistoriador` (`checklists.py:59-63`), preenche os itens, submete e **aceita a própria vistoria** como locatária (`checklists.py:66-72`). Ela também pode criar checklists em contratos de outras pessoas.
- **Pilares:** Integridade e Não-repúdio: o laudo deixa de provar quem vistoriou. OWASP API5, CWE-862.
- **Correção:**
  - restringir a rota a admin/gestor;
  - validar que `vistoriador_id` é um usuário com perfil vistoriador;
  - exigir contrato ativo;
  - impedir que vistoriador e aceitante sejam a mesma pessoa (separação de deveres).

### N4 — Gestor consegue se promover a admin · Alta
- **Evidência:**
  - `PUT /usuarios/{id}` (`usuarios.py:137-168`) aceita `role` como string livre (`schemas.py:118`), sem lista de valores permitidos e sem impedir que o gestor altere a si mesmo ou a um admin.
  - O gestor também pode trocar a senha e o e-mail de um admin e zerar o MFA dele (`:227-242`).
  - O gestor pode criar usuários com perfil admin (`:245-266`, `schemas.py:100`).
- **Pilar:** Autenticidade. Viola menor privilégio. STRIDE Elevation, CWE-269.
- **Correção:**
  - aceitar só os perfis existentes (`Literal[...]`);
  - só admin pode atribuir `admin`/`gestor` ou alterar contas admin;
  - nenhum usuário altera o próprio perfil.

### N5 — Desativar o próprio MFA sem reautenticação · Alta
- **Evidência:** `POST /auth/mfa/desabilitar` (`auth_router.py:197-207`) e `DELETE /usuarios/me/mfa` (`usuarios.py:96-106`) desligam o MFA com apenas o access token. Isso vale inclusive para perfis em que o MFA é obrigatório (`MFA_REQUIRED_ROLES`, `auth.py:17`).
- **Impacto:** um token roubado (XSS, máquina compartilhada) vira acesso permanente só com a senha.
- **Correção:** exigir código TOTP atual + senha e bloquear para perfis obrigatórios. Se essa função for necessária, deixar só o admin resetar o MFA de outros, com log.

### N6 — Sem rate limit em login e verificação de MFA · Média
- `POST /auth/login` e `/auth/mfa/verify` não têm limite de tentativas. O `temp_token` vale 10 minutos com `valid_window=1` (`auth.py:96`), o que permite força bruta de senha e de código TOTP.
- **Correção:** limitar tentativas por IP e por conta (ex.: `slowapi`), bloquear temporariamente após N falhas e registrar as falhas de MFA no log.

### N7 — Uploads sem validação de tipo, servidos publicamente · Média
- `ALLOWED_MIME_TYPES` está definido em `problemas.py:17`, mas **nunca é usado**.
- A extensão salva vem do nome enviado pelo cliente (`checklists.py:248`, `contratos.py:385`, `problemas.py:121`). Um `.html` ou `.svg` enviado como "foto" é servido por `GET /uploads/{filename}` (`health.py:15-21`) **sem autenticação**, com `Content-Type` deduzido da extensão: XSS armazenado na origem da API.
- As fotos das vistorias também ficam públicas para quem tiver a URL (LGPD).
- **Correção:** validar o conteúdo (magic bytes ou Pillow), fixar a extensão pelo tipo detectado, servir com `Content-Disposition: attachment` e `X-Content-Type-Options: nosniff`, e avaliar autenticação no download.

### N8 — Segredos com valor padrão · Média
- `JWT_SECRET` tem fallback `"onecheck-dev-secret-change-me"` (`config.py:16`, `docker-compose.yml:12`).
- O Render gera um valor, mas qualquer outro deploy sem a variável aceita tokens forjados por quem lê o repositório. O mesmo vale para a senha padrão do Postgres no compose.
- **Correção:** falhar na inicialização se `JWT_SECRET` (e `SEED_SECRET`, se as rotas admin estiverem ativas) não estiverem definidos fora do ambiente de desenvolvimento.

---

## 4. Ordem sugerida de correção
1. **N2** (reset por seed) e **N1** (bypass de MFA): críticas e exploráveis sem conta válida ou só com a senha.
2. **N3**, **N4**, **N5** e os itens **1** e **2**.
3. Itens **3**, **4** e **6**, e **N6**, **N7**, **N8**.
4. Contrato do OpenAPI (itens 9, 10 e 11) e as decisões de negócio (itens 5, 7, 8 e 12), que dependem de confirmação do time.

Cada correção deve vir com um teste em `tests/` que reproduza o cenário de ataque descrito.
