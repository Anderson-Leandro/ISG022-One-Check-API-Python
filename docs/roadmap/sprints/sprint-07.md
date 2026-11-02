# Sprint 07 (retroativa)

- **Período:** 2026-08-26 → 2026-09-08 · **Status:** closed
- **Sprint Goal:** MVP completo: paridade com a API PHP e todos os módulos (US-001 a US-014)
- **Comprometido:** 67 pts

> Sprint reconstruída na adoção (02/11/2026) a partir das datas dos commits. Não houve planejamento
> formal na época: o "comprometido" é o que foi entregue, e as estimativas dos itens SEC foram feitas
> depois.

## Itens
| ID | Título | Est. | Seg. | Status |
|---|---|---|---|---|
| US-001 | Autenticar identidade com JWT e refresh | 5 | high | done |
| US-002 | Configurar e validar MFA (TOTP) em papéis críticos | 5 | high | done |
| US-003 | Administrar usuários com papéis e soft delete seguro | 5 | high | done |
| US-004 | Cadastrar imóvel com endereço e geocoding | 5 | medium | done |
| US-005 | Criar e consultar contrato com titularidade | 5 | medium | done |
| US-006 | Agendar vistoria vinculada a contrato ativo | 3 | low | done |
| US-007 | Preencher checklist com itens e fotos | 8 | high | done |
| US-008 | Aceitar ou rejeitar laudo de vistoria | 5 | high | done |
| US-009 | Baixar laudo de vistoria em PDF | 5 | medium | done |
| US-010 | Registrar problema com foto e linha do tempo | 5 | medium | done |
| US-011 | Consultar dashboard operacional | 3 | medium | done |
| US-012 | Isolar cômodos do imóvel com CRUD protegido | 3 | low | done |
| US-013 | Encerrar ou cancelar contrato liberando imóvel | 3 | low | done |
| US-014 | Enviar checklist para aceite formal | 3 | medium | done |
| TK-010 | Baseline de segurança, riscos iniciais e arquitetura v1 | 3 | low | done |
| TK-011 | README com a documentação dos módulos e endpoints | 1 | none | done |

## Sprint Review (retroativa)
- **Incremento:** paridade com a API PHP (auth, MFA, usuários, imóveis com geocoding), contratos, agendamentos, checklists com aceite e PDF, problemas com notificações, dashboard e logs.
- **Goal atingido?** sim. As histórias US-001 a US-014 estão implementadas e testadas.
- **Evidências:** commits `5c7decd`, `c6a7cae`, `f68c812` (03/09) e `ee20607` a `69d7dcb` (07/09); PRs #1 a #9; baseline de segurança `fbaf99e`; README `e85e0df`.
- **Checagem de segurança:** baseline e riscos iniciais (TK-010). Os problemas encontrados depois (N1–N8, SEC-001 a SEC-016) nasceram nesta entrega.

## Observação sobre a velocity
Os 67 pontos não são um ritmo normal. Grande parte do código já existia desde a Sprint 1 e foi portado da API PHP.
