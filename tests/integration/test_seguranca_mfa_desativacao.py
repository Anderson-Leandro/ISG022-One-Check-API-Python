"""
Segurança — N5: desativar o MFA sem reautenticação

Cenário de ataque original: POST /auth/mfa/desabilitar e DELETE /usuarios/me/mfa
desligavam o MFA só com o access token, inclusive para perfis em que o MFA é
obrigatório. Um token roubado virava acesso permanente só com a senha.
Os resets feitos por admin também deixavam mfa_enabled=False, o que liberava
login sem segundo fator para perfis obrigatórios.

Regras verificadas:
  - perfis com MFA obrigatório não desativam o próprio MFA (só reset por outro admin)
  - perfis opcionais desativam com senha + código TOTP atual
  - reset por admin em perfil obrigatório força nova configuração no próximo login
"""
import pytest

from app.models import Usuario
from tests.conftest import MFA_TEST_SECRET, TEST_SENHA, _SENHA_HASH, auth, totp_now

ROTAS_SELF = [
    ("POST", "/api/v1/auth/mfa/desabilitar"),
    ("DELETE", "/api/v1/usuarios/me/mfa"),
]


@pytest.fixture
def locatario_com_mfa(db):
    u = Usuario(
        nome="Loc MFA", email="loc_mfa@test.com", senha_hash=_SENHA_HASH,
        role="locatario", mfa_enabled=True, mfa_secret=MFA_TEST_SECRET, ativo=True,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def token_locatario_com_mfa(locatario_com_mfa):
    from app.auth import create_access_token
    return create_access_token(locatario_com_mfa.id, locatario_com_mfa.role)


def _desativar(client, metodo, rota, token, body=None):
    return client.request(metodo, rota, json=body, headers=auth(token))


def _recarregar(db, user):
    db.expire_all()
    return db.query(Usuario).filter(Usuario.id == user.id).first()


# ── Perfis com MFA obrigatório ──────────────────────────────────────────────────

class TestPerfilObrigatorio:
    @pytest.mark.parametrize("metodo,rota", ROTAS_SELF)
    @pytest.mark.parametrize("perfil", ["admin", "vistoriador", "gestor"])
    def test_nao_desativa_o_proprio_mfa_mesmo_com_senha_e_codigo(
        self, client, db, request, metodo, rota, perfil
    ):
        user = request.getfixturevalue(f"user_{perfil}")
        token = request.getfixturevalue(f"token_{perfil}")
        r = _desativar(client, metodo, rota, token, {"senha": TEST_SENHA, "codigo": totp_now()})
        assert r.status_code == 403
        u = _recarregar(db, user)
        assert u.mfa_enabled is True
        assert u.mfa_secret == MFA_TEST_SECRET


# ── Perfis com MFA opcional ─────────────────────────────────────────────────────

class TestPerfilOpcional:
    @pytest.mark.parametrize("metodo,rota", ROTAS_SELF)
    def test_token_roubado_sem_senha_nao_desativa(
        self, client, db, locatario_com_mfa, token_locatario_com_mfa, metodo, rota
    ):
        r = _desativar(client, metodo, rota, token_locatario_com_mfa)
        assert r.status_code == 422
        assert _recarregar(db, locatario_com_mfa).mfa_secret == MFA_TEST_SECRET

    @pytest.mark.parametrize("metodo,rota", ROTAS_SELF)
    def test_senha_errada_nao_desativa(self, client, db, locatario_com_mfa, token_locatario_com_mfa, metodo, rota):
        r = _desativar(client, metodo, rota, token_locatario_com_mfa, {"senha": "errada", "codigo": totp_now()})
        assert r.json()["sucesso"] is False
        assert _recarregar(db, locatario_com_mfa).mfa_secret == MFA_TEST_SECRET

    @pytest.mark.parametrize("metodo,rota", ROTAS_SELF)
    def test_sem_codigo_nao_desativa(self, client, db, locatario_com_mfa, token_locatario_com_mfa, metodo, rota):
        r = _desativar(client, metodo, rota, token_locatario_com_mfa, {"senha": TEST_SENHA})
        assert r.json()["sucesso"] is False
        assert _recarregar(db, locatario_com_mfa).mfa_secret == MFA_TEST_SECRET

    @pytest.mark.parametrize("metodo,rota", ROTAS_SELF)
    def test_codigo_errado_nao_desativa(self, client, db, locatario_com_mfa, token_locatario_com_mfa, metodo, rota):
        r = _desativar(client, metodo, rota, token_locatario_com_mfa, {"senha": TEST_SENHA, "codigo": "000000"})
        assert r.json()["sucesso"] is False
        assert _recarregar(db, locatario_com_mfa).mfa_secret == MFA_TEST_SECRET

    @pytest.mark.parametrize("metodo,rota", ROTAS_SELF)
    def test_senha_e_codigo_corretos_desativam(
        self, client, db, locatario_com_mfa, token_locatario_com_mfa, metodo, rota
    ):
        r = _desativar(client, metodo, rota, token_locatario_com_mfa, {"senha": TEST_SENHA, "codigo": totp_now()})
        assert r.json()["sucesso"] is True
        u = _recarregar(db, locatario_com_mfa)
        assert u.mfa_enabled is False
        assert u.mfa_secret is None

    def test_mfa_habilitado_sem_autenticador_desativa_so_com_senha(self, client, db, user_locatario, token_locatario):
        user_locatario.mfa_enabled = True
        db.flush()
        r = _desativar(client, "POST", "/api/v1/auth/mfa/desabilitar", token_locatario, {"senha": TEST_SENHA})
        assert r.json()["sucesso"] is True
        assert _recarregar(db, user_locatario).mfa_enabled is False


# ── Reset feito por admin ───────────────────────────────────────────────────────

class TestResetPorAdmin:
    @pytest.mark.parametrize("metodo,rota", [
        ("DELETE", "/api/v1/usuarios/{id}/mfa"),
        ("POST", "/api/v1/usuarios/{id}/mfa/desabilitar"),
    ])
    def test_reset_de_perfil_obrigatorio_forca_nova_configuracao(
        self, client, db, user_vistoriador, token_admin, metodo, rota
    ):
        r = client.request(metodo, rota.format(id=user_vistoriador.id), headers=auth(token_admin))
        assert r.json()["sucesso"] is True
        u = _recarregar(db, user_vistoriador)
        assert u.mfa_secret is None
        assert u.mfa_enabled is True

        login = client.post("/api/v1/auth/login", json={"email": u.email, "senha": TEST_SENHA}).json()
        assert login["dados"].get("mfa_setup_required") is True
        assert "access_token" not in login["dados"]

    def test_auth_mfa_disable_em_perfil_obrigatorio_forca_nova_configuracao(
        self, client, db, user_vistoriador, token_admin
    ):
        r = client.post("/api/v1/auth/mfa/disable", json={"usuario_id": user_vistoriador.id}, headers=auth(token_admin))
        assert r.json()["sucesso"] is True
        assert _recarregar(db, user_vistoriador).mfa_enabled is True

    def test_auth_mfa_disable_nao_aceita_a_propria_conta(self, client, db, user_admin, token_admin):
        r = client.post("/api/v1/auth/mfa/disable", json={"usuario_id": user_admin.id}, headers=auth(token_admin))
        assert r.status_code == 403
        assert _recarregar(db, user_admin).mfa_secret == MFA_TEST_SECRET

    def test_put_nao_desliga_mfa_de_perfil_obrigatorio(self, client, db, user_vistoriador, token_admin):
        r = client.put(f"/api/v1/usuarios/{user_vistoriador.id}", json={"mfa_enabled": False}, headers=auth(token_admin))
        assert r.json()["sucesso"] is False
        assert _recarregar(db, user_vistoriador).mfa_enabled is True

    def test_reset_de_perfil_opcional_desliga_mfa(self, client, db, locatario_com_mfa, token_admin):
        r = client.delete(f"/api/v1/usuarios/{locatario_com_mfa.id}/mfa", headers=auth(token_admin))
        assert r.json()["sucesso"] is True
        assert _recarregar(db, locatario_com_mfa).mfa_enabled is False
