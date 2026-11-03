# Visão do Produto — OneCheck API

> **Por que isso importa:** a visão é o filtro de todas as decisões. Quando surgir uma ideia nova,
> pergunte "isso aproxima o produto desta visão?". Se não, vai para o fim do backlog ou é descartada.

Projeto da disciplina ISG-022 (Segurança no Desenvolvimento de Aplicações), FATEC Mauá, DSM, 2026/2. Esta visão consolida o Product Goal de [`docs/product-backlog.md`](../product-backlog.md).

## Problema
A vistoria de entrada e saída de um imóvel alugado costuma ser feita em papel ou em planilhas soltas, e as fotos ficam espalhadas. Na devolução das chaves, locatário e imobiliária discordam do estado do imóvel, e falta prova de quem registrou o quê e quando. Isso gera disputas sobre caução e reparos.

## Usuários e perfis
| Perfil | Quem é | O que precisa fazer | Nível de acesso |
|---|---|---|---|
| Administrador | equipe de TI ou dono da imobiliária | gerenciar usuários, MFA, auditoria e operação completa | total; MFA obrigatório |
| Gestor | operação da imobiliária | operar imóveis, contratos, agendamentos e problemas | carteira operacional; não gerencia admin/gestor; MFA obrigatório |
| Vistoriador | técnico de campo | preencher checklists com fotos e submeter vistorias | só contratos em que tem vistoria; MFA obrigatório |
| Locatário | inquilino | consultar o próprio contrato, aceitar ou rejeitar o laudo, abrir problemas | só recursos do próprio contrato |
| Visualizador | consulta interna | ler a operação | leitura (alcance em decisão: SPK-001) |
| Sistemas externos | ViaCEP e Nominatim | completar endereço e coordenadas | só consulta, com timeout |

## Proposta de valor
Para imobiliárias e locatários que precisam registrar o estado de um imóvel sem gerar disputa, a OneCheck API é um backend de vistorias que guarda laudos com fotos, aceite formal do locatário e trilha de auditoria. O controle de acesso é feito no servidor, por perfil e por titularidade do contrato.

## Objetivos e métricas de sucesso
| Objetivo | Como medir | Meta |
|---|---|---|
| Laudo com valor de prova | checklist imutável depois do envio, aceite com data e autor | 100% dos laudos aceitos sem edição posterior (testes de ciclo de vida) |
| Nenhum acesso indevido entre clientes | testes de cenário negado por perfil e por dono | um teste negado por rota de leitura por ID |
| Segurança verificável | auditorias `/security-audit` | 0 achados críticos, altos ou médios em aberto |
| Qualidade contínua | CI com testes e cobertura | ≥ 90% de cobertura, CI verde na `main` |

## Escopo do MVP
- Autenticação JWT com refresh rotativo, MFA TOTP por perfil e gestão de usuários.
- Imóveis com endereço, geocoding e cômodos.
- Contratos, encerramento e cancelamento, e agendamento de vistorias.
- Checklists com itens e fotos, envio para aceite, aceite/rejeição e laudo em PDF.
- Problemas com fotos, linha do tempo e notificações.
- Dashboard por perfil e consulta da trilha de auditoria.
- Até a entrega final: fotos com URL assinada (SEC-026), se o prazo permitir. Anexos de contrato (US-016) ficaram fora das sprints e entram só se sobrar tempo.

## Fora de escopo (por enquanto)
- Pagamentos e cobrança do aluguel.
- Front-end: fica em outro repositório (React).

## Restrições
- **Prazo:** entrega final em 11/12/2026 (semestre letivo 2026/2).
- **Hospedagem:** Render, plano gratuito, com 1 instância e 1 worker; o limite de tentativas fica em memória.
- **Stack:** Python 3.12, FastAPI, SQLAlchemy e PostgreSQL (ADR-0002).
- **Repositório público:** nenhum segredo ou dado real versionado.
- **Conformidade:** LGPD, porque há nome, e-mail, CPF, endereço e IP.

## Dados e ativos sensíveis (primeira visão)
Credenciais (hash de senha, segredo TOTP, refresh tokens), segredos da aplicação, dados pessoais de usuários (nome, e-mail, CPF), endereços dos imóveis, laudos, fotos e aceites, e a trilha de auditoria (IP). O detalhe está em [`docs/risks/asset-inventory.md`](../risks/asset-inventory.md).
