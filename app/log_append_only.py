"""Log de auditoria append-only (SEC-025, ADR-0016).

Um trigger no banco recusa UPDATE e DELETE em log_operacao (e TRUNCATE, no PostgreSQL) vindos do caminho
comum da aplicação: o ORM, um bug, uma consulta montada errada. A única exceção é uma transação que se
declara autorizada, gravando uma linha em log_operacao_liberacao antes de apagar: a rotina de retenção
(Marco Civil, LOG_RETENCAO_DIAS) e o seed destrutivo com `force`.

A autorização vale só para a transação que a grava:
- no PostgreSQL, o trigger confere que a linha foi gravada pela transação atual (xmin), então uma linha
  que tenha ficado gravada por engano não autoriza mais ninguém;
- nos dois bancos, a linha sai no fim do bloco, mesmo com erro, e a inicialização apaga qualquer sobra.

Limitação (ADR-0016): quem tem a conexão da aplicação e executa SQL arbitrário (o dono do banco, ou uma
injeção com vários comandos) consegue gravar a liberação ou desligar o trigger. A proteção é contra o
caminho comum da aplicação e contra erros, não contra quem controla o banco.

Banco sem suporte (nem PostgreSQL nem SQLite): a inicialização falha (fail secure).
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import delete, event, insert, text

from app.models import LiberacaoLog, LogOperacao, new_uuid

# Sobe quando a definição dos triggers muda: a migração só recria o que estiver numa versão diferente
VERSAO = "sec-025-v2"

_SQLITE = {
    "log_operacao_sem_update": """CREATE TRIGGER log_operacao_sem_update BEFORE UPDATE ON log_operacao
    WHEN NOT EXISTS (SELECT 1 FROM log_operacao_liberacao)
    BEGIN SELECT RAISE(ABORT, 'log_operacao e append-only, UPDATE recusado (SEC-025)'); END""",
    "log_operacao_sem_delete": """CREATE TRIGGER log_operacao_sem_delete BEFORE DELETE ON log_operacao
    WHEN NOT EXISTS (SELECT 1 FROM log_operacao_liberacao)
    BEGIN SELECT RAISE(ABORT, 'log_operacao e append-only, DELETE recusado (SEC-025)'); END""",
}

# Por comando (FOR EACH STATEMENT): a conferência roda uma vez, e não uma vez por linha apagada.
# xmin da linha de liberação = transação atual (os 32 bits baixos do txid_current)
_POSTGRES = [
    """CREATE OR REPLACE FUNCTION log_operacao_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM log_operacao_liberacao WHERE xmin::text = (txid_current() % 4294967296)::text
      ) THEN
        RETURN NULL;
      END IF;
      RAISE EXCEPTION 'log_operacao e append-only, % recusado (SEC-025)', TG_OP;
    END $$""",
    f"COMMENT ON FUNCTION log_operacao_append_only() IS '{VERSAO}'",
    "DROP TRIGGER IF EXISTS log_operacao_sem_alteracao ON log_operacao",
    """CREATE TRIGGER log_operacao_sem_alteracao BEFORE UPDATE OR DELETE ON log_operacao
    FOR EACH STATEMENT EXECUTE FUNCTION log_operacao_append_only()""",
    "DROP TRIGGER IF EXISTS log_operacao_sem_truncate ON log_operacao",
    """CREATE TRIGGER log_operacao_sem_truncate BEFORE TRUNCATE ON log_operacao
    FOR EACH STATEMENT EXECUTE FUNCTION log_operacao_append_only()""",
]


def _postgres_na_versao(conn) -> bool:
    versao = conn.execute(
        text("SELECT obj_description(p.oid, 'pg_proc') FROM pg_proc p WHERE p.proname = 'log_operacao_append_only'")
    ).scalar()
    gatilhos = conn.execute(
        text(
            "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN "
            "('log_operacao_sem_alteracao', 'log_operacao_sem_truncate')"
        )
    ).scalar()
    return versao == VERSAO and gatilhos == 2


def instalar(conn) -> bool:
    """Cria ou atualiza os triggers e apaga sobras de liberação. Sem DDL quando já estão na versão atual.

    Levanta RuntimeError num banco sem suporte: o log não pode ficar sem a proteção sem ninguém saber."""
    dialeto = conn.dialect.name
    if dialeto not in ("sqlite", "postgresql"):
        raise RuntimeError(
            f"SEC-025: o log de auditoria append-only só tem trigger no PostgreSQL e no SQLite (banco: {dialeto})."
        )
    # A tabela de liberação pode ainda não existir quando o create_all cria log_operacao
    LiberacaoLog.__table__.create(conn, checkfirst=True)
    # Uma liberação que tenha ficado gravada não pode valer para as próximas transações
    conn.execute(delete(LiberacaoLog))
    if dialeto == "postgresql":
        if not _postgres_na_versao(conn):
            for sql in _POSTGRES:
                conn.execute(text(sql))
        return True
    for nome, sql in _SQLITE.items():
        atual = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = :nome"), {"nome": nome}
        ).scalar()
        if atual != sql:
            conn.execute(text(f"DROP TRIGGER IF EXISTS {nome}"))
            conn.execute(text(sql))
    return True


@event.listens_for(LogOperacao.__table__, "after_create")
def _ao_criar_a_tabela(_tabela, conn, **_):
    instalar(conn)


@contextmanager
def exclusao_autorizada(alvo, motivo: str) -> Iterator[None]:
    """Autoriza UPDATE e DELETE em log_operacao só dentro desta transação (Session ou Connection).

    Sem commit aqui: quem chama confirma. A linha de liberação sai no fim do bloco, mesmo se ele falhar.
    Numa transação já abortada (PostgreSQL), a remoção falha, e o rollback a desfaz."""
    alvo.execute(insert(LiberacaoLog).values(id=new_uuid(), motivo=motivo))
    try:
        yield
    finally:
        try:
            alvo.execute(delete(LiberacaoLog))
        except Exception:  # noqa: BLE001 - transação abortada: o commit também falha, e o rollback limpa
            pass
