"""
Segurança — SEC-027: refresh token já trocado e reutilizado encerra todas as sessões (ADR-0004, R-011)

A rotação apagava o refresh usado: quem roubasse um refresh e o usasse antes do dono ganhava uma sessão
paralela, e o reuso pelo dono só falhava. Agora o refresh trocado fica marcado como usado; reenviá-lo é
sinal de roubo, e a API nega, encerra todas as sessões do usuário e registra o evento na auditoria.
"""

from app.models import LogOperacao, RefreshToken, Usuario
from tests.conftest import TEST_SENHA, auth

API = "/api/v1"


def _login(client, email):
    r = client.post(f"{API}/auth/login", json={"email": email, "senha": TEST_SENHA})
    assert r.status_code == 200, r.text
    return r.json()["dados"]


def _refresh(client, token):
    return client.post(f"{API}/auth/refresh", json={"refresh_token": token})


def test_uso_legitimo_um_refresh_por_vez_continua_funcionando(client, user_locatario):
    sessao = _login(client, user_locatario.email)
    for _ in range(3):
        r = _refresh(client, sessao["refresh_token"])
        assert r.status_code == 200, r.text
        sessao = r.json()["dados"]
    assert client.get(f"{API}/usuarios/me", headers=auth(sessao["access_token"])).status_code == 200


def test_reuso_de_refresh_trocado_nega_e_encerra_todas_as_sessoes(client, db, user_locatario):
    roubado = _login(client, user_locatario.email)["refresh_token"]
    dono = _refresh(client, roubado).json()["dados"]  # o dono troca primeiro
    outra = _login(client, user_locatario.email)  # outra sessão do mesmo usuário

    r = _refresh(client, roubado)  # o atacante reenvia o trocado

    assert r.status_code == 401, r.text
    assert r.json()["erro"] == "Refresh token inválido ou expirado"
    assert "access_token" not in r.text
    for sessao in (dono, outra):
        assert client.get(f"{API}/usuarios/me", headers=auth(sessao["access_token"])).status_code == 401
        assert _refresh(client, sessao["refresh_token"]).status_code == 401
    db.expire_all()
    assert db.query(RefreshToken).filter(RefreshToken.usuario_id == user_locatario.id).count() == 0


def test_reuso_fica_na_auditoria(client, db, user_locatario):
    roubado = _login(client, user_locatario.email)["refresh_token"]
    _refresh(client, roubado)
    _refresh(client, roubado)
    db.expire_all()
    eventos = db.query(LogOperacao).filter(LogOperacao.acao == "refresh_reutilizado").all()
    assert [(e.usuario_id, e.entidade_id) for e in eventos] == [(user_locatario.id, user_locatario.id)]


def test_reuso_nao_afeta_outro_usuario(client, db, user_locatario, user_locatario_2):
    alheia = _login(client, user_locatario_2.email)
    roubado = _login(client, user_locatario.email)["refresh_token"]
    _refresh(client, roubado)
    _refresh(client, roubado)
    assert client.get(f"{API}/usuarios/me", headers=auth(alheia["access_token"])).status_code == 200


def test_refresh_desconhecido_continua_401_sem_encerrar_nada(client, db, user_locatario):
    sessao = _login(client, user_locatario.email)
    antes = db.get(Usuario, user_locatario.id).token_version
    assert _refresh(client, "token-que-nunca-existiu").status_code == 401
    db.expire_all()
    assert db.get(Usuario, user_locatario.id).token_version == antes
    assert client.get(f"{API}/usuarios/me", headers=auth(sessao["access_token"])).status_code == 200


def test_pedidos_simultaneos_so_um_recebe_o_par_novo(client, db, user_locatario):
    """A troca é atômica: o segundo pedido com o mesmo token vê o token já marcado e cai no reuso."""
    from app.auth import trocar_refresh_token

    roubado = _login(client, user_locatario.email)["refresh_token"]
    primeiro, _ = trocar_refresh_token(db, roubado)
    segundo, _ = trocar_refresh_token(db, roubado)
    assert (primeiro, segundo) == ("ok", "reuso")


def test_refresh_trocado_e_vencido_nao_encerra_as_sessoes(client, db, user_locatario):
    from datetime import datetime, timedelta

    roubado = _login(client, user_locatario.email)["refresh_token"]
    atual = _refresh(client, roubado).json()["dados"]
    db.query(RefreshToken).filter(RefreshToken.usado_em.isnot(None)).update(
        {RefreshToken.expires_at: datetime.now() - timedelta(days=1)}
    )
    db.flush()

    assert _refresh(client, roubado).status_code == 401
    assert client.get(f"{API}/usuarios/me", headers=auth(atual["access_token"])).status_code == 200


def test_logout_nao_apaga_o_refresh_de_outra_conta(client, db, user_locatario, user_locatario_2):
    alheio = _login(client, user_locatario_2.email)["refresh_token"]
    minha = _login(client, user_locatario.email)
    client.post(f"{API}/auth/logout", headers=auth(minha["access_token"]), json={"refresh_token": alheio})
    assert _refresh(client, alheio).status_code == 200
