"""
SEC-019 — O login falho não grava o texto digitado no campo e-mail

Antes, o log guardava "email: <o que foi digitado>": quem digitava a senha no campo e-mail por engano
deixava a senha em log_operacao, visível em GET /logs até a retenção (SEC-014).
- Conta existente (ativa ou não): o log leva o id da conta (usuario_id e entidade_id), e nada do texto.
- Conta inexistente: só um HMAC do e-mail normalizado, com o segredo do servidor. Nem o domínio vai,
  porque uma senha como "Joao@Casa.net" deixaria metade dela no log.
- Os registros antigos com o texto digitado são limpos na inicialização.
"""

import pytest
from sqlalchemy import text

from app.auditoria import email_para_log
from app.models import LogOperacao
from tests.conftest import TEST_SENHA, auth

LOGIN = "/api/v1/auth/login"


def _falhas(db):
    db.expire_all()
    return db.query(LogOperacao).filter(LogOperacao.acao == "login_falho").all()


def test_conta_existente_grava_o_id_da_conta_e_nao_o_email(client, db, user_locatario):
    client.post(LOGIN, json={"email": user_locatario.email, "senha": "errada"})

    [log] = _falhas(db)
    assert (log.usuario_id, log.entidade, log.entidade_id) == (user_locatario.id, "usuario", user_locatario.id)
    assert log.detalhes is None


def test_filtro_por_usuario_acha_as_tentativas_contra_a_conta(client, db, user_locatario, token_admin):
    client.post(LOGIN, json={"email": user_locatario.email, "senha": "errada"})
    r = client.get(
        "/api/v1/logs", params={"usuario_id": user_locatario.id, "acao": "login_falho"}, headers=auth(token_admin)
    )
    assert [l["entidade_id"] for l in r.json()["dados"]] == [user_locatario.id]


def test_conta_desativada_tambem_grava_o_id_e_nao_entra(client, db, user_locatario):
    user_locatario.ativo = False
    db.flush()
    r = client.post(LOGIN, json={"email": user_locatario.email, "senha": TEST_SENHA})

    assert r.status_code == 401
    [log] = _falhas(db)
    assert log.entidade_id == user_locatario.id


@pytest.mark.parametrize(
    "digitado",
    ["ninguem@exemplo.com.br", "MinhaSenha#2026", "Joao@Casa.net", "p4ss@minha.senha.io", "a@b@c.com"],
)
def test_conta_inexistente_grava_so_o_hmac(client, db, digitado):
    client.post(LOGIN, json={"email": digitado, "senha": "qualquer"})

    [log] = _falhas(db)
    assert log.detalhes == f"email_hmac: {email_para_log(digitado)}"
    assert (log.usuario_id, log.entidade_id) == (None, None)
    for parte in digitado.lower().replace("@", " ").replace(".", " ").split():
        if len(parte) > 2:
            assert parte not in log.detalhes.lower()


def test_hmac_junta_o_mesmo_email_e_separa_os_diferentes():
    assert email_para_log(" Ninguem@Exemplo.com ") == email_para_log("ninguem@exemplo.com")
    assert email_para_log("ninguem@exemplo.com") != email_para_log("outro@exemplo.com")
    assert len(email_para_log("x" * 100_000)) == 16


def test_resposta_do_login_falho_nao_muda(client, user_locatario):
    existente = client.post(LOGIN, json={"email": user_locatario.email, "senha": "errada"})
    inexistente = client.post(LOGIN, json={"email": "ninguem@exemplo.com", "senha": "errada"})
    assert existente.status_code == inexistente.status_code == 401
    assert existente.json() == inexistente.json()


def test_inicializacao_limpa_o_texto_digitado_nos_logs_antigos(db):
    from app.database import engine, ensure_schema_updates

    db.add_all(
        [
            LogOperacao(acao="login_falho", entidade="usuario", detalhes="email: MinhaSenha#2026"),
            LogOperacao(acao="login_falho", entidade="usuario", detalhes="email_hmac: 0123456789abcdef"),
            LogOperacao(acao="update", entidade="usuario", detalhes="email: alterado@exemplo.com"),
        ]
    )
    db.commit()

    ensure_schema_updates()

    with engine.connect() as conn:
        linhas = conn.execute(text("SELECT acao, detalhes FROM log_operacao ORDER BY acao, detalhes")).all()
    assert ("login_falho", "email: MinhaSenha#2026") not in linhas
    assert ("login_falho", "email_hmac: 0123456789abcdef") in linhas
    assert ("update", "email: alterado@exemplo.com") in linhas
