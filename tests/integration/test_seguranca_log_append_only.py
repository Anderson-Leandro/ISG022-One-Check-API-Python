"""
Segurança — SEC-025: log de auditoria append-only

Cenário original: qualquer conexão da aplicação com o banco conseguia alterar ou apagar linhas de
log_operacao. Um bug, uma injeção de SQL ou um operador com o usuário da aplicação podia apagar o
rastro de uma ação (R-005, STRIDE R e T).

Regras verificadas (decisão do PO em 2026-11-11, ADR-0016):
  - UPDATE e DELETE em log_operacao são recusados pelo banco (trigger), venham de onde vierem
  - no PostgreSQL, TRUNCATE também é recusado
  - a rotina de retenção (Marco Civil, LOG_RETENCAO_DIAS) e o seed com force apagam com a autorização
    da própria transação; a autorização não sobra depois do commit, nem quando quem chama captura uma
    falha e confirma; no PostgreSQL, uma liberação que tenha ficado gravada não autoriza outra transação
  - o refresh-data do seed mantém o log (os usuários continuam)
  - banco sem suporte: a inicialização falha (fail secure)
  - instalar os triggers de novo (a cada inicialização) não falha
  - não existe rota de edição ou exclusão de logs
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.log_append_only import exclusao_autorizada, instalar
from app.main import app
from app.models import LiberacaoLog, LogOperacao
from app.retencao import limpar_dados_vencidos
from tests.conftest import test_engine


def _log(db, **kw) -> LogOperacao:
    log = LogOperacao(acao="login", entidade="usuario", ip="10.0.0.1", **kw)
    db.add(log)
    db.commit()
    return log


class TestBancoRecusa:
    def test_update_e_recusado_e_o_log_nao_muda(self, db):
        log = _log(db)
        with pytest.raises(DBAPIError):
            db.execute(text("UPDATE log_operacao SET ip = '1.2.3.4' WHERE id = :id"), {"id": log.id})
            db.commit()
        db.rollback()
        db.expire_all()
        assert db.get(LogOperacao, log.id).ip == "10.0.0.1"

    def test_update_pelo_orm_tambem_e_recusado(self, db):
        log = _log(db)
        log.acao = "forjado"
        with pytest.raises(DBAPIError):
            db.commit()
        db.rollback()

    def test_delete_e_recusado_e_o_log_continua(self, db):
        log = _log(db)
        with pytest.raises(DBAPIError):
            db.execute(text("DELETE FROM log_operacao WHERE id = :id"), {"id": log.id})
            db.commit()
        db.rollback()
        assert db.get(LogOperacao, log.id) is not None

    @pytest.mark.skipif(test_engine.dialect.name != "postgresql", reason="TRUNCATE só existe no PostgreSQL")
    def test_truncate_e_recusado(self, db):
        _log(db)
        with pytest.raises(DBAPIError):
            db.execute(text("TRUNCATE log_operacao"))
            db.commit()
        db.rollback()
        assert db.query(LogOperacao).count() == 1


class TestExclusaoAutorizada:
    def test_retencao_apaga_os_vencidos_e_mantem_os_recentes(self, db):
        antigo = _log(db, created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10_000)).id
        recente = _log(db).id
        assert limpar_dados_vencidos(db)["logs"] == 1
        db.expire_all()
        assert db.get(LogOperacao, antigo) is None
        assert db.get(LogOperacao, recente) is not None

    def test_a_autorizacao_nao_sobra_depois_do_commit(self, db):
        vencido = _log(db, created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10_000)).id
        limpar_dados_vencidos(db)
        assert db.query(LiberacaoLog).count() == 0
        outro = _log(db)
        with pytest.raises(DBAPIError):
            db.execute(text("DELETE FROM log_operacao WHERE id = :id"), {"id": outro.id})
            db.commit()
        db.rollback()
        assert db.get(LogOperacao, vencido) is None
        assert db.get(LogOperacao, outro.id) is not None

    def test_falha_dentro_da_autorizacao_nao_deixa_a_liberacao(self, db):
        _log(db)
        with pytest.raises(RuntimeError):
            with exclusao_autorizada(db, "teste"):
                raise RuntimeError("falhou no meio")
        db.rollback()
        assert db.query(LiberacaoLog).count() == 0

    def test_instalar_de_novo_nao_falha(self, db):
        with test_engine.begin() as conn:
            assert instalar(conn)
            assert instalar(conn)
        log = _log(db)
        with pytest.raises(DBAPIError):
            db.execute(text("DELETE FROM log_operacao WHERE id = :id"), {"id": log.id})
            db.commit()
        db.rollback()


class TestLiberacaoNaoVaza:
    def test_quem_captura_a_falha_e_confirma_nao_deixa_a_liberacao(self, db):
        try:
            with exclusao_autorizada(db, "teste"):
                raise ValueError("capturado por quem chama")
        except ValueError:
            pass
        db.commit()
        assert db.query(LiberacaoLog).count() == 0

    def test_inicializacao_apaga_liberacao_que_ficou_gravada(self, db):
        db.add(LiberacaoLog(motivo="esquecida"))
        db.commit()
        with test_engine.begin() as conn:
            instalar(conn)
        assert db.query(LiberacaoLog).count() == 0

    @pytest.mark.skipif(test_engine.dialect.name != "postgresql", reason="xmin só existe no PostgreSQL")
    def test_liberacao_gravada_por_outra_transacao_nao_autoriza(self, db):
        db.add(LiberacaoLog(motivo="esquecida"))
        db.commit()
        log = _log(db)
        with pytest.raises(DBAPIError):
            db.execute(text("DELETE FROM log_operacao WHERE id = :id"), {"id": log.id})
            db.commit()
        db.rollback()
        db.query(LiberacaoLog).delete()
        db.commit()


class TestSeed:
    def test_refresh_data_mantem_o_log(self, db, user_admin):
        from app.seed_service import _clear_data_keep_users

        log = _log(db).id
        _clear_data_keep_users(db)
        db.expire_all()
        assert db.get(LogOperacao, log) is not None


class TestBancoSemSuporte:
    def test_outro_banco_recusa_a_inicializacao(self):
        class _Dialeto:
            name = "mysql"

        class _Conexao:
            dialect = _Dialeto()

            def execute(self, _sql):
                raise AssertionError("não devia executar nada")

        with pytest.raises(RuntimeError, match="SEC-025"):
            instalar(_Conexao())


class TestSemRotaDeEdicao:
    def test_logs_so_tem_leitura(self):
        # pelo OpenAPI: app.routes não mostra as rotas dos roteadores incluídos nesta versão do FastAPI
        paths = app.openapi()["paths"]
        metodos = {m for caminho, ops in paths.items() if "/logs" in caminho for m in ops}
        assert metodos == {"get"}
