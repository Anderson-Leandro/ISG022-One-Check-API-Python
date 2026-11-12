"""
Segurança — SEC-029: forçar a troca das senhas fracas cadastradas antes da política

Cenário original: a política de senha (SEC-011) só vale para senhas novas, e o login continua aceitando a
senha antiga, mesmo fora dela. Uma conta com "senha123" seguia entrando para sempre (risco residual do SEC-011).

Regras verificadas (decisões do PO em 2026-11-11 e 2026-11-12):
  - no login com a senha correta, se ela não passa na política atual, a conta fica com senha_expirada;
    o banco só guarda o hash, então a conferência só pode ser feita ali
  - com senha_expirada, o token só serve para ver o próprio perfil, trocar a senha e sair: o resto → 403
  - a troca da própria senha (PUT /usuarios/me/senha ou PATCH /usuarios/me) e a troca pelo admin limpam a marca
  - contas com senha forte não são afetadas
  - em APP_ENV=development/dev/local o login não marca: as contas do seed usam senhas públicas por desenho
  - vale também no login com MFA e depois do refresh
"""

import bcrypt
import pytest
from sqlalchemy import text

from app.models import Usuario
from app.routers import auth_router
from tests.conftest import MFA_TEST_SECRET, TEST_SENHA, auth, totp_now
from tests.unit.test_database_migracoes import banco_antigo  # noqa: F401, F811 - fixture do banco antigo

API = "/api/v1"
FRACA = "senha123"
NOVA = "Nova.Frase#Forte2026"


def _hash(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt(rounds=4)).decode()


@pytest.fixture
def conta_fraca(db):
    u = Usuario(nome="Conta Antiga", email="antiga@test.com", senha_hash=_hash(FRACA), role="locatario", ativo=True)
    db.add(u)
    db.commit()
    return u


def _login(client, email, senha):
    r = client.post(f"{API}/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200, r.text
    return r.json()["dados"]


class TestMarcacaoNoLogin:
    def test_senha_fraca_marca_a_conta_e_avisa_no_login(self, client, db, conta_fraca):
        dados = _login(client, conta_fraca.email, FRACA)
        assert dados["usuario"]["senha_expirada"] is True
        db.expire_all()
        assert db.get(Usuario, conta_fraca.id).senha_expirada is True

    def test_senha_forte_nao_e_afetada(self, client, db, user_locatario):
        dados = _login(client, user_locatario.email, TEST_SENHA)
        assert dados["usuario"]["senha_expirada"] is False
        r = client.get(f"{API}/contratos", headers=auth(dados["access_token"]))
        assert r.status_code == 200

    def test_em_desenvolvimento_nao_marca(self, client, db, conta_fraca, monkeypatch):
        monkeypatch.setattr(auth_router, "MARCAR_SENHA_FRACA", False)
        dados = _login(client, conta_fraca.email, FRACA)
        assert dados["usuario"]["senha_expirada"] is False
        db.expire_all()
        assert db.get(Usuario, conta_fraca.id).senha_expirada is False

    def test_login_com_mfa_tambem_marca_e_restringe(self, client, db):
        admin = Usuario(
            nome="Admin Antigo",
            email="admin.antigo@test.com",
            senha_hash=_hash(FRACA),
            role="admin",
            mfa_enabled=True,
            mfa_secret=MFA_TEST_SECRET,
            ativo=True,
        )
        db.add(admin)
        db.commit()
        temp = _login(client, admin.email, FRACA)["temp_token"]
        r = client.post(f"{API}/auth/mfa/verify", json={"temp_token": temp, "codigo": totp_now()})
        dados = r.json()["dados"]
        assert dados["usuario"]["senha_expirada"] is True
        assert client.get(f"{API}/logs", headers=auth(dados["access_token"])).status_code == 403


class TestRestricao:
    @pytest.fixture
    def token(self, client, conta_fraca):
        return _login(client, conta_fraca.email, FRACA)

    def test_outras_rotas_recebem_403_com_o_caminho_da_troca(self, client, token):
        r = client.get(f"{API}/contratos", headers=auth(token["access_token"]))
        assert r.status_code == 403
        assert "/api/v1/usuarios/me/senha" in r.json()["erro"]

    def test_pode_ver_o_proprio_perfil_e_sair(self, client, token):
        h = auth(token["access_token"])
        perfil = client.get(f"{API}/usuarios/me", headers=h)
        assert perfil.status_code == 200 and perfil.json()["dados"]["senha_expirada"] is True
        assert client.post(f"{API}/auth/logout", headers=h).status_code == 200

    def test_refresh_nao_tira_a_restricao(self, client, token):
        r = client.post(f"{API}/auth/refresh", json={"refresh_token": token["refresh_token"]})
        assert r.status_code == 200
        novo = r.json()["dados"]["access_token"]
        assert client.get(f"{API}/contratos", headers=auth(novo)).status_code == 403

    def test_trocar_a_senha_libera_o_acesso(self, client, db, conta_fraca, token):
        r = client.put(
            f"{API}/usuarios/me/senha",
            json={"senha_atual": FRACA, "nova_senha": NOVA},
            headers=auth(token["access_token"]),
        )
        assert r.status_code == 200, r.text
        db.expire_all()
        assert db.get(Usuario, conta_fraca.id).senha_expirada is False
        sessao = r.json()["dados"]["sessao"]
        assert client.get(f"{API}/contratos", headers=auth(sessao["access_token"])).status_code == 200

    def test_admin_define_a_senha_e_limpa_a_marca(self, client, db, conta_fraca, token, token_admin):
        r = client.put(f"{API}/usuarios/{conta_fraca.id}", json={"senha": NOVA}, headers=auth(token_admin))
        assert r.status_code == 200, r.text
        db.expire_all()
        assert db.get(Usuario, conta_fraca.id).senha_expirada is False

    def test_patch_do_perfil_fica_bloqueado_com_a_marca(self, client, token):
        # só o PUT /usuarios/me/senha troca a senha com a marca: o PATCH também mudaria o nome
        r = client.patch(
            f"{API}/usuarios/me", json={"senha_atual": FRACA, "senha_nova": NOVA}, headers=auth(token["access_token"])
        )
        assert r.status_code == 403


class TestMigracao:
    def test_banco_antigo_ganha_a_coluna_desmarcada(self, banco_antigo):  # noqa: F811
        # usuários de antes do SEC-029 começam sem a marca: ela só é posta no próximo login
        import app.database as database

        database.ensure_schema_updates()
        with banco_antigo.connect() as conn:
            assert conn.execute(text("SELECT senha_expirada FROM usuarios WHERE id = 'u1'")).scalar() in (0, False)


class TestRevisao:
    def test_login_com_mfa_sem_o_codigo_nao_marca(self, client, db):
        # quem só sabe a senha não consegue travar as sessões de uma conta com MFA
        admin = Usuario(
            nome="Admin Antigo",
            email="admin.semcodigo@test.com",
            senha_hash=_hash(FRACA),
            role="admin",
            mfa_enabled=True,
            mfa_secret=MFA_TEST_SECRET,
            ativo=True,
        )
        db.add(admin)
        db.commit()
        assert _login(client, admin.email, FRACA)["mfa_required"] is True
        db.expire_all()
        assert db.get(Usuario, admin.id).senha_expirada is False

    def test_primeiro_acesso_com_mfa_marca_depois_da_ativacao(self, client, db):
        import pyotp

        gestor = Usuario(
            nome="Gestor Novo",
            email="gestor.novo@test.com",
            senha_hash=_hash(FRACA),
            role="gestor",
            mfa_enabled=True,
            ativo=True,
        )
        db.add(gestor)
        db.commit()
        temp = _login(client, gestor.email, FRACA)["temp_token"]
        db.expire_all()
        assert db.get(Usuario, gestor.id).senha_expirada is False
        segredo = client.get(f"{API}/auth/mfa/setup-login", params={"temp_token": temp}).json()["dados"]["secret"]
        r = client.post(
            f"{API}/auth/mfa/activate-login", json={"temp_token": temp, "codigo": pyotp.TOTP(segredo).now()}
        )
        assert r.status_code == 200, r.text
        db.expire_all()
        assert db.get(Usuario, gestor.id).senha_expirada is True

    def test_rota_do_seed_tambem_fica_fechada(self, client, db, monkeypatch):
        from app.auth import create_access_token
        from app.routers import admin as admin_router

        monkeypatch.setattr(admin_router, "SEED_SECRET", "s" * 40)
        admin = Usuario(
            nome="Admin Marcado",
            email="admin.marcado@test.com",
            senha_hash=_hash(FRACA),
            role="admin",
            senha_expirada=True,
            ativo=True,
        )
        db.add(admin)
        db.commit()
        token = create_access_token(admin.id, admin.role, admin.token_version)
        r = client.get(f"{API}/admin/data/status", headers={**auth(token), "X-Seed-Secret": "s" * 40})
        assert r.status_code == 403
