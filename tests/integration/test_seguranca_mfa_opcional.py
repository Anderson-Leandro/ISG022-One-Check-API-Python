"""
Segurança — SEC-036: o MFA ligado pelo próprio usuário passa a valer no login (ADR-0011)

O locatário conseguia ligar o MFA (POST /usuarios/me/mfa/enable), mas o login só pedia o código para os
perfis obrigatórios: com a senha, ele entrava direto. Agora quem tem MFA ligado e autenticador configurado
recebe mfa_required no login, em qualquer perfil.
"""
import pytest

from app.models import Usuario
from tests.conftest import MFA_TEST_SECRET, TEST_SENHA, totp_now

API = "/api/v1"


@pytest.fixture
def locatario_com_mfa(db, user_locatario):
    user_locatario.mfa_enabled = True
    user_locatario.mfa_secret = MFA_TEST_SECRET
    db.flush()
    return user_locatario


def _login(client, email, senha=TEST_SENHA):
    return client.post(f"{API}/auth/login", json={"email": email, "senha": senha})


def test_locatario_com_mfa_recebe_mfa_required_e_nao_a_sessao(client, locatario_com_mfa):
    r = _login(client, locatario_com_mfa.email)

    assert r.status_code == 200, r.text
    dados = r.json()["dados"]
    assert dados["mfa_required"] is True
    assert dados["temp_token"]
    assert "access_token" not in dados and "refresh_token" not in dados


def test_codigo_certo_abre_a_sessao(client, locatario_com_mfa):
    temp = _login(client, locatario_com_mfa.email).json()["dados"]["temp_token"]

    r = client.post(f"{API}/auth/mfa/verify", json={"temp_token": temp, "codigo": totp_now()})

    assert r.status_code == 200, r.text
    assert r.json()["dados"]["access_token"]
    assert r.json()["dados"]["usuario"]["id"] == locatario_com_mfa.id


def test_codigo_errado_e_recusado_e_conta_no_limite(client, locatario_com_mfa):
    from app.rate_limit import limitador
    temp = _login(client, locatario_com_mfa.email).json()["dados"]["temp_token"]

    r = client.post(f"{API}/auth/mfa/verify", json={"temp_token": temp, "codigo": "000000"})

    assert r.status_code == 401, r.text
    assert r.json()["erro"] == "Código MFA inválido"
    assert limitador.espera(f"mfa:{locatario_com_mfa.id}", maximo=1) > 0


def test_locatario_sem_mfa_continua_entrando_direto(client, user_locatario):
    r = _login(client, user_locatario.email)
    assert r.status_code == 200, r.text
    assert r.json()["dados"]["access_token"]


def test_mfa_ligado_sem_autenticador_leva_a_configuracao(client, db, user_locatario):
    """MFA ligado (por /mfa/habilitar ou pelo admin) e sem autenticador: o login pede a configuração, sem sessão."""
    user_locatario.mfa_enabled = True
    user_locatario.mfa_secret = None
    db.flush()
    r = _login(client, user_locatario.email)
    assert r.status_code == 200, r.text
    dados = r.json()["dados"]
    assert dados["mfa_setup_required"] is True
    assert "access_token" not in dados


def test_habilitar_configurar_e_entrar_com_codigo(client, db, user_locatario, token_locatario):
    """Fluxo de /auth/mfa/habilitar: o próximo login configura o autenticador e, a partir daí, pede o código."""
    import pyotp
    from tests.conftest import auth
    assert client.post(f"{API}/auth/mfa/habilitar", headers=auth(token_locatario)).status_code == 200

    temp = _login(client, user_locatario.email).json()["dados"]["temp_token"]
    secret = client.get(f"{API}/auth/mfa/setup-login", params={"temp_token": temp}).json()["dados"]["secret"]
    r = client.post(f"{API}/auth/mfa/activate-login", json={"temp_token": temp, "codigo": pyotp.TOTP(secret).now()})
    assert r.status_code == 200, r.text
    assert r.json()["dados"]["access_token"]

    assert _login(client, user_locatario.email).json()["dados"]["mfa_required"] is True


def test_perfil_obrigatorio_continua_igual(client, user_gestor):
    r = _login(client, user_gestor.email)
    assert r.json()["dados"]["mfa_required"] is True


def test_ligar_o_mfa_pela_api_passa_a_exigir_o_codigo(client, db, user_locatario, token_locatario):
    """Fluxo completo: o locatário configura o autenticador e o próximo login pede o código."""
    from tests.conftest import auth
    setup = client.post(f"{API}/usuarios/me/mfa/setup", headers=auth(token_locatario)).json()["dados"]
    import pyotp
    r = client.post(f"{API}/usuarios/me/mfa/enable", headers=auth(token_locatario),
                    json={"secret": setup["secret"], "codigo": pyotp.TOTP(setup["secret"]).now()})
    assert r.status_code == 200, r.text

    db.expire_all()
    assert db.get(Usuario, user_locatario.id).mfa_enabled is True
    assert _login(client, user_locatario.email).json()["dados"]["mfa_required"] is True
