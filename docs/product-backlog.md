# Product Backlog — OneCheck API

**Disciplina:** ISG-022 • Segurança no Desenvolvimento de Aplicações  
**Curso:** FATEC Mauá • DSM • 2026/2  
**Produto:** OneCheck — gestão de vistorias e locações imobiliárias  
**Registro:** arquivo Markdown pronto para migração para GitHub Issues/Projects

---

## 1. Product Goal

Nosso produto permitirá que **imobiliárias, gestores, vistoriadores e locatários** consigam **gerenciar contratos, executar vistorias com evidências fotográficas, emitir laudos e acompanhar ocorrências** para **reduzir disputas e garantir rastreabilidade do estado do imóvel**, respeitando **controle de acesso por perfil, titularidade contratual e trilha de auditoria**.

---

## 2. Atores e permissões

| Ator | Objetivos legítimos | Dados/ações | Restrições |
|---|---|---|---|
| **Locatário** | Consultar contrato/imóvel, aceitar ou rejeitar laudo, abrir problemas | Apenas recursos vinculados ao próprio contrato ativo | Não acessa dados de outros locatários; não gerencia carteira |
| **Vistoriador** | Preencher checklist, anexar fotos, submeter vistoria | Checklists e agendamentos atribuídos/operacionais | Não encerra contratos; não altera usuários; MFA obrigatório |
| **Gestor** | Operar imóveis, contratos, agendamentos e atendimento a problemas | Carteira operacional e métricas | Sem acesso irrestrito a administração total; MFA obrigatório |
| **Administrador** | Gerenciar usuários, MFA, auditoria e operação completa | Configurações, usuários, logs | Ações críticas auditadas; auto-exclusão bloqueada; MFA obrigatório |
| **Sistema externo (ViaCEP / Nominatim)** | Enriquecer endereço com CEP e geocoding | Consulta de CEP/coordenadas | Somente escopo necessário; timeout e fallback gracioso |

---

## 3. Épicos (capacidades)

| ID | Épico | Descrição |
|---|---|---|
| **E-01** | Identidade e Acesso | Cadastro, autenticação JWT, MFA, sessões e gestão de usuários com RBAC |
| **E-02** | Carteira Imobiliária | Imóveis, endereços, cômodos, geocoding e ciclo de vida da propriedade |
| **E-03** | Contratos e Agendamentos | Locação, vínculo locatário–imóvel e agendamento de vistorias |
| **E-04** | Vistorias e Laudos | Checklists, fotos, aceite/rejeição e emissão de laudo em PDF |
| **E-05** | Ocorrências e Comunicação | Problemas, linha do tempo, anexos e notificações |
| **E-06** | Auditoria e Segurança | Autorização por recurso, logs, hardening e evidências de segurança |

---

## 4. Backlog inicial (visão em tabela)

| ID | Épico | Item | Tipo | Prioridade | Estim. | Status | Sprint |
|---|---|---|---|---|---|---|---|
| US-001 | E-01 | Autenticar identidade com JWT e refresh | Story | Must | 5 | Ready | Sprint 1 |
| US-002 | E-01 | Configurar e validar MFA (TOTP) em papéis críticos | Story | Must | 5 | Ready | Sprint 1 |
| US-003 | E-01 | Administrar usuários com papéis e soft delete seguro | Story | Must | 5 | Ready | Sprint 1 |
| SEC-001 | E-06 | Validar autorização por recurso (anti-IDOR) | Security | Must | 5 | Ready | Sprint 1 |
| US-004 | E-02 | Cadastrar imóvel com endereço e geocoding | Story | Must | 5 | Ready | Sprint 1 |
| US-005 | E-03 | Criar e consultar contrato com titularidade | Story | Must | 5 | Ready | Sprint 1 |
| US-006 | E-03 | Agendar vistoria vinculada a contrato ativo | Story | Must | 3 | Backlog | Sprint 2 |
| US-007 | E-04 | Preencher checklist com itens e fotos | Story | Must | 8 | Ready | Sprint 2 |
| US-008 | E-04 | Aceitar ou rejeitar laudo de vistoria | Story | Must | 5 | Ready | Sprint 2 |
| US-009 | E-04 | Baixar laudo de vistoria em PDF | Story | Should | 5 | Backlog | Sprint 2 |
| SEC-002 | E-06 | Impedir adulteração de checklist finalizado | Security | Must | 5 | Ready | Sprint 2 |
| US-010 | E-05 | Registrar problema com foto e linha do tempo | Story | Should | 5 | Backlog | Sprint 2 |
| US-011 | E-06 | Consultar dashboard operacional | Story | Should | 3 | Backlog | Sprint 3 |
| SEC-003 | E-06 | Registrar auditoria append-only com IP e payload | Security | Must | 5 | Ready | Sprint 1 |
| SEC-004 | E-06 | Aplicar rate limiting em autenticação/MFA | Security | Should | 5 | Backlog | Sprint 3 |
| US-012 | E-02 | Isolar cômodos do imóvel com CRUD protegido | Story | Should | 3 | Backlog | Sprint 2 |
| US-013 | E-03 | Encerrar ou cancelar contrato liberando imóvel | Story | Should | 3 | Backlog | Sprint 2 |
| DOC-001 | E-06 | Manter threat model e baseline alinhados ao backlog | Task | Should | 2 | Ready | Sprint 1 |
| US-014 | E-04 | Enviar checklist para aceite formal | Story | Could | 3 | Backlog | Won’t now* |
| SEC-005 | E-06 | Migrar mídias para storage com URL assinada | Security | Could | 8 | Backlog | Won’t now |

\* “Won’t now” = fora do horizonte da próxima Sprint; permanece no backlog para não criar expectativa implícita.

**Total de itens:** 20 (dentro da faixa 12–20).  
**Itens explícitos de segurança:** SEC-001, SEC-002, SEC-003, SEC-004, SEC-005 (≥ 3 exigidos).

---

## 5. Itens refinados (histórias + critérios de aceite)

### US-001 — Autenticar identidade com JWT e refresh
**Como** usuário cadastrado, **quero** autenticar minha identidade e renovar a sessão, **para** acessar funcionalidades protegidas sem reenviar senha a cada chamada.

**Prioridade:** Must | **Estimativa:** 5 | **Dependências:** usuários existentes / seed  
**Segurança:** credenciais nunca retornadas; mensagens genéricas de falha; refresh revogável.

**Critérios de aceite:**
- Login com credenciais válidas retorna access token (ou fluxo MFA quando aplicável).
- Credenciais inválidas retornam erro genérico sem enumerar e-mail.
- Refresh rotaciona/revoga o refresh token anterior.
- Logout invalida o refresh token vigente.
- Requisição sem token em rota protegida é negada (401).

---

### US-002 — Configurar e validar MFA (TOTP) em papéis críticos
**Como** admin/gestor/vistoriador, **quero** configurar e validar MFA no primeiro acesso, **para** reduzir risco de sessão privilegiada com senha vazada.

**Prioridade:** Must | **Estimativa:** 5 | **Risco/Requisito:** R-02  
**Dependências:** US-001

**Critérios de aceite:**
- Conta privilegiada sem segredo MFA recebe `mfa_setup_required` e `temp_token` de escopo restrito.
- Access token definitivo só é emitido após TOTP válido.
- Setup autenticado gera segredo/URI utilizável em app autenticador.
- Tentativas inválidas de MFA não concedem acesso.
- Admin consegue resetar MFA de outro usuário com registro em auditoria.

---

### US-003 — Administrar usuários com papéis e soft delete seguro
**Como** administrador, **quero** criar, atualizar e desativar usuários com papéis definidos, **para** operar o acesso da imobiliária com menor privilégio.

**Prioridade:** Must | **Estimativa:** 5 | **Risco:** R-04  
**Dependências:** US-001

**Critérios de aceite:**
- Admin cria usuário com role válida (`admin`, `gestor`, `vistoriador`, `locatario`).
- Usuário autentica e consulta apenas `/usuarios/me` para dados próprios.
- Soft delete não remove fisicamente o registro.
- Auto-desativação é bloqueada com mensagem clara.
- Respostas não expõem `senha_hash` nem segredo MFA.

---

### SEC-001 — Validar autorização por recurso (anti-IDOR)
**Contexto:** Risco **R-01** / ameaça de acesso horizontal.  
**Requisito:** a API deve validar autorização por recurso no backend.

**Como** usuário autenticado, **quero** que somente recursos autorizados ao meu perfil/titularidade sejam retornados, **para** evitar exposição indevida de dados de terceiros.

**Prioridade:** Must | **Estimativa:** 5 | **Tipo:** Security  
**Dependências:** US-001, US-005 (contratos para titularidade)

**Critérios de aceite:**
- Locatário A não acessa imóvel/contrato/checklist de B (403/404 sem vazamento).
- Decisão de autorização ocorre no backend, não apenas no frontend.
- Tentativas negadas podem ser auditadas sem conteúdo sensível desnecessário.
- Testes automatizados cobrem acesso permitido e negado (positivo e negativo).

**Given / When / Then (exemplo):**
- Dado que o locatário A está autenticado  
- E existe um imóvel vinculado apenas ao contrato do locatário B  
- Quando A solicitar `GET /imoveis/{id_de_B}`  
- Então a API deve negar o acesso  
- E não deve retornar dados do imóvel.

---

### US-004 — Cadastrar imóvel com endereço e geocoding
**Como** gestor/admin, **quero** cadastrar imóvel com endereço e coordenadas automáticas, **para** manter a carteira georreferenciada.

**Prioridade:** Must | **Estimativa:** 5 | **Dependências:** US-001

**Critérios de aceite:**
- Criação atômica persiste imóvel + endereço.
- Falha de ViaCEP/Nominatim não quebra a criação (coordenadas nulas + fallback).
- Locatário não cria/edita imóveis de terceiros.
- Soft delete de imóvel com locação ativa é bloqueado.

---

### US-005 — Criar e consultar contrato com titularidade
**Como** gestor, **quero** vincular imóvel a locatário com datas válidas, **para** estabelecer o vínculo jurídico e a âncora de autorização.

**Prioridade:** Must | **Estimativa:** 5 | **Dependências:** US-003, US-004

**Critérios de aceite:**
- Contrato só é criado para imóvel disponível e locatário válido.
- Locatário consulta apenas contratos em que é titular.
- Detalhe do contrato exige autenticação.
- Status do imóvel reflete locação ativa.

---

### US-006 — Agendar vistoria vinculada a contrato ativo
**Como** gestor, **quero** agendar vistoria inicial/encerramento, **para** organizar a execução técnica no tempo certo.

**Prioridade:** Must | **Estimativa:** 3 | **Dependências:** US-005

**Critérios de aceite:**
- Agendamento exige contrato ativo e data futura válida.
- Roles não autorizadas não criam/alteram agendamento.
- Listagem do contrato retorna apenas agendamentos daquele contrato.

---

### US-007 — Preencher checklist com itens e fotos
**Como** vistoriador, **quero** registrar itens por cômodo com fotos e observações, **para** documentar o estado do imóvel com evidências.

**Prioridade:** Must | **Estimativa:** 8 | **Dependências:** US-006 (ou contrato elegível)

**Critérios de aceite:**
- Checklist inicia vinculado a contrato.
- Itens e fotos só são mutáveis em `em_preenchimento`.
- Upload rejeita tipos/tamanhos inválidos de forma segura.
- Submissão trava novas edições indevidas conforme máquina de estados.

---

### US-008 — Aceitar ou rejeitar laudo de vistoria
**Como** locatário titular, **quero** aceitar ou rejeitar o laudo com motivo, **para** formalizar concordância ou contestar o estado registrado.

**Prioridade:** Must | **Estimativa:** 5 | **Dependências:** US-007  
**Risco:** R-03

**Critérios de aceite:**
- Somente o locatário titular do contrato aceita/rejeita.
- Rejeição exige motivo persistido.
- Aceite gera registro histórico com timestamp.
- Usuário não titular recebe negação sem dados indevidos.

---

### US-009 — Baixar laudo de vistoria em PDF
**Como** usuário autorizado, **quero** baixar o laudo em PDF, **para** usar o documento em processos operacionais e evidência.

**Prioridade:** Should | **Estimativa:** 5 | **Dependências:** US-007

**Critérios de aceite:**
- PDF contém imóvel, contrato, itens e informações de aceite quando houver.
- Download exige autenticação e autorização por recurso.
- Erros de geração não expõem stack trace ao cliente.

---

### SEC-002 — Impedir adulteração de checklist finalizado
**Contexto:** Risco **R-03** — fraude em laudo após conclusão.

**Como** parte interessada no laudo, **quero** que checklists fora de `em_preenchimento` sejam imutáveis, **para** preservar integridade probatória.

**Prioridade:** Must | **Estimativa:** 5 | **Tipo:** Security  
**Dependências:** US-007, US-008

**Critérios de aceite:**
- Após `pendente_aceite`/`finalizado`, edição de itens/fotos é negada.
- Transições de estado inválidas são rejeitadas.
- Tentativas de alteração indevida geram evidência auditável.
- Testes cobrem ciclo de vida completo do checklist.

---

### US-010 — Registrar problema com foto e linha do tempo
**Como** locatário, **quero** abrir ocorrência vinculada ao meu contrato e acompanhar atualizações, **para** registrar defeitos com rastreabilidade.

**Prioridade:** Should | **Estimativa:** 5 | **Dependências:** US-005

**Critérios de aceite:**
- Problema só é aberto em contrato ativo do solicitante (ou por perfil autorizado).
- Linha do tempo ordena atualizações cronologicamente.
- Gestor/admin atualiza status; locatário não altera status arbitrariamente.
- Anexos seguem as mesmas regras de autorização do problema.

---

### US-011 — Consultar dashboard operacional
**Como** gestor/admin, **quero** ver métricas consolidadas, **para** priorizar operação (imóveis, checklists, problemas, agendamentos).

**Prioridade:** Should | **Estimativa:** 3 | **Dependências:** US-001

**Critérios de aceite:**
- Endpoint retorna contagens coerentes com o estado do banco.
- Locatário não acessa dashboard administrativo.
- Resposta não inclui segredos ou payloads internos sensíveis.

---

### SEC-003 — Registrar auditoria append-only com IP e payload
**Contexto:** Risco **R-05** — falha de não-repúdio.

**Como** administrador, **quero** consultar logs de mutações com autor, IP e payload sanitizado, **para** investigar incidentes e disputas.

**Prioridade:** Must | **Estimativa:** 5 | **Tipo:** Security  
**Dependências:** US-001

**Critérios de aceite:**
- Mutações relevantes gravam autor, entidade, ação, timestamp, IP e payload.
- Campos sensíveis (senha, segredos) são omitidos/mascarados no payload.
- Não existem rotas de edição/exclusão de logs para usuários.
- Filtros por data/entidade/usuário funcionam para perfil autorizado.

---

### SEC-004 — Aplicar rate limiting em autenticação/MFA
**Como** operador de segurança, **quero** limitar tentativas em `/auth/login` e `/auth/mfa/*`, **para** reduzir força bruta e abuso de TOTP.

**Prioridade:** Should | **Estimativa:** 5 | **Tipo:** Security  
**Dependências:** US-001, US-002  
**Referência:** roadmap em `docs/security/security-baseline.md`

**Critérios de aceite:**
- Após limiar configurável, novas tentativas são rejeitadas temporariamente.
- Resposta não auxilia enumeração de contas.
- Limite aplica-se por IP e/ou identificador de conta.
- Evidência/teste demonstra bloqueio após excesso de tentativas.

---

### US-012 — Isolar cômodos do imóvel com CRUD protegido
**Como** gestor, **quero** manter cômodos do imóvel, **para** estruturar a vistoria por ambiente.

**Prioridade:** Should | **Estimativa:** 3 | **Dependências:** US-004

**Critérios de aceite:**
- CRUD de cômodo exige papel autorizado.
- Cômodo sempre pertence a um imóvel existente.
- Locatário não altera estrutura de cômodos.

---

### US-013 — Encerrar ou cancelar contrato liberando imóvel
**Como** gestor, **quero** encerrar/cancelar contrato, **para** liberar o imóvel para nova locação com consistência.

**Prioridade:** Should | **Estimativa:** 3 | **Dependências:** US-005

**Critérios de aceite:**
- Encerrar/cancelar atualiza status do contrato e libera imóvel (`disponivel`) atomicamente.
- Operação é auditada.
- Perfis sem permissão são negados.

---

### DOC-001 — Manter threat model e baseline alinhados ao backlog
**Como** time do projeto, **quero** atualizar documentação de riscos/arquitetura quando controles mudarem, **para** sustentar a defesa e rastreabilidade ISG-022.

**Prioridade:** Should | **Estimativa:** 2 | **Tipo:** Task

**Critérios de aceite:**
- Itens SEC referenciam IDs de risco (R-0x) quando aplicável.
- `docs/security/*` e arquitetura refletem decisões da Sprint.
- Nenhum segredo real versionado na documentação.

---

### US-014 — Enviar checklist para aceite formal
**Como** vistoriador/gestor, **quero** enviar checklist submetido para aceite do locatário, **para** iniciar o rito formal de concordância.

**Prioridade:** Could | **Estimativa:** 3 | **Dependências:** US-007

**Critérios de aceite:**
- Transição para `pendente_aceite` só ocorre a partir de estado válido.
- Locatário titular passa a conseguir aceitar/rejeitar.
- Edição técnica permanece bloqueada após o envio.

---

### SEC-005 — Migrar mídias para storage com URL assinada
**Como** time técnico, **quero** servir fotos via URL assinada com expiração, **para** reduzir acesso direto indevido a arquivos.

**Prioridade:** Could | **Estimativa:** 8 | **Tipo:** Security  
**Observação:** item grande — quebrar antes de entrar em Sprint (upload, leitura, política de expiração, migração).

**Critérios de aceite (alto nível):**
- Upload grava em storage externo/controlado.
- Leitura usa URL temporária autorizada.
- URL expirada não entrega o arquivo.
- Metadados e autorização por recurso permanecem no backend.

---

## 6. Rastreabilidade risco → item

| Risco | Item(ns) do backlog | Controle esperado |
|---|---|---|
| R-01 (IDOR / acesso horizontal) | SEC-001, US-005, US-004 | Autorização contextual no backend + testes negativos |
| R-02 (bypass MFA no 1º acesso) | US-002 | Setup bloqueante + temp token de escopo restrito |
| R-03 (adulteração de laudo) | SEC-002, US-007, US-008 | Máquina de estados + imutabilidade |
| R-04 (auto-exclusão admin) | US-003 | Bloqueio de auto-desativação |
| R-05 (falha de auditoria/não-repúdio) | SEC-003 | Log append-only com IP e payload sanitizado |

---

## 7. Priorização (MoSCoW) — justificativa resumida

| Classe | Itens | Por quê |
|---|---|---|
| **Must** | US-001..US-008, SEC-001..SEC-003 | Formam o incremento mínimo demonstrável + reduzem riscos inaceitáveis (R-01, R-02, R-03, R-05) |
| **Should** | US-009..US-013, SEC-004, DOC-001 | Alto valor operacional/segurança, com adiamento controlado |
| **Could** | US-014, SEC-005 | Agregam valor, sem comprometer o objetivo imediato |
| **Won’t now** | SEC-005 (execução), fatias avançadas de PDF assinado | Registrados para evitar expectativa implícita |

---

## 8. Dependências críticas

```text
US-001 (Auth)
  ├─ US-002 (MFA)
  ├─ US-003 (Usuários)
  ├─ SEC-003 (Auditoria)
  └─ US-004 (Imóveis) → US-005 (Contratos)
                              ├─ US-006 (Agendamentos)
                              ├─ US-010 (Problemas)
                              └─ US-007 (Checklist)
                                    ├─ US-008 / US-014 (Aceite)
                                    ├─ US-009 (PDF)
                                    └─ SEC-002 (Imutabilidade)

SEC-001 depende de Auth + regras de titularidade (Contratos)
SEC-004 depende de Auth/MFA estáveis
```

---

## 9. Definition of Ready (DoR)

Um item só entra na Sprint se:
- Objetivo e contexto estão compreensíveis
- Critérios de aceite estão definidos
- Dependências conhecidas
- Impacto de segurança identificado quando aplicável
- Tamanho compatível (≤ 5 ideal; 8+ deve ser quebrado)
- Dúvidas críticas resolvidas ou registradas como hipótese

---

## 10. Definition of Done (DoD)

- Implementação integrada e executável (quando aplicável)
- Critérios de aceite atendidos
- Revisão por outro integrante quando relevante
- Testes relevantes executados
- Nenhum segredo real versionado
- Documentação/threat model atualizados se a mudança impactar segurança
- Issue/PR com evidência suficiente da entrega

---

## 11. Próxima Sprint proposta

### Sprint Goal
> Entregar o fluxo mínimo de autenticação com MFA, consulta/gestão de dados próprios com autorização por recurso, e evidências iniciais de auditoria — base segura para contratos e vistorias.

### Candidatos Ready → Sprint 1
| ID | Item | Estim. |
|---|---|---|
| US-001 | Autenticar identidade com JWT e refresh | 5 |
| US-002 | Configurar e validar MFA (TOTP) | 5 |
| US-003 | Administrar usuários com soft delete seguro | 5 |
| SEC-001 | Validar autorização por recurso (anti-IDOR) | 5 |
| SEC-003 | Auditoria append-only com IP e payload | 5 |
| US-004 | Cadastrar imóvel com endereço/geocoding | 5 |
| US-005 | Criar/consultar contrato com titularidade | 5 |
| DOC-001 | Atualizar docs de risco/baseline | 2 |

### Sprint 2 (preview)
US-006, US-007, US-008, US-009, SEC-002, US-010, US-012, US-013

---

## 12. Labels sugeridas (GitHub)

- `type:story` · `type:task` · `type:security` · `type:bug`
- `priority:must` · `priority:should` · `priority:could`
- `area:backend` · `area:data` · `area:docs` · `area:security`
- `epic:identidade` · `epic:carteira` · `epic:contratos` · `epic:vistorias` · `epic:ocorrencias` · `epic:auditoria`

**Colunas de Project sugeridas:** Backlog → Ready → In Progress → Review → Done

---

## 13. Checklist de qualidade (oficina)

- [x] Product Goal explica resultado/valor
- [x] Atores principais identificados
- [x] Épicos organizam o produto (6) sem virar tarefas
- [x] 20 itens iniciais com comportamento verificável
- [x] Critérios de aceite nos itens prioritários
- [x] Segurança explícita (≥ 3 itens SEC) e também em critérios
- [x] Itens grandes sinalizados para quebra (SEC-005 / US-007)
- [x] Prioridade MoSCoW com justificativa valor/risco
- [x] Dependências críticas visíveis
- [x] Sprint Goal + itens Ready definidos
- [x] Registro versionável em `docs/product-backlog.md`

---

## 14. Referências internas

- `docs/architecture/architecture-v1.md`
- `docs/security/security-baseline.md`
- `docs/security/initial-risks.md`
- Guia da oficina: ISG022_Oficina_Product_Backlog.pdf
