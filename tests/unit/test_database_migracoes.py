"""
DEBT-010 — Migrações de ensure_schema_updates num banco antigo

Um banco criado antes das colunas novas (o PHP convertido e as Sprints 11 a 13) ganha cada coluna na
inicialização, sem perder os dados. Aqui o banco antigo é um SQLite temporário com as tabelas mínimas
de antes; o create_all não mexe em tabela que já existe, então só as migrações acrescentam as colunas.
"""

import pytest
from sqlalchemy import create_engine, inspect, text

import app.database as database

ANTIGAS = [
    "CREATE TABLE usuarios (id VARCHAR(36) PRIMARY KEY, cpf VARCHAR(14))",
    "CREATE TABLE enderecos (id VARCHAR(36) PRIMARY KEY)",
    "CREATE TABLE imoveis (id VARCHAR(36) PRIMARY KEY)",
    "CREATE TABLE problemas (id VARCHAR(36) PRIMARY KEY)",
    "CREATE TABLE contratos (id VARCHAR(36) PRIMARY KEY)",
    "CREATE TABLE checklists (id VARCHAR(36) PRIMARY KEY)",
    "CREATE TABLE auth_refresh_tokens (id VARCHAR(36) PRIMARY KEY)",
    "CREATE TABLE log_operacao (id VARCHAR(36) PRIMARY KEY, acao VARCHAR(50), detalhes TEXT)",
]
ESPERADAS = {
    "usuarios": {"mfa_secret_pendente", "token_version"},
    "enderecos": {"latitude", "longitude", "bloco", "andar", "ativo"},
    "imoveis": {"ativo"},
    "problemas": {"comodo_id", "foto_url", "excluido_em", "excluido_por"},
    "contratos": {"excluido_em", "excluido_por"},
    "checklists": {"excluido_em", "excluido_por"},
    "auth_refresh_tokens": {"usado_em"},
    "log_operacao": {"payload", "ip"},
}


@pytest.fixture
def banco_antigo(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'antigo.db'}")
    with engine.begin() as conn:
        for sql in ANTIGAS:
            conn.execute(text(sql))
        conn.execute(text("INSERT INTO usuarios (id, cpf) VALUES ('u1', '529.982.247-25')"))
        conn.execute(text("INSERT INTO log_operacao (id, acao, detalhes) VALUES ('l1', 'login_falho', 'email: x')"))
        # Outros eventos, e um login falho já no formato novo, não são tocados pela limpeza do SEC-019
        conn.execute(text("INSERT INTO log_operacao (id, acao, detalhes) VALUES ('l2', 'update', 'email: alterado')"))
        conn.execute(
            text("INSERT INTO log_operacao (id, acao, detalhes) VALUES ('l3', 'login_falho', 'email_hmac: ab')")
        )
    monkeypatch.setattr(database, "engine", engine)
    yield engine
    engine.dispose()


def _colunas(engine, tabela):
    return {c["name"] for c in inspect(engine).get_columns(tabela)}


def test_banco_antigo_ganha_todas_as_colunas(banco_antigo):
    database.ensure_schema_updates()

    for tabela, colunas in ESPERADAS.items():
        assert colunas <= _colunas(banco_antigo, tabela), tabela


def test_dados_antigos_sao_mantidos_e_migrados(banco_antigo):
    database.ensure_schema_updates()

    from app.cpf_cifrado import cifra

    with banco_antigo.connect() as conn:
        cpf, versao = conn.execute(text("SELECT cpf, token_version FROM usuarios WHERE id = 'u1'")).one()
        detalhes = dict(conn.execute(text("SELECT id, detalhes FROM log_operacao")).all())
    assert cpf.startswith("gAAAAA") and cifra.decifrar(cpf) == "529.982.247-25"  # cifrado (SEC-031)
    assert versao == 0  # o padrão da coluna nova
    # Só o texto digitado no login falho sai (SEC-019)
    assert detalhes == {"l1": None, "l2": "email: alterado", "l3": "email_hmac: ab"}


def test_segunda_execucao_nao_muda_nada(banco_antigo):
    def estado():
        with banco_antigo.connect() as conn:
            dados = {
                "cpf": conn.execute(text("SELECT cpf FROM usuarios WHERE id = 'u1'")).scalar(),
                "logs": conn.execute(text("SELECT id, detalhes FROM log_operacao ORDER BY id")).all(),
            }
        return {t: _colunas(banco_antigo, t) for t in ESPERADAS}, dados

    database.ensure_schema_updates()
    antes = estado()

    database.ensure_schema_updates()

    assert estado() == antes  # nem as colunas nem os dados mudam (o CPF não é cifrado duas vezes)


def test_banco_novo_cria_as_tabelas_que_faltam(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'novo.db'}")
    monkeypatch.setattr(database, "engine", engine)

    database.ensure_schema_updates()

    assert {"usuarios", "contratos", "log_operacao"} <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_get_db_fecha_a_sessao(monkeypatch):
    fechadas = []

    class Sessao:
        def close(self):
            fechadas.append(True)

    monkeypatch.setattr(database, "SessionLocal", Sessao)
    gerador = database.get_db()
    assert isinstance(next(gerador), Sessao)
    gerador.close()
    assert fechadas == [True]
