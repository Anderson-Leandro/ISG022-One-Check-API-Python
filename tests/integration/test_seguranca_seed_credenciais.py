"""
Segurança — SEC-001: seed com credenciais públicas em produção

Cenário original: o start.sh rodava scripts/seed.py em todo start do container.
Em banco vazio, o seed criava admin@onecheck.local (e gestor, vistoriadores,
locatários) com senhas fixas e o mesmo segredo TOTP, todos publicados no
repositório público. Qualquer pessoa fazia login como admin e passava no MFA.
/admin/seed (bootstrap e force) criava as mesmas contas.

Regras verificadas (fora de APP_ENV=development/test):
  - o seed gera senhas aleatórias e distintas, exibidas só na resposta
  - perfis com MFA obrigatório ficam sem segredo e configuram o autenticador no primeiro login
  - nenhuma senha ou segredo de demonstração é aceito
  - contas antigas com credenciais públicas são detectadas e rotacionadas (senha, MFA e sessões)
Em desenvolvimento as credenciais fixas continuam valendo.
"""
import bcrypt
import pytest

import app.routers.admin as admin_router
import app.seed_service as seed_service
from app.auth import create_refresh_token, verify_password
from app.models import RefreshToken, Usuario
from app.seed_service import MFA_SECRET_DEV, SENHAS_DEV

SEGREDO = "segredo-de-teste-com-tamanho-ok"
HEADER = {"X-Seed-Secret": SEGREDO}


def hash_password(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt(rounds=4)).decode()


@pytest.fixture(autouse=True)
def bcrypt_rapido(monkeypatch):
    # O seed cria 7 contas; com o custo padrão do bcrypt cada teste levaria segundos
    monkeypatch.setattr(seed_service, "hash_password", hash_password)


@pytest.fixture
def producao(monkeypatch):
    monkeypatch.setattr(seed_service, "IS_DEV", False)
    monkeypatch.setattr(admin_router, "SEED_SECRET", SEGREDO)


def _seed(client, **body):
    r = client.post("/api/v1/admin/seed", json=body or None, headers=HEADER)
    assert r.status_code == 200, r.text
    assert r.json()["sucesso"] is True, r.json()
    return r.json()["dados"]


def _usuarios(db):
    db.expire_all()
    return db.query(Usuario).all()


# ── Produção ─────────────────────────────────────────────────────────────────────

@pytest.mark.usefixtures("producao")
class TestSeedEmProducao:
    def test_nenhuma_senha_de_demonstracao(self, client, db):
        _seed(client)
        usuarios = _usuarios(db)
        assert len(usuarios) == len(SENHAS_DEV)
        for u in usuarios:
            assert not verify_password(SENHAS_DEV[u.email], u.senha_hash), u.email

    def test_nenhum_segredo_mfa_definido(self, client, db):
        dados = _seed(client)
        assert "mfa_secret" not in dados and "mfa_codigo_atual" not in dados
        assert all(u.mfa_secret is None for u in _usuarios(db))

    def test_perfis_com_mfa_configuram_no_primeiro_login(self, client, db):
        _seed(client)
        for u in _usuarios(db):
            assert u.mfa_enabled is (u.role in ("admin", "gestor", "vistoriador")), u.email

    def test_senhas_geradas_sao_fortes_distintas_e_validas(self, client, db):
        credenciais = {c["email"]: c["senha"] for c in _seed(client)["usuarios"]}
        assert len(set(credenciais.values())) == len(credenciais)
        assert all(len(s) >= 16 for s in credenciais.values())
        for u in _usuarios(db):
            assert verify_password(credenciais[u.email], u.senha_hash)

    def test_login_com_credencial_publica_falha(self, client, db):
        _seed(client)
        r = client.post("/api/v1/auth/login", json={"email": "admin@onecheck.local", "senha": "admin123"})
        assert r.json()["sucesso"] is False

    def test_login_do_admin_exige_configurar_mfa(self, client, db):
        senha = next(c["senha"] for c in _seed(client)["usuarios"] if c["email"] == "admin@onecheck.local")
        r = client.post("/api/v1/auth/login", json={"email": "admin@onecheck.local", "senha": senha})
        dados = r.json()["dados"]
        assert dados.get("mfa_setup_required") is True
        assert "access_token" not in dados

    def test_mode_expand_tambem_gera_senhas(self, client, db, user_admin, token_admin):
        r = client.post(
            "/api/v1/admin/seed", json={"mode": "expand"},
            headers={**HEADER, "Authorization": f"Bearer {token_admin}"},
        )
        assert r.json()["sucesso"] is True
        criados = [u for u in _usuarios(db) if u.email in SENHAS_DEV]
        assert criados
        for u in criados:
            assert not verify_password(SENHAS_DEV[u.email], u.senha_hash)
            assert u.mfa_secret is None


# ── Desenvolvimento ──────────────────────────────────────────────────────────────

class TestSeedEmDesenvolvimento:
    def test_mantem_credenciais_fixas(self, client, db, monkeypatch):
        monkeypatch.setattr(admin_router, "SEED_SECRET", SEGREDO)
        dados = _seed(client)
        assert dados["mfa_secret"] == MFA_SECRET_DEV
        admin = next(u for u in _usuarios(db) if u.email == "admin@onecheck.local")
        assert verify_password("admin123", admin.senha_hash)
        assert admin.mfa_secret == MFA_SECRET_DEV


# ── Contas já criadas pelo seed antigo ───────────────────────────────────────────

@pytest.fixture
def contas_antigas(db):
    """Simula um banco de produção populado pelo seed antigo."""
    admin = Usuario(nome="Admin", email="admin@onecheck.local", senha_hash=hash_password("admin123"),
                    role="admin", mfa_enabled=True, mfa_secret=MFA_SECRET_DEV)
    # Senha já trocada, mas segredo TOTP ainda o público
    vist = Usuario(nome="Vist", email="vistoriador@onecheck.local", senha_hash=hash_password("outra-senha-forte"),
                   role="vistoriador", mfa_enabled=True, mfa_secret=MFA_SECRET_DEV)
    # Senha pública, sem MFA
    loc = Usuario(nome="Loc", email="locatario@onecheck.local", senha_hash=hash_password("locat123"), role="locatario")
    # Conta de seed que já foi corrigida
    gestor = Usuario(nome="Gestor", email="gestor@onecheck.local", senha_hash=hash_password("senha-propria-forte"),
                     role="gestor", mfa_enabled=True, mfa_secret="KRSXG5CTMVRXEZLU")
    db.add_all([admin, vist, loc, gestor])
    db.flush()
    return {"admin": admin, "vist": vist, "loc": loc, "gestor": gestor}


class TestContasExistentes:
    def test_detecta_senha_ou_segredo_publico(self, db, contas_antigas):
        emails = {u.email for u in seed_service.contas_com_credenciais_publicas(db)}
        assert emails == {"admin@onecheck.local", "vistoriador@onecheck.local", "locatario@onecheck.local"}

    def test_rotacao_troca_senha_reseta_mfa_e_revoga_sessoes(self, client, db, contas_antigas):
        admin = contas_antigas["admin"]
        create_refresh_token(db, admin.id)
        novas = {c["email"]: c["senha"] for c in seed_service.rotacionar_credenciais_publicas(db)}

        db.expire_all()
        assert not verify_password("admin123", admin.senha_hash)
        assert verify_password(novas["admin@onecheck.local"], admin.senha_hash)
        assert admin.mfa_secret is None and admin.mfa_enabled is True
        assert db.query(RefreshToken).filter(RefreshToken.usuario_id == admin.id).count() == 0
        assert seed_service.contas_com_credenciais_publicas(db) == []

    def test_rotacao_preserva_conta_ja_corrigida(self, db, contas_antigas):
        gestor = contas_antigas["gestor"]
        hash_antes = gestor.senha_hash
        seed_service.rotacionar_credenciais_publicas(db)
        db.expire_all()
        assert gestor.senha_hash == hash_antes and gestor.mfa_secret == "KRSXG5CTMVRXEZLU"

    def test_ataque_antigo_falha_apos_rotacao(self, client, db, contas_antigas):
        seed_service.rotacionar_credenciais_publicas(db)
        r = client.post("/api/v1/auth/login", json={"email": "admin@onecheck.local", "senha": "admin123"})
        assert r.json()["sucesso"] is False
        # O segredo TOTP público deixa de valer: nenhuma conta o usa mais
        db.expire_all()
        assert db.query(Usuario).filter(Usuario.mfa_secret == MFA_SECRET_DEV).count() == 0
