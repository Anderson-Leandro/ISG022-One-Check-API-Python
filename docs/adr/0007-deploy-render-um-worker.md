# ADR-0007: Deploy no Render com uma instância e um worker

- **Status:** aceito (registro retroativo; decisão tomada em 2026-06, com o limite de tentativas acrescentado em 2026-10-25)
- **Data:** 2026-11-08
- **Itens relacionados:** DEBT-009, SEC-034, TK-002, TK-003, R-008, R-012, R-017

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
O projeto é acadêmico, mantido por um time pequeno e sem orçamento. Precisa de um ambiente público com HTTPS e PostgreSQL gerenciado, que suba direto do GitHub. O tráfego esperado é baixo (demonstrações e testes).

## Opções consideradas
1. **Render, plano gratuito: um web service e um Postgres** (`render.yaml`).
   - Prós: grátis; HTTPS e Postgres gerenciados; deploy a cada push; blueprint versionado.
   - Contras: uma instância pequena, que adormece sem uso; disco efêmero; Postgres gratuito com prazo de validade.
2. **Render ou outro PaaS em plano pago, com várias instâncias.**
   - Prós: escala e disco persistente.
   - Contras: custo mensal sem demanda que o justifique.
3. **VPS própria com Docker Compose.**
   - Prós: controle total; o mesmo compose do desenvolvimento.
   - Contras: o time passa a cuidar de sistema operacional, TLS, backup e atualizações.

## Decisão
Vamos usar a **opção 1**:
- **Processo:** `start.sh` sobe `uvicorn app.main:app` **sem `--workers`**, ou seja, um processo só, numa instância.
- **Build:** `pip install --require-hashes -r requirements.lock`; health check em `/api/v1/health`.
- **Configuração:** `JWT_SECRET` gerado pelo Render; `SEED_SECRET`, `CORS_ORIGINS` e `PUBLIC_BASE_URL` definidos no painel (`sync: false`); o IP do cliente vem do item que o proxy do Render acrescenta ao `X-Forwarded-For` (`PROXY_SALTOS=1`). Até 2026-11-10 era `FORWARDED_ALLOW_IPS="*"`, que aceitava o IP escrito pelo cliente (SEC-017, ADR-0015).
- **Estado em memória permitido.** Com um processo só, o **limite de tentativas** de login, MFA e reautenticação fica na memória (`app/rate_limit.py`), sem Redis nem tabela. O teto de 10.000 chaves descarta as expiradas para a memória não crescer sem limite (SEC-034).

## Consequências
- **Positivas:**
  - nenhum custo de hospedagem;
  - o limitador não depende de outro serviço e responde em microssegundos.
- **Negativas / custos:**
  - um reinício ou deploy zera os contadores do limitador;
  - a instância gratuita adormece sem tráfego; a primeira requisição depois disso demora;
  - o disco é efêmero: as fotos gravadas em `UPLOAD_DIR` se perdem a cada reinício (ADR-0006, R-017).
- **Segurança:**
  - **com mais de um worker ou instância, o limite efetivo se multiplica**, porque cada processo conta à parte. Risco R-012, aceito enquanto o deploy for de um worker; ao mudar o plano ou o número de workers, o contador precisa ir para Redis ou para o banco antes;
  - o IP do limite por IP vem do `X-Forwarded-For`; se o cliente conseguir forjá-lo, escapa do limite por IP, mas não do limite por conta (R-008).
