"""
Fase 2.6 — Testes de integração das rotas de dashboard, logs, health e admin

Rotas cobertas:
  GET  /api/v1/dashboard
  GET  /api/v1/logs
  GET  /api/v1/health
  GET  /api/v1/uploads/{filename}
  GET  /api/v1/admin/data/status
  POST /api/v1/admin/refresh-data
  POST /api/v1/admin/seed
"""
from datetime import datetime
from app.config import SEED_SECRET, UPLOAD_DIR
from tests.conftest import auth, small_image_bytes

SEED_HEADER = {"X-Seed-Secret": SEED_SECRET}


# ── GET /dashboard ────────────────────────────────────────────────────────────────

class TestDashboard:
    def test_retorna_campos_esperados(self, client, token_admin):
        r = client.get("/api/v1/dashboard", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert "imoveis_locados" in data["dados"]
        assert "checklists_pendentes" in data["dados"]
        assert "problemas_abertos" in data["dados"]
        assert "vistorias_agendadas" in data["dados"]

    def test_contadores_sao_inteiros(self, client, token_admin):
        r = client.get("/api/v1/dashboard", headers=auth(token_admin))
        d = r.json()["dados"]
        assert isinstance(d["imoveis_locados"], int)
        assert isinstance(d["checklists_pendentes"], int)
        assert isinstance(d["problemas_abertos"], int)
        assert isinstance(d["vistorias_agendadas"], int)

    def test_contador_reflete_dados_existentes(self, client, contrato, token_admin):
        # contrato fixture marca o imovel como "locado" e cria 2 agendamentos
        r = client.get("/api/v1/dashboard", headers=auth(token_admin))
        d = r.json()["dados"]
        assert d["imoveis_locados"] >= 1
        assert d["vistorias_agendadas"] >= 2

    def test_qualquer_role_pode_acessar(self, client, token_locatario):
        r = client.get("/api/v1/dashboard", headers=auth(token_locatario))
        assert r.json()["sucesso"] is True

    def test_sem_autenticacao_retorna_401(self, client):
        r = client.get("/api/v1/dashboard")
        assert r.status_code == 401


# ── GET /logs ─────────────────────────────────────────────────────────────────────

class TestLogs:
    def test_lista_logs_autenticado(self, client, token_admin):
        r = client.get("/api/v1/logs", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert isinstance(data["dados"], list)

    def test_paginacao_presente(self, client, token_admin):
        r = client.get("/api/v1/logs", headers=auth(token_admin))
        assert "paginacao" in r.json()

    def test_log_criado_apos_login_aparece_na_listagem(self, client, user_locatario, token_admin):
        from tests.conftest import TEST_SENHA
        client.post("/api/v1/auth/login", json={
            "email": user_locatario.email,
            "senha": TEST_SENHA,
        })
        r = client.get("/api/v1/logs", headers=auth(token_admin))
        logs = r.json()["dados"]
        assert any(l["acao"] == "login" for l in logs)

    def test_campos_do_log(self, client, user_locatario, token_admin):
        from tests.conftest import TEST_SENHA
        client.post("/api/v1/auth/login", json={
            "email": user_locatario.email,
            "senha": TEST_SENHA,
        })
        r = client.get("/api/v1/logs", headers=auth(token_admin))
        log = r.json()["dados"][0]
        assert "id" in log
        assert "usuario_id" in log
        assert "acao" in log
        assert "entidade" in log
        assert "created_at" in log

    def test_paginacao_por_pagina(self, client, token_admin):
        r = client.get("/api/v1/logs?pagina=1&por_pagina=5", headers=auth(token_admin))
        data = r.json()
        assert data["paginacao"]["itensPorPagina"] == 5

    def test_filtro_por_entidade_e_datas(self, client, token_admin):
        hoje = datetime.now().strftime("%Y-%m-%d")
        r = client.get(f"/api/v1/logs?entidade=usuario&de={hoje}&ate={hoje}", headers=auth(token_admin))
        assert r.status_code == 200
        data = r.json()
        assert data["sucesso"] is True
        for item in data["dados"]:
            assert item["entidade"] == "usuario"

    def test_filtro_data_futura_retorna_vazio(self, client, token_admin):
        r = client.get("/api/v1/logs?de=2099-01-01&ate=2099-12-31", headers=auth(token_admin))
        assert r.status_code == 200
        assert len(r.json()["dados"]) == 0

    def test_payload_nao_contem_senhas(self, client, token_admin):
        r = client.get("/api/v1/logs", headers=auth(token_admin))
        assert r.status_code == 200
        for item in r.json()["dados"]:
            p = item.get("payload")
            if isinstance(p, dict):
                assert "senha" not in p
                assert "senha_hash" not in p
                assert "mfa_secret" not in p

    def test_locatario_nao_pode_acessar_logs_retorna_403(self, client, token_locatario):
        r = client.get("/api/v1/logs", headers=auth(token_locatario))
        assert r.status_code == 403

    def test_sem_autenticacao_retorna_401(self, client):
        r = client.get("/api/v1/logs")
        assert r.status_code == 401


# ── GET /health ───────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_retorna_ok(self, client):
        r = client.get("/api/v1/health")
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["status"] == "ok"
        assert data["dados"]["service"] == "onecheck-api"

    def test_health_sem_autenticacao(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200


# ── GET /uploads/{filename} ───────────────────────────────────────────────────────

class TestServeUpload:
    def test_serve_arquivo_existente(self, client):
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOAD_DIR / "test_serve.jpg").write_bytes(small_image_bytes())
        r = client.get("/api/v1/uploads/test_serve.jpg")
        assert r.status_code == 200

    def test_arquivo_inexistente_retorna_404(self, client):
        r = client.get("/api/v1/uploads/arquivo-que-nao-existe.jpg")
        assert r.status_code == 404


# ── GET /admin/data/status ────────────────────────────────────────────────────────

class TestAdminDataStatus:
    def test_secret_correto_retorna_status(self, client):
        r = client.get("/api/v1/admin/data/status", headers=SEED_HEADER)
        data = r.json()
        assert data["sucesso"] is True
        assert isinstance(data["dados"], dict)

    def test_sem_secret_retorna_403(self, client):
        r = client.get("/api/v1/admin/data/status")
        assert r.status_code == 403

    def test_secret_errado_retorna_403(self, client):
        r = client.get("/api/v1/admin/data/status",
                       headers={"X-Seed-Secret": "secret-invalido"})
        assert r.status_code == 403


# ── POST /admin/seed ──────────────────────────────────────────────────────────────

class TestAdminSeed:
    def test_sem_secret_retorna_403(self, client):
        r = client.post("/api/v1/admin/seed")
        assert r.status_code == 403

    def test_secret_errado_retorna_403(self, client):
        r = client.post("/api/v1/admin/seed",
                        headers={"X-Seed-Secret": "errado"})
        assert r.status_code == 403

    def test_seed_retorna_resposta_json(self, client, db):
        r = client.post("/api/v1/admin/seed", headers=SEED_HEADER)
        assert r.status_code == 200
        data = r.json()
        assert "sucesso" in data

    def test_seed_mode_expand(self, client, db):
        r = client.post("/api/v1/admin/seed",
                        json={"mode": "expand"},
                        headers=SEED_HEADER)
        assert r.status_code == 200
        assert "sucesso" in r.json()

    def test_seed_mode_refresh_data(self, client, db):
        r = client.post("/api/v1/admin/seed",
                        json={"mode": "refresh_data"},
                        headers=SEED_HEADER)
        assert r.status_code == 200
        assert "sucesso" in r.json()


# ── POST /admin/refresh-data ──────────────────────────────────────────────────────

class TestAdminRefreshData:
    def test_sem_secret_retorna_403(self, client):
        r = client.post("/api/v1/admin/refresh-data")
        assert r.status_code == 403

    def test_secret_errado_retorna_403(self, client):
        r = client.post("/api/v1/admin/refresh-data",
                        headers={"X-Seed-Secret": "errado"})
        assert r.status_code == 403

    def test_refresh_retorna_resposta_json(self, client, db):
        r = client.post("/api/v1/admin/refresh-data", headers=SEED_HEADER)
        assert r.status_code == 200
        assert "sucesso" in r.json()

    def test_put_e_patch_tambem_funcionam(self, client, db):
        for method in (client.put, client.patch):
            r = method("/api/v1/admin/refresh-data", headers=SEED_HEADER)
            assert r.status_code == 200
