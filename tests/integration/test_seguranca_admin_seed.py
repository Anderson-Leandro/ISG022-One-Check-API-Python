"""
Segurança — N2: reset do banco e tomada de conta via /admin/seed

Cenário de ataque original: o SEED_SECRET tinha valor padrão público
("onecheck-seed-dev") e era o único controle das rotas /admin/*. Sem login,
POST /admin/seed {"force": true} apagava o banco e recriava o admin de seed
com senha e segredo TOTP conhecidos.

Rotas cobertas:
  GET   /admin/data/status
  POST  /admin/seed
  POST  /admin/refresh-data
"""
import importlib

import pytest

import app.config as config
import app.routers.admin as admin_router
from app.models import Usuario
from tests.conftest import auth

SEGREDO_PUBLICO_ANTIGO = "onecheck-seed-dev"
SEGREDO_TESTE = "segredo-de-teste-com-tamanho-ok"


@pytest.fixture
def seed_secret(monkeypatch):
    """Configura um SEED_SECRET válido e desliga operações destrutivas."""
    monkeypatch.setattr(admin_router, "SEED_SECRET", SEGREDO_TESTE)
    monkeypatch.setattr(admin_router, "SEED_ALLOW_DESTRUCTIVE", False)
    return SEGREDO_TESTE


def _usuarios(db) -> int:
    db.expire_all()
    return db.query(Usuario).count()


# ── Configuração (secure by default) ────────────────────────────────────────────

class TestSeedSecretConfig:
    def _reload_config(self, monkeypatch, valor):
        if valor is None:
            monkeypatch.delenv("SEED_SECRET", raising=False)
        else:
            monkeypatch.setenv("SEED_SECRET", valor)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        return importlib.reload(config)

    def test_sem_variavel_de_ambiente_seed_fica_desabilitado(self, monkeypatch):
        try:
            cfg = self._reload_config(monkeypatch, None)
            assert not cfg.SEED_SECRET
        finally:
            monkeypatch.undo()
            importlib.reload(config)

    def test_segredo_publico_antigo_e_tratado_como_nao_configurado(self, monkeypatch):
        try:
            cfg = self._reload_config(monkeypatch, SEGREDO_PUBLICO_ANTIGO)
            assert not cfg.SEED_SECRET
        finally:
            monkeypatch.undo()
            importlib.reload(config)

    def test_operacoes_destrutivas_desligadas_por_padrao(self, monkeypatch):
        try:
            monkeypatch.delenv("SEED_ALLOW_DESTRUCTIVE", raising=False)
            cfg = self._reload_config(monkeypatch, SEGREDO_TESTE)
            assert cfg.SEED_ALLOW_DESTRUCTIVE is False
        finally:
            monkeypatch.undo()
            importlib.reload(config)


# ── Ataque sem autenticação ─────────────────────────────────────────────────────

class TestSeedSemAutenticacao:
    def test_rotas_admin_desabilitadas_sem_segredo_configurado(self, client, db, user_admin, monkeypatch):
        monkeypatch.setattr(admin_router, "SEED_SECRET", "")
        r = client.post(
            "/api/v1/admin/seed",
            json={"force": True},
            headers={"X-Seed-Secret": SEGREDO_PUBLICO_ANTIGO},
        )
        assert r.status_code == 404
        assert _usuarios(db) == 1

    def test_ataque_force_com_segredo_publico_nao_apaga_banco(self, client, db, user_admin, seed_secret):
        r = client.post(
            "/api/v1/admin/seed",
            json={"force": True},
            headers={"X-Seed-Secret": SEGREDO_PUBLICO_ANTIGO},
        )
        assert r.status_code == 403
        assert db.query(Usuario).filter(Usuario.id == user_admin.id).first() is not None

    def test_segredo_correto_sem_token_admin_e_negado_quando_ha_usuarios(
        self, client, db, user_admin, seed_secret
    ):
        r = client.post(
            "/api/v1/admin/seed",
            json={"force": True},
            headers={"X-Seed-Secret": seed_secret},
        )
        assert r.status_code == 401
        assert _usuarios(db) == 1

    def test_segredo_correto_com_token_nao_admin_e_negado(
        self, client, db, user_admin, token_gestor, seed_secret
    ):
        r = client.post(
            "/api/v1/admin/seed",
            json={"force": True},
            headers={"X-Seed-Secret": seed_secret, **auth(token_gestor)},
        )
        assert r.status_code == 403
        assert _usuarios(db) == 2

    def test_refresh_data_sem_token_admin_e_negado(self, client, db, user_admin, seed_secret):
        r = client.post("/api/v1/admin/refresh-data", headers={"X-Seed-Secret": seed_secret})
        assert r.status_code == 401

    def test_data_status_sem_token_admin_e_negado(self, client, db, user_admin, seed_secret):
        r = client.get("/api/v1/admin/data/status", headers={"X-Seed-Secret": seed_secret})
        assert r.status_code == 401


# ── Operações destrutivas ───────────────────────────────────────────────────────

class TestSeedDestrutivo:
    def test_force_bloqueado_sem_flag_mesmo_com_admin(self, client, db, user_admin, token_admin, seed_secret):
        r = client.post(
            "/api/v1/admin/seed",
            json={"force": True},
            headers={"X-Seed-Secret": seed_secret, **auth(token_admin)},
        )
        assert r.status_code == 403
        assert db.query(Usuario).filter(Usuario.id == user_admin.id).first() is not None

    def test_refresh_data_bloqueado_sem_flag_mesmo_com_admin(self, client, user_admin, token_admin, seed_secret):
        r = client.post(
            "/api/v1/admin/refresh-data",
            headers={"X-Seed-Secret": seed_secret, **auth(token_admin)},
        )
        assert r.status_code == 403

    def test_mode_refresh_data_no_seed_tambem_bloqueado(self, client, user_admin, token_admin, seed_secret):
        r = client.post(
            "/api/v1/admin/seed",
            json={"mode": "refresh_data"},
            headers={"X-Seed-Secret": seed_secret, **auth(token_admin)},
        )
        assert r.status_code == 403

    def test_force_permitido_com_flag_e_admin(self, client, db, user_admin, token_admin, seed_secret, monkeypatch):
        monkeypatch.setattr(admin_router, "SEED_ALLOW_DESTRUCTIVE", True)
        r = client.post(
            "/api/v1/admin/seed",
            json={"force": True},
            headers={"X-Seed-Secret": seed_secret, **auth(token_admin)},
        )
        assert r.status_code == 200
        assert r.json()["sucesso"] is True


# ── Caminhos legítimos ──────────────────────────────────────────────────────────

class TestSeedLegitimo:
    def test_data_status_com_segredo_e_admin(self, client, user_admin, token_admin, seed_secret):
        r = client.get(
            "/api/v1/admin/data/status",
            headers={"X-Seed-Secret": seed_secret, **auth(token_admin)},
        )
        assert r.status_code == 200
        assert r.json()["sucesso"] is True

    def test_bootstrap_em_banco_vazio_exige_apenas_segredo(self, client, db, seed_secret):
        assert _usuarios(db) == 0
        r = client.post("/api/v1/admin/seed", json={}, headers={"X-Seed-Secret": seed_secret})
        assert r.status_code == 200
        assert _usuarios(db) > 0

    def test_bootstrap_nao_aceita_segredo_errado(self, client, db, seed_secret):
        r = client.post("/api/v1/admin/seed", json={}, headers={"X-Seed-Secret": "errado"})
        assert r.status_code == 403
        assert _usuarios(db) == 0
