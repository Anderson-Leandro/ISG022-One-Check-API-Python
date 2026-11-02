# Inventário de Ativos — OneCheck API

> **Por que isso importa:** não dá para proteger o que não se sabe que existe. Cada ativo tem
> propriedades de segurança diferentes (C = confidencialidade, I = integridade, D = disponibilidade,
> A = autenticidade). A importância de cada uma guia os controles.

Levantado em 2026-11-02 a partir dos modelos (`app/models.py`), do mapa de funcionalidades e do [modelo de ameaças](../security/threat-model.md).

| ID | Ativo | Tipo | Onde fica | Dono | C | I | D | A | Dados pessoais? | Observações |
|---|---|---|---|---|---|---|---|---|---|---|
| A-01 | Credenciais de usuários: `senha_hash`, `mfa_secret`, `mfa_secret_pendente`, `token_version` | dado | `usuarios` | Anderson Mendes Leandro | alta | alta | média | alta | sim | bcrypt; o segredo TOTP fica em texto no banco; nunca vai em resposta nem em log |
| A-02 | Refresh tokens | dado | `auth_refresh_tokens` | Anderson Mendes Leandro | alta | alta | baixa | alta | não | só o hash SHA-256; rotacionado a cada refresh; apagado quando vence (SEC-014). Reuso ainda não é detectado (SEC-027) |
| A-03 | Dados pessoais de usuários: nome, e-mail, CPF | dado | `usuarios` | Anderson Mendes Leandro | alta | média | média | média | sim | CPF validado e mascarado nas respostas, em texto no banco (SEC-031); direitos do titular pendentes (SEC-028) |
| A-04 | Segredos da aplicação: `JWT_SECRET`, `SEED_SECRET`, `DATABASE_URL`, `POSTGRES_PASSWORD` | configuração/segredo | variáveis de ambiente (Render, `.env` local) | Anderson Mendes Leandro | alta | alta | média | alta | não | obrigatórios e fortes fora de dev; fora do git |
| A-05 | Endereços e coordenadas dos imóveis | dado | `enderecos` | Anderson Mendes Leandro | média | média | baixa | baixa | sim (indireto: endereço do locatário) | acesso por perfil e titularidade (`assert_acesso_imovel`) |
| A-06 | Contratos: locatário, imóvel, datas, status | dado | `contratos` | Anderson Mendes Leandro | média | alta | média | média | sim (vínculo pessoa–imóvel) | âncora de toda a autorização por dono |
| A-07 | Laudos: checklists, itens, aceites e PDF | evidência | `checklists`, `checklist_itens`, `aceite_checklists` | Anderson Mendes Leandro | média | alta | média | alta | sim | imutável depois do envio; aceite só do titular, com data e hora |
| A-08 | Fotos de vistoria e de problemas | evidência/arquivo | `UPLOAD_DIR` (volume) | Anderson Mendes Leandro | média | alta | média | média | sim (interior da casa) | servidas sem login, com nome aleatório de 128 bits (T-14, SPK-002) |
| A-09 | Problemas e atualizações (texto livre) | dado | `problemas`, `atualizacoes_problema` | Anderson Mendes Leandro | média | média | baixa | média | sim (pode conter qualquer coisa) | acesso só de admin/gestor e do locatário dono |
| A-10 | Trilha de auditoria: autor, ação, IP, campos alterados | dado | `log_operacao` | Anderson Mendes Leandro | média | alta | média | alta | sim (IP, e-mail digitado no login) | retenção de `LOG_RETENCAO_DIAS`; não é append-only (SEC-025); IP depende do proxy (SEC-017) |
| A-11 | Código-fonte, CI e imagem Docker | código | GitHub (público), GitHub Actions | Anderson Mendes Leandro | baixa | alta | média | alta | não | lockfile com hashes, actions por SHA, container sem root |
| A-12 | Banco PostgreSQL e backups | infraestrutura | Render (gerenciado) e volume local `api-python_pgdata` | Anderson Mendes Leandro | alta | alta | alta | média | sim | backup e restauração não testados (TK-005) |
| A-13 | Disponibilidade da API | serviço | Render (1 instância, 1 worker) | Anderson Mendes Leandro | — | média | média | — | não | limite de corpo e de tentativas; plano gratuito hiberna |
| A-14 | Serviços externos ViaCEP e Nominatim | serviço externo | internet | terceiros | baixa | média | baixa | baixa | não (CEP) | timeout de 5 s e fallback sem coordenadas |

Tipos: dado, serviço/API, código, configuração/segredo, infraestrutura, pessoa/processo.
