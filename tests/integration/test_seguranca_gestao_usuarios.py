"""
Segurança — N4: escalonamento de privilégio pelo gestor

Cenário de ataque original: PUT /usuarios/{id} aceitava qualquer string em
`role` e não distinguia o alvo. O gestor podia se promover a admin, promover
outros, trocar senha/e-mail de um admin, zerar ou definir o MFA de um admin e
criar novos admins.

Regras verificadas:
  - perfis aceitos: admin, gestor, vistoriador, locatario, visualizador
  - só admin atribui os perfis admin/gestor e gerencia contas admin/gestor
  - ninguém altera a própria conta pelas rotas /usuarios/{id} (usa /usuarios/me)
"""
import pytest

from app.auth import verify_password
from app.models import Usuario
from tests.conftest import MFA_TEST_SECRET, TEST_SENHA, _SENHA_HASH, auth, totp_now

BASE = "/api/v1/usuarios"


@pytest.fixture
def outro_gestor(db):
    u = Usuario(
        nome="Outro Gestor", email="outro_gestor@test.com", senha_hash=_SENHA_HASH,
        role="gestor", mfa_enabled=True, mfa_secret=MFA_TEST_SECRET, ativo=True,
    )
    db.add(u)
    db.flush()
    return u


def _recarregar(db, user):
    db.expire_all()
    return db.query(Usuario).filter(Usuario.id == user.id).first()


# ── Gestor tentando escalar ─────────────────────────────────────────────────────

class TestGestorNaoEscala:
    def test_gestor_nao_se_promove_a_admin(self, client, db, user_gestor, token_gestor):
        r = client.put(f"{BASE}/{user_gestor.id}", json={"role": "admin"}, headers=auth(token_gestor))
        assert r.status_code == 403
        assert _recarregar(db, user_gestor).role == "gestor"

    @pytest.mark.parametrize("role", ["admin", "gestor"])
    def test_gestor_nao_promove_outro_a_perfil_privilegiado(self, client, db, user_locatario, token_gestor, role):
        r = client.put(f"{BASE}/{user_locatario.id}", json={"role": role}, headers=auth(token_gestor))
        assert r.status_code == 403
        assert _recarregar(db, user_locatario).role == "locatario"

    def test_gestor_nao_troca_senha_de_admin(self, client, db, user_admin, token_gestor):
        r = client.put(f"{BASE}/{user_admin.id}", json={"senha": "senha-do-atacante"}, headers=auth(token_gestor))
        assert r.status_code == 403
        assert verify_password(TEST_SENHA, _recarregar(db, user_admin).senha_hash)

    def test_gestor_nao_troca_email_de_admin(self, client, db, user_admin, token_gestor):
        r = client.put(f"{BASE}/{user_admin.id}", json={"email": "atacante@x.com"}, headers=auth(token_gestor))
        assert r.status_code == 403
        assert _recarregar(db, user_admin).email == "admin@test.com"

    def test_gestor_nao_altera_outro_gestor(self, client, db, outro_gestor, token_gestor):
        r = client.put(f"{BASE}/{outro_gestor.id}", json={"nome": "X"}, headers=auth(token_gestor))
        assert r.status_code == 403

    @pytest.mark.parametrize("metodo,sufixo", [("delete", "/mfa"), ("post", "/mfa/desabilitar")])
    def test_gestor_nao_reseta_mfa_de_admin(self, client, db, user_admin, token_gestor, metodo, sufixo):
        r = getattr(client, metodo)(f"{BASE}/{user_admin.id}{sufixo}", headers=auth(token_gestor))
        assert r.status_code == 403
        assert _recarregar(db, user_admin).mfa_secret == MFA_TEST_SECRET

    def test_gestor_nao_define_segredo_mfa_de_admin(self, client, db, user_admin, token_gestor):
        import pyotp
        segredo_atacante = pyotp.random_base32()
        r = client.post(
            f"{BASE}/{user_admin.id}/mfa/enable",
            json={"secret": segredo_atacante, "codigo": pyotp.TOTP(segredo_atacante).now()},
            headers=auth(token_gestor),
        )
        assert r.status_code == 403
        assert _recarregar(db, user_admin).mfa_secret == MFA_TEST_SECRET

    def test_gestor_nao_ve_setup_mfa_de_admin(self, client, user_admin, token_gestor):
        r = client.post(f"{BASE}/{user_admin.id}/mfa/setup", headers=auth(token_gestor))
        assert r.status_code == 403

    def test_gestor_nao_desativa_admin(self, client, db, user_admin, token_gestor):
        r = client.delete(f"{BASE}/{user_admin.id}", headers=auth(token_gestor))
        assert r.status_code == 403
        assert _recarregar(db, user_admin).ativo is True

    @pytest.mark.parametrize("role", ["admin", "gestor"])
    def test_gestor_nao_cria_usuario_privilegiado(self, client, db, token_gestor, role):
        r = client.post(
            BASE,
            json={"nome": "Novo", "email": f"novo_{role}@x.com", "senha": "senha123", "role": role},
            headers=auth(token_gestor),
        )
        assert r.status_code == 403
        assert db.query(Usuario).filter(Usuario.email == f"novo_{role}@x.com").first() is None


# ── Validação de perfil ─────────────────────────────────────────────────────────

class TestPerfisValidos:
    def test_admin_nao_atribui_perfil_inexistente(self, client, db, user_locatario, token_admin):
        r = client.put(f"{BASE}/{user_locatario.id}", json={"role": "superadmin"}, headers=auth(token_admin))
        assert r.json()["sucesso"] is False
        assert _recarregar(db, user_locatario).role == "locatario"

    def test_nao_cria_usuario_com_perfil_inexistente(self, client, db, token_admin):
        r = client.post(
            BASE,
            json={"nome": "X", "email": "perfil_x@x.com", "senha": "senha123", "role": "root"},
            headers=auth(token_admin),
        )
        assert r.json()["sucesso"] is False


# ── Própria conta pelas rotas administrativas ───────────────────────────────────

class TestPropriaContaPelaRotaAdmin:
    def test_admin_nao_altera_a_propria_conta_por_id(self, client, db, user_admin, token_admin):
        r = client.put(f"{BASE}/{user_admin.id}", json={"senha": "nova-senha-123"}, headers=auth(token_admin))
        assert r.status_code == 403
        assert verify_password(TEST_SENHA, _recarregar(db, user_admin).senha_hash)

    def test_admin_nao_reseta_o_proprio_mfa_por_id(self, client, db, user_admin, token_admin):
        r = client.delete(f"{BASE}/{user_admin.id}/mfa", headers=auth(token_admin))
        assert r.status_code == 403
        assert _recarregar(db, user_admin).mfa_secret == MFA_TEST_SECRET


# ── Caminhos legítimos ──────────────────────────────────────────────────────────

class TestGestaoLegitima:
    def test_gestor_edita_locatario(self, client, db, user_locatario, token_gestor):
        r = client.put(f"{BASE}/{user_locatario.id}", json={"nome": "Nome Novo"}, headers=auth(token_gestor))
        assert r.json()["sucesso"] is True
        assert _recarregar(db, user_locatario).nome == "Nome Novo"

    def test_gestor_cria_vistoriador_com_mfa_exigido(self, client, token_gestor):
        r = client.post(
            BASE,
            json={"nome": "Vist", "email": "vist_novo@x.com", "senha": "senha123", "role": "vistoriador"},
            headers=auth(token_gestor),
        )
        assert r.json()["sucesso"] is True
        assert r.json()["dados"]["mfa_enabled"] is True

    def test_admin_promove_locatario_a_gestor_e_mfa_passa_a_ser_exigido(self, client, db, user_locatario, token_admin):
        r = client.put(f"{BASE}/{user_locatario.id}", json={"role": "gestor"}, headers=auth(token_admin))
        assert r.json()["sucesso"] is True
        u = _recarregar(db, user_locatario)
        assert u.role == "gestor"
        assert u.mfa_enabled is True

    def test_admin_gerencia_gestor(self, client, db, user_gestor, token_admin):
        r = client.put(f"{BASE}/{user_gestor.id}", json={"nome": "Gestor Renomeado"}, headers=auth(token_admin))
        assert r.json()["sucesso"] is True
