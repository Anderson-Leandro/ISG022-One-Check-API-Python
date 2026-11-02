# ADR-0002: Stack da API — FastAPI, SQLAlchemy 2 e PostgreSQL

- **Status:** aceito (registro retroativo; decisão tomada em 2026-06 e revista nas correções de segurança de 2026-10)
- **Data:** 2026-11-02
- **Itens relacionados:** EP-001 a EP-008, SEC-006, SEC-008

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
A OneCheck tinha uma API em PHP. A versão em Python precisava manter a paridade de dados e de fluxos com a anterior (commit `5c7decd`) e expor uma API REST para o front web e o mobile. Também precisava ter validação de entrada forte, documentação OpenAPI e testes automatizados.

## Opções consideradas
1. **FastAPI + SQLAlchemy 2 + PostgreSQL.** Prós: validação por Pydantic, OpenAPI automático, injeção de dependências usada para autenticação e autorização (`app/deps.py`), ORM com consultas parametrizadas, Postgres gerenciado no Render. Contras: o ecossistema assíncrono pede cuidado com bibliotecas síncronas.
2. **Django + DRF.** Prós: admin, autenticação e migrações prontos. Contras: mais pesado e com mais convenções do que o escopo pede; a paridade com a API PHP ficaria mais trabalhosa.
3. **Flask.** Prós: simples. Contras: validação, OpenAPI e injeção de dependências teriam de ser montadas à mão.

## Decisão
Vamos usar a opção 1, com estas peças:
- Python 3.12, FastAPI 0.162 e SQLAlchemy 2.0;
- PostgreSQL 16 em produção, e SQLite para desenvolvimento local e testes rápidos;
- PyJWT (HS256) para os tokens, bcrypt para as senhas e pyotp para o TOTP;
- Pillow 13 para validar as imagens;
- uvicorn com um worker;
- Docker e Docker Compose localmente, Render em produção.

As dependências são instaladas pelo `requirements.lock`, com hashes (`--require-hashes`).

## Consequências
- **Positivas:** a validação de entrada e a autorização ficam centralizadas e testáveis (824 testes); o OpenAPI serve ao front.
- **Negativas / custos:**
  - as rotas que leem o corpo com `request.json()` ficam fora do OpenAPI (DEBT-001);
  - não há Alembic: as colunas novas entram por `ensure_schema_updates` (`app/database.py`).
- **Segurança:**
  - o ORM evita SQL injection;
  - o `python-jose`, que tinha CVEs críticas, foi trocado pelo PyJWT (SEC-006);
  - com um único worker, o limite de tentativas pode ficar em memória (risco aceito R-012).
