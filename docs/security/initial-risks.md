# Initial Security Risks — OneCheck API

## 1. Matriz Consolidada de Riscos Iniciais

| ID | Ativo | Ameaça | Vulnerabilidade | Exploração | Impacto (Consequência) | Prob. | Impacto | Risco | Controles / Decisões Adotadas | Risco Residual |
|---|---|---|---|---|---|---|---|---|---|---|
| **R-01** | Dados Cadastrais e Endereço de Imóveis | Usuário malicioso autenticado (Locatário) | Endpoints de consulta de imóvel e endereço sem validação contextual de titularidade | Usuário altera o UUID do imóvel na requisição (`GET /imoveis/{id}`) para consultar dados de propriedades de terceiros | Exposição indevida de dados do imóvel, histórico de vistorias e endereço residencial de outros inquilinos | Média | Médio | **Médio** | **Decisão:** Backend valida em tempo de execução se o locatário possui contrato ativo para o imóvel solicitado e nega com HTTP 403 por padrão.<br>**Controle:** Validação contextual no router/service + testes de autorização negativa. | Erro de regra em novos endpoints; mitigado por testes de integração automatizados. |
| **R-02** | Credenciais e Sessão Administrativa | Atacante externo com senha vazada/obtida por phishing | Login emite token de acesso direto se a conta não tiver segredo MFA configurado | Atacante autentica em conta administrativa recém-criada burlando a exigência de segundo fator | Tomada de controle total da API, acesso irrestrito a todos os dados imobiliários e de usuários | Média | Alto | **Alto** | **Decisão:** Login detecta contas que exigem MFA sem secret e retorna `mfa_setup_required`, emitindo apenas `temp_token` com escopo restrito ao setup.<br>**Controle:** Endpoints `/auth/mfa/setup-login` e `/auth/mfa/activate-login` validando código TOTP antes da emissão do token JWT. | Comprometimento do dispositivo do usuário; mitigado por rotação de token e reset administrativo. |
| **R-03** | Laudos de Vistoria e Registros de Aceite | Locatário, vistoriador ou locador malicioso | Ausência de máquina de estados ou bloqueio de edição em laudos já concluídos | Usuário envia `PUT` ou `PATCH` para alterar avarias, fotos ou observações de um checklist já aprovado | Fraude em laudo pericial, quebra de fé pública e geração de disputas jurídicas e financeiras | Baixa | Alto | **Médio** | **Decisão:** Checklists finalizados tornam-se imutáveis no backend; o aceite formal é restrito exclusivamente ao titular do contrato e registrado com timestamp.<br>**Controle:** Validação de transição de estados (`em_preenchimento` ➔ `pendente_aceite` ➔ `finalizado`), tabela `aceite_checklists`. | Falhas pontuais na máquina de estados; mitigado por testes de ciclo de vida. |
| **R-04** | Dados Cadastrais e Contas de Usuários | Administrador por erro operacional ou conta comprometida | Endpoint `DELETE /usuarios/{id}` permitir a desativação do próprio usuário logado | Administrador envia o seu próprio UUID para exclusão, revogando o próprio acesso e potencialmente travando a gestão | Indisponibilidade de acesso administrativo e travamento de operações de gestão da imobiliária | Média | Alto | **Médio** | **Decisão:** Backend valida e proíbe explicitamente que um usuário autenticado desative a sua própria conta.<br>**Controle:** Verificação `if current.id == usuario_id: return fail(...)` no router/service + testes unitários. | Exclusão cruzada entre administradores distintos; mitigado por soft delete reversível (`ativo = False`). |
| **R-05** | Logs de Auditoria e Rastreabilidade | Usuário autenticado tentando fraude interna | Ausência de registro de IP e dados do payload original nas mutações de estado | Operador altera registros de aluguel ou dados cadastrais e posteriormente alega não-repúdio ou contesta autoria | Impossibilidade de investigar incidentes de segurança, responsabilizar infratores e cumprir conformidade | Média | Médio | **Médio** | **Decisão:** Cada mutação de estado registra compulsoriamente autor, entidade, ID, ação, data/hora UTC, IP de origem e payload JSON no banco de dados.<br>**Controle:** Modelo `LogOperacao` com campos `ip` e `payload` em tabela append-only. | Volume elevado de logs ao longo do tempo; mitigado por política futura de retenção e arquivo. |

---

## 2. Detalhamento dos Cenários de Risco

### Cenário 1: Quebra de Controle de Acesso e IDOR em Dados do Imóvel (R-01)
- **Ativo:** Dados Cadastrais e Endereço dos Imóveis (`Imovel` + `Endereco`).
- **Propriedades:** Confidencialidade + Integridade.
- **Ameaça:** Usuário malicioso autenticado (perfil `locatario`).
- **Vulnerabilidade:** Endpoints `GET /api/v1/imoveis/{id}` e `GET /api/v1/imoveis/{id}/endereco` consultarem registros apenas pelo UUID sem validar se o solicitante possui contrato de locação ativo para aquela propriedade.
- **Exploração:** O locatário altera o ID do imóvel na URL e acessa dados confidenciais, histórico de vistorias e endereço de outras pessoas.
- **Impacto:** Violação de privacidade residencial de locatários e vazamento de ativos imobiliários.
- **Probabilidade:** Média (acessível a qualquer locatário autenticado).
- **Impacto:** Médio (exposição de dados contidos e sem privilégio administrativo).
- **Princípios Aplicados:** *Secure by default*, *Menor privilégio*, *Fronteiras de confiança*.
- **Decisão de Arquitetura:** O backend valida a relação contratual ativa (`Contrato.imovel_id == id and Contrato.locatario_id == user.id and Contrato.status == 'ativo'`) e nega com HTTP 403 por padrão.
- **Controles Implementados:** Verificação no roteador/service, testes de integração cobrindo tentativa de acesso não autorizado, logs de auditoria.
- **Risco Residual:** Erro de implementação em novos endpoints; controlado via cobertura de testes de integração.

---

### Cenário 2: Bypass de MFA em Contas Administrativas no Primeiro Acesso (R-02)
- **Ativo:** Credenciais Administrativas e Sessão de Usuário (`Usuario` + `RefreshToken`).
- **Propriedades:** Confidencialidade + Autenticidade.
- **Ameaça:** Atacante externo de posse de credenciais vazadas ou obtidas por engenharia social/phishing.
- **Vulnerabilidade:** O sistema exigir MFA apenas para usuários que já cadastraram o segredo TOTP, permitindo que contas novas emitam tokens de acesso direto sem segundo fator.
- **Exploração:** O atacante loga com e-mail e senha de um admin recém-criado antes que este configure seu app autenticador, obtendo privilégios imediatos.
- **Impacto:** Comprometimento total da plataforma, vazamento em massa de dados e alteração de regras do sistema.
- **Probabilidade:** Média.
- **Impacto:** Alto (acesso root/admin irrestrito).
- **Princípios Aplicados:** *Secure by default*, *Defesa em profundidade*, *Fail secure*.
- **Decisão de Arquitetura:** Usuários com papéis administrativos (`admin`, `gestor`, `vistoriador`) sem segredo configurado recebem `mfa_setup_required: true` e um `temp_token` (expiração de 5 minutos, escopo restrito a setup). O `access_token` só é gerado após validação bem-sucedida do primeiro código TOTP.
- **Controles Implementados:** Rotas `/auth/mfa/setup-login` e `/auth/mfa/activate-login`, bloqueio no `/auth/login`, validação de janela TOTP (janela ±1 intervalo de 30s).
- **Risco Residual:** Comprometimento do próprio dispositivo do administrador; mitigado por expiração curta de token (15 min) e revogação de MFA por outro admin.

---

### Cenário 3: Adulteração de Laudo Pericial de Vistoria Finalizado (R-03)
- **Ativo:** Laudos de Vistoria e Registros de Aceite (`Checklist` + `ItemChecklist` + `AceiteChecklist`).
- **Propriedades:** Integridade + Autenticidade.
- **Ameaça:** Locador, locatário ou vistoriador com interesses financeiros em fraudar o estado do imóvel.
- **Vulnerabilidade:** Ausência de trava de modificação no backend quando o checklist atinge os status `pendente_aceite` ou `finalizado`.
- **Exploração:** Envio de requisições de alteração para remover avarias registradas ou adicionar danos inexistentes após a entrega das chaves.
- **Impacto:** Perda de validade jurídica do laudo, disputas financeiras e prejuízo reputacional para a imobiliária.
- **Probabilidade:** Baixa.
- **Impacto:** Alto (consequências jurídicas e perda de fé pública).
- **Princípios Aplicados:** *Fail secure*, *Menor privilégio*, *Defesa em profundidade*.
- **Decisão de Arquitetura:** Checklists que saem do status `em_preenchimento` são bloqueados contra edição de itens e fotos. O aceite é vinculado atomicamente ao locatário titular do contrato com registro de data/hora.
- **Controles Implementados:** Máquina de estados no backend com validações pré-mutação, registro imutável em `aceite_checklists`, trilha de auditoria para cada transição.
- **Risco Residual:** Bug na máquina de estados; controlado por suíte de testes de ciclo de vida de checklist.

---

### Cenário 4: Indisponibilidade Administrativa por Auto-exclusão de Conta (R-04)
- **Ativo:** Dados Cadastrais e Acesso de Administradores (`Usuario`).
- **Propriedades:** Disponibilidade + Integridade.
- **Ameaça:** Administrador por descuido ou conta comprometida executando auto-exclusão.
- **Vulnerabilidade:** Endpoint `DELETE /usuarios/{id}` não validar se o ID informado é o mesmo do usuário autenticado no cabeçalho Authorization.
- **Exploração:** O administrador envia seu próprio ID para deleção, resultando na perda imediata de sua própria conta.
- **Impacto:** Perda de acesso administrativo, travamento de processos operacionais e necessidade de intervenção direta no banco.
- **Probabilidade:** Média.
- **Impacto:** Alto (bloqueio de operação).
- **Princípios Aplicados:** *Fail secure*, *Redução da superfície de ataque*.
- **Decisão de Arquitetura:** O backend valida a identidade e rejeita tentativas de auto-desativação com mensagem clara de regra de negócio (`"Não é possível desativar a própria conta"`).
- **Controles Implementados:** Verificação `current.id == usuario_id` no endpoint, testes automatizados cobrindo a rejeição, suporte a soft delete com preservação do registro no banco.
- **Risco Residual:** Exclusão coordenada entre múltiplos administradores; mitigado pela exigência de no mínimo um administrador ativo.

---

### Cenário 5: Injeção ou Contestação de Ações Operacionais (R-05)
- **Ativo:** Logs de Auditoria e Rastreabilidade Operacional (`LogOperacao`).
- **Propriedades:** Integridade + Não-Repúdio.
- **Ameaça:** Operador ou usuário interno executando mutações indevidas e negando a autoria.
- **Vulnerabilidade:** Logs de auditoria registrarem apenas autor e nome da ação sem capturar o endereço IP e os dados modificados (payload).
- **Exploração:** O usuário alega que sua conta foi acessada de outro local ou que os dados não foram enviados por ele, inviabilizando a perícia.
- **Impacto:** Falha em auditorias de segurança, não-conformidade com LGPD e impossibilidade de responsabilização.
- **Probabilidade:** Média.
- **Impacto:** Médio (dano a investigações e resolução de disputas).
- **Princípios Aplicados:** *Defesa em profundidade*, *Rastreabilidade*.
- **Decisão de Arquitetura:** Toda mutação relevante grava compulsoriamente autor, entidade, ID, ação, data/hora UTC, IP de origem e payload JSON no banco de dados em tabela append-only.
- **Controles Implementados:** Tabela `log_operacoes` com colunas `payload` (JSON) e `ip` (String(45)), sem rotas de deleção/edição para usuários.
- **Risco Residual:** Crescimento da tabela de logs; mitigado por planejamento de expurgo/backup histórico a longo prazo.
