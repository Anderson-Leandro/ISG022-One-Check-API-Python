"""
Segurança — N1: bypass do MFA usando apenas a senha

Cenário de ataque original:
  1. POST /auth/login com a senha de um usuário com MFA ativo → temp_token
  2. GET  /auth/mfa/setup-login?temp_token=... → gravava um segredo novo e o devolvia
  3. POST /auth/mfa/activate-login com o código desse segredo → access_token

Rotas cobertas:
  POST /auth/login
  GET  /auth/mfa/setup-login
  POST /auth/mfa/activate-login
  POST /auth/mfa/verify
"""
import pyotp
import pytest

from app.auth import create_mfa_setup_token, create_temp_token, decode_token
from app.models import Usuario
from tests.conftest import MFA_TEST_SECRET, TEST_SENHA, _SENHA_HASH, totp_now


def _login(client, email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "senha": TEST_SENHA})
    assert r.json()["sucesso"] is True
    return r.json()["dados"]


@pytest.fixture
def user_sem_autenticador(db):
    """Admin com MFA exigido que ainda não configurou o autenticador."""
    u = Usuario(
        nome="Admin Novo",
        email="admin_novo@test.com",
        senha_hash=_SENHA_HASH,
        role="admin",
        mfa_enabled=True,
        mfa_secret=None,
        ativo=True,
    )
    db.add(u)
    db.flush()
    return u


# ── Ataque: usuário com MFA ativo ───────────────────────────────────────────────

class TestBypassMfa:
    def test_ataque_completo_nao_emite_tokens(self, client, db, user_admin):
        temp = _login(client, user_admin.email)["temp_token"]

        r_setup = client.get(f"/api/v1/auth/mfa/setup-login?temp_token={temp}")
        assert r_setup.status_code == 401
        assert "secret" not in r_setup.text

        codigo_atacante = pyotp.TOTP(pyotp.random_base32()).now()
        r_act = client.post(
            "/api/v1/auth/mfa/activate-login",
            json={"temp_token": temp, "codigo": codigo_atacante},
        )
        assert r_act.json()["sucesso"] is False
        assert "access_token" not in r_act.text

    def test_segredo_da_vitima_nao_e_alterado(self, client, db, user_admin):
        temp = _login(client, user_admin.email)["temp_token"]
        client.get(f"/api/v1/auth/mfa/setup-login?temp_token={temp}")

        db.refresh(user_admin)
        assert user_admin.mfa_secret == MFA_TEST_SECRET
        assert user_admin.mfa_secret_pendente is None

    def test_vitima_continua_entrando_com_autenticador_original(self, client, db, user_admin):
        temp = _login(client, user_admin.email)["temp_token"]
        client.get(f"/api/v1/auth/mfa/setup-login?temp_token={temp}")

        temp2 = _login(client, user_admin.email)["temp_token"]
        r = client.post("/api/v1/auth/mfa/verify", json={"temp_token": temp2, "codigo": totp_now()})
        assert r.json()["sucesso"] is True

    def test_activate_login_com_codigo_do_segredo_ativo_nao_e_atalho(self, client, user_admin):
        temp = _login(client, user_admin.email)["temp_token"]
        r = client.post(
            "/api/v1/auth/mfa/activate-login",
            json={"temp_token": temp, "codigo": totp_now()},
        )
        assert r.json()["sucesso"] is False

    def test_token_de_setup_forjado_para_usuario_com_mfa_ativo_e_rejeitado(self, client, db, user_admin):
        token = create_mfa_setup_token(user_admin.id)
        r = client.get(f"/api/v1/auth/mfa/setup-login?temp_token={token}")
        assert r.status_code == 409
        db.refresh(user_admin)
        assert user_admin.mfa_secret == MFA_TEST_SECRET


# ── Tipos de token ──────────────────────────────────────────────────────────────

class TestTiposDeTokenMfa:
    def test_login_com_mfa_ativo_emite_token_de_verificacao(self, client, user_admin):
        temp = _login(client, user_admin.email)["temp_token"]
        assert decode_token(temp)["type"] == "mfa"

    def test_login_sem_autenticador_emite_token_de_setup(self, client, user_sem_autenticador):
        dados = _login(client, user_sem_autenticador.email)
        assert dados["mfa_setup_required"] is True
        assert decode_token(dados["temp_token"])["type"] == "mfa_setup"

    def test_token_de_setup_nao_serve_para_verify(self, client, user_sem_autenticador):
        token = create_mfa_setup_token(user_sem_autenticador.id)
        r = client.post("/api/v1/auth/mfa/verify", json={"temp_token": token, "codigo": "123456"})
        assert r.json()["sucesso"] is False

    def test_token_de_verificacao_nao_serve_para_setup_mesmo_sem_autenticador(
        self, client, user_sem_autenticador
    ):
        token = create_temp_token(user_sem_autenticador.id)
        r = client.get(f"/api/v1/auth/mfa/setup-login?temp_token={token}")
        assert r.status_code == 401


# ── Fluxo legítimo de primeiro acesso ───────────────────────────────────────────

class TestSetupMfaPrimeiroAcesso:
    def test_fluxo_completo_promove_segredo_pendente(self, client, db, user_sem_autenticador):
        temp = _login(client, user_sem_autenticador.email)["temp_token"]

        r_setup = client.get(f"/api/v1/auth/mfa/setup-login?temp_token={temp}")
        assert r_setup.json()["sucesso"] is True
        secret = r_setup.json()["dados"]["secret"]

        db.refresh(user_sem_autenticador)
        assert user_sem_autenticador.mfa_secret is None
        assert user_sem_autenticador.mfa_secret_pendente == secret

        r_act = client.post(
            "/api/v1/auth/mfa/activate-login",
            json={"temp_token": temp, "codigo": pyotp.TOTP(secret).now()},
        )
        assert r_act.json()["sucesso"] is True
        assert "access_token" in r_act.json()["dados"]

        db.refresh(user_sem_autenticador)
        assert user_sem_autenticador.mfa_secret == secret
        assert user_sem_autenticador.mfa_secret_pendente is None
        assert user_sem_autenticador.mfa_enabled is True

    def test_activate_login_sem_setup_previo_falha(self, client, user_sem_autenticador):
        token = create_mfa_setup_token(user_sem_autenticador.id)
        r = client.post(
            "/api/v1/auth/mfa/activate-login",
            json={"temp_token": token, "codigo": "123456"},
        )
        assert r.json()["sucesso"] is False

    def test_activate_login_com_codigo_errado_mantem_pendente(self, client, db, user_sem_autenticador):
        token = create_mfa_setup_token(user_sem_autenticador.id)
        client.get(f"/api/v1/auth/mfa/setup-login?temp_token={token}")

        r = client.post(
            "/api/v1/auth/mfa/activate-login",
            json={"temp_token": token, "codigo": "000000"},
        )
        assert r.json()["sucesso"] is False
        db.refresh(user_sem_autenticador)
        assert user_sem_autenticador.mfa_secret is None

    def test_token_de_setup_reutilizado_apos_ativacao_e_rejeitado(self, client, db, user_sem_autenticador):
        token = create_mfa_setup_token(user_sem_autenticador.id)
        secret = client.get(f"/api/v1/auth/mfa/setup-login?temp_token={token}").json()["dados"]["secret"]
        client.post(
            "/api/v1/auth/mfa/activate-login",
            json={"temp_token": token, "codigo": pyotp.TOTP(secret).now()},
        )

        r = client.get(f"/api/v1/auth/mfa/setup-login?temp_token={token}")
        assert r.status_code == 409
        db.refresh(user_sem_autenticador)
        assert user_sem_autenticador.mfa_secret == secret
