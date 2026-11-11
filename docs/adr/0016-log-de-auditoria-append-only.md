# ADR-0016: Log de auditoria append-only por trigger no banco

- **Status:** aceito
- **Data:** 2026-11-11
- **Itens relacionados:** SEC-025, R-005, SEC-010 (IP e campos alterados), SEC-014 (retenção)

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
`log_operacao` é a trilha de auditoria: quem fez o quê, quando e de onde (SEC-010). Qualquer conexão da aplicação conseguia alterar ou apagar linhas dela. Um bug, uma injeção de SQL ou alguém com o usuário da aplicação apagaria o rastro de uma ação (R-005; STRIDE R e T). Dois caminhos legítimos precisam apagar logs: a retenção (Marco Civil, `LOG_RETENCAO_DIAS`, no mínimo 180 dias) e o seed com `force` (`SEED_ALLOW_DESTRUCTIVE`), que apaga também os usuários.

## Decisão
Decisão do PO em 2026-11-11.
- **Trigger no banco** (`app/log_append_only.py`):
  - **PostgreSQL:** uma função plpgsql e triggers por comando (`FOR EACH STATEMENT`), `BEFORE UPDATE OR DELETE` e `BEFORE TRUNCATE`;
  - **SQLite:** triggers `BEFORE UPDATE` e `BEFORE DELETE` com `RAISE(ABORT)`;
  - **Criação:** os triggers são criados junto com a tabela (evento `after_create`) e, em bancos já existentes, pela migração da inicialização. A definição tem uma versão (`VERSAO`): a migração só recria o que estiver diferente, então uma inicialização comum não roda DDL nem trava `log_operacao`.
- **Exceção autorizada:** `exclusao_autorizada(conexão, motivo)` grava uma linha em `log_operacao_liberacao` e a apaga antes do commit, na mesma transação.
  - O trigger só deixa passar quando essa linha existe. No PostgreSQL, ela também precisa ter sido gravada pela transação atual (`xmin`): uma linha que tenha ficado gravada por engano não autoriza mais ninguém.
  - A linha sai no fim do bloco, mesmo com erro, e a inicialização apaga qualquer sobra.
  - Usam a exceção: a retenção, o seed com `force`, a limpeza única dos logins falhos antigos (SEC-019) e a limpeza entre testes. O `refresh-data` do seed, que mantém os usuários, mantém também o log.
- **Sem rota** de edição ou exclusão de logs: `GET /logs` é só leitura.
- **Outro banco** (MySQL, por exemplo): a inicialização falha (fail secure), em vez de subir com o log sem proteção.

## Alternativas consideradas
- **Papéis no banco** (a API com um papel só de INSERT e SELECT em `log_operacao`, e a retenção com outro): é mais forte, porque nem a aplicação consegue gravar a liberação. Mas exige criar papéis e uma segunda `DATABASE_URL` no Render, e o plano gratuito pode não permitir.
- **Só na aplicação** (nenhuma função altera logs, com um teste que garante): não protege contra injeção de SQL nem contra quem usa a conexão da aplicação.
- **Encadear os logs por hash:** detecta a alteração, mas não a impede, e precisa de um lugar confiável para guardar a última âncora.

## Consequências
- **Limitação:** quem executa SQL arbitrário com a conexão da aplicação (o dono do banco, ou uma injeção com vários comandos numa transação) consegue gravar a liberação ou desligar o trigger. A proteção é contra o caminho comum da aplicação (ORM, bugs, consultas erradas), não contra quem controla o banco. Esse é o risco residual do R-005, e os papéis no banco são o próximo passo, se ele precisar cair.
- Toda exclusão futura de logs precisa usar `exclusao_autorizada`, e o teste `test_seguranca_log_append_only.py` falha se o trigger sumir.
- A fixture `db` dos testes limpa as tabelas com a mesma autorização.
