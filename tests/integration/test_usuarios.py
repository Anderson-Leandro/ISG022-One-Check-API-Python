"""
Fase 2.2 — Testes de integração das rotas de usuários

Rotas cobertas:
  GET    /api/v1/usuarios/me
  PATCH  /api/v1/usuarios/me
  POST   /api/v1/usuarios/me/mfa/setup
  POST   /api/v1/usuarios/me/mfa/enable
  DELETE /api/v1/usuarios/me/mfa
  GET    /api/v1/usuarios
  GET    /api/v1/usuarios/{id}
  PUT    /api/v1/usuarios/{id}
  POST   /api/v1/usuarios/{id}/mfa/setup
  POST   /api/v1/usuarios/{id}/mfa/enable
  DELETE /api/v1/usuarios/{id}/mfa
  POST   /api/v1/usuarios
"""
import pytest

from tests.conftest import MFA_TEST_SECRET, TEST_SENHA, auth, totp_now

BASE = "/api/v1/usuarios"


# ── GET /me ───────────────────────────────────────────────────────────────────────

class TestMe:
    def test_me_retorna_dados_do_usuario(self, client, user_locatario, token_locatario):
        r = client.get(f"{BASE}/me", headers=auth(token_locatario))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["email"] == user_locatario.email
        assert data["dados"]["role"] == "locatario"

    def test_me_sem_autenticacao_retorna_401(self, client):
        r = client.get(f"{BASE}/me")
        assert r.status_code == 401

    def test_me_contem_campos_de_mfa(self, client, token_admin):
        r = client.get(f"{BASE}/me", headers=auth(token_admin))
        data = r.json()
        assert "mfa_ativo" in data["dados"]
        assert "mfa_enabled" in data["dados"]
        assert "mfa_configurado" in data["dados"]


# ── PATCH /me ─────────────────────────────────────────────────────────────────────

class TestUpdateMe:
    def test_atualiza_nome(self, client, db, user_locatario, token_locatario):
        r = client.patch(
            f"{BASE}/me",
            json={"nome": "Novo Nome"},
            headers=auth(token_locatario),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["nome"] == "Novo Nome"

    def test_atualiza_senha_com_senha_atual_correta(self, client, user_locatario, token_locatario):
        r = client.patch(
            f"{BASE}/me",
            json={"senha_atual": TEST_SENHA, "senha_nova": "novasenha456"},
            headers=auth(token_locatario),
        )
        data = r.json()
        assert data["sucesso"] is True

    def test_atualiza_senha_com_senha_atual_errada(self, client, token_locatario):
        r = client.patch(
            f"{BASE}/me",
            json={"senha_atual": "senhaerrada", "senha_nova": "novasenha456"},
            headers=auth(token_locatario),
        )
        data = r.json()
        assert data["sucesso"] is False
        assert "incorreta" in data["erro"].lower()

    def test_atualiza_senha_nova_sem_informar_atual(self, client, token_locatario):
        r = client.patch(
            f"{BASE}/me",
            json={"senha_nova": "novasenha456"},
            headers=auth(token_locatario),
        )
        data = r.json()
        assert data["sucesso"] is False
        assert "atual" in data["erro"].lower()

    def test_nome_vazio_retorna_falha(self, client, token_locatario):
        r = client.patch(
            f"{BASE}/me",
            json={"nome": "   "},
            headers=auth(token_locatario),
        )
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client):
        r = client.patch(f"{BASE}/me", json={"nome": "X"})
        assert r.status_code == 401


# ── POST /me/mfa/setup ────────────────────────────────────────────────────────────

class TestMfaSetupMe:
    def test_setup_retorna_secret_e_uri(self, client, token_locatario):
        r = client.post(f"{BASE}/me/mfa/setup", headers=auth(token_locatario))
        data = r.json()
        assert data["sucesso"] is True
        assert "secret" in data["dados"]
        assert "provisioning_uri" in data["dados"]
        assert "qr_url" in data["dados"]

    def test_sem_autenticacao_retorna_401(self, client):
        r = client.post(f"{BASE}/me/mfa/setup")
        assert r.status_code == 401


# ── POST /me/mfa/enable ───────────────────────────────────────────────────────────

class TestMfaEnableMe:
    def test_enable_com_codigo_valido(self, client, db, user_locatario, token_locatario):
        r = client.post(
            f"{BASE}/me/mfa/enable",
            json={"secret": MFA_TEST_SECRET, "codigo": totp_now()},
            headers=auth(token_locatario),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["mfa_ativo"] is True
        assert data["dados"]["mfa_configurado"] is True

    def test_enable_com_codigo_invalido(self, client, token_locatario):
        if totp_now() == "000000":
            pytest.skip("000000 é o código TOTP atual — skip")
        r = client.post(
            f"{BASE}/me/mfa/enable",
            json={"secret": MFA_TEST_SECRET, "codigo": "000000"},
            headers=auth(token_locatario),
        )
        data = r.json()
        assert data["sucesso"] is False
        assert "inválido" in data["erro"].lower()

    def test_sem_autenticacao_retorna_401(self, client):
        r = client.post(f"{BASE}/me/mfa/enable", json={"secret": MFA_TEST_SECRET, "codigo": "000000"})
        assert r.status_code == 401


# ── DELETE /me/mfa ────────────────────────────────────────────────────────────────

class TestMfaDisableMe:
    def test_disable_remove_mfa(self, client, db, user_locatario, token_locatario):
        # Perfil com MFA opcional e reautenticação; perfis obrigatórios: test_seguranca_mfa_desativacao.py
        user_locatario.mfa_enabled = True
        user_locatario.mfa_secret = MFA_TEST_SECRET
        db.flush()
        r = client.request(
            "DELETE", f"{BASE}/me/mfa",
            json={"senha": TEST_SENHA, "codigo": totp_now()},
            headers=auth(token_locatario),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["mfa_ativo"] is False
        assert data["dados"]["mfa_configurado"] is False

    def test_sem_autenticacao_retorna_401(self, client):
        r = client.delete(f"{BASE}/me/mfa")
        assert r.status_code == 401


# ── GET /usuarios (listagem) ──────────────────────────────────────────────────────

class TestListUsuarios:
    def test_lista_usuarios_gestor(self, client, user_locatario, token_gestor):
        r = client.get(BASE, headers=auth(token_gestor))
        data = r.json()
        assert data["sucesso"] is True
        assert isinstance(data["dados"], list)
        assert len(data["dados"]) >= 1

    def test_lista_com_paginacao(self, client, user_admin, token_admin):
        r = client.get(f"{BASE}?pagina=1&por_pagina=5", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert "paginacao" in data
        assert data["paginacao"]["pagina"] == 1

    def test_filtra_por_role(self, client, user_admin, user_locatario, token_admin):
        r = client.get(f"{BASE}?role=locatario", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        for u in data["dados"]:
            assert u["role"] == "locatario"

    def test_sem_autenticacao_retorna_401(self, client):
        r = client.get(BASE)
        assert r.status_code == 401


# ── GET /usuarios/{id} ────────────────────────────────────────────────────────────

class TestGetUsuario:
    def test_admin_busca_usuario_por_id(self, client, user_locatario, token_admin):
        r = client.get(f"{BASE}/{user_locatario.id}", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["id"] == user_locatario.id

    def test_gestor_busca_usuario_por_id(self, client, user_locatario, token_gestor):
        r = client.get(f"{BASE}/{user_locatario.id}", headers=auth(token_gestor))
        data = r.json()
        assert data["sucesso"] is True

    def test_locatario_nao_pode_buscar_por_id(self, client, user_admin, token_locatario):
        r = client.get(f"{BASE}/{user_admin.id}", headers=auth(token_locatario))
        assert r.status_code == 403

    def test_id_inexistente_retorna_falha(self, client, token_admin):
        r = client.get(f"{BASE}/id-que-nao-existe", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "encontrado" in data["erro"].lower()

    def test_sem_autenticacao_retorna_401(self, client, user_locatario):
        r = client.get(f"{BASE}/{user_locatario.id}")
        assert r.status_code == 401


# ── PUT /usuarios/{id} ────────────────────────────────────────────────────────────

class TestUpdateUsuario:
    def test_admin_atualiza_nome(self, client, user_locatario, token_admin):
        r = client.put(
            f"{BASE}/{user_locatario.id}",
            json={"nome": "Nome Atualizado"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["nome"] == "Nome Atualizado"

    def test_admin_atualiza_role(self, client, user_locatario, token_admin):
        r = client.put(
            f"{BASE}/{user_locatario.id}",
            json={"role": "visualizador"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["role"] == "visualizador"

    def test_desativar_mfa_limpa_secret(self, client, db, user_locatario, token_admin):
        # Perfil com MFA opcional; em perfis obrigatórios o PUT recusa (test_seguranca_mfa_desativacao.py)
        user_locatario.mfa_enabled = True
        user_locatario.mfa_secret = MFA_TEST_SECRET
        db.flush()
        r = client.put(
            f"{BASE}/{user_locatario.id}",
            json={"mfa_enabled": False},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["mfa_ativo"] is False

    def test_vistoriador_nao_pode_atualizar(self, client, user_locatario, token_vistoriador):
        r = client.put(
            f"{BASE}/{user_locatario.id}",
            json={"nome": "X"},
            headers=auth(token_vistoriador),
        )
        assert r.status_code == 403

    def test_id_inexistente_retorna_falha(self, client, token_admin):
        r = client.put(
            f"{BASE}/id-inexistente",
            json={"nome": "X"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is False


# ── POST /usuarios (criar) ────────────────────────────────────────────────────────

class TestCreateUsuario:
    def test_admin_cria_usuario(self, client, token_admin):
        r = client.post(
            BASE,
            json={"nome": "Novo User", "email": "novo@test.com", "senha": "senha123", "role": "locatario"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["email"] == "novo@test.com"
        assert data["dados"]["role"] == "locatario"

    def test_gestor_cria_usuario(self, client, token_gestor):
        r = client.post(
            BASE,
            json={"nome": "User Gestor", "email": "usergestor@test.com", "senha": "senha123", "role": "locatario"},
            headers=auth(token_gestor),
        )
        data = r.json()
        assert data["sucesso"] is True

    def test_email_duplicado_retorna_falha(self, client, user_locatario, token_admin):
        r = client.post(
            BASE,
            json={"nome": "Duplicado", "email": user_locatario.email, "senha": "senha123", "role": "locatario"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is False
        assert "cadastrado" in data["erro"].lower()

    def test_role_admin_ativa_mfa_automaticamente(self, client, token_admin):
        r = client.post(
            BASE,
            json={"nome": "Novo Admin", "email": "novoadmin@test.com", "senha": "senha123", "role": "admin"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["mfa_enabled"] is True

    def test_role_locatario_nao_ativa_mfa(self, client, token_admin):
        r = client.post(
            BASE,
            json={"nome": "Loc Sem Mfa", "email": "locsemmfa@test.com", "senha": "senha123", "role": "locatario"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["mfa_enabled"] is False

    def test_locatario_nao_pode_criar_usuario(self, client, token_locatario):
        r = client.post(
            BASE,
            json={"nome": "X", "email": "x@x.com", "senha": "senha123", "role": "locatario"},
            headers=auth(token_locatario),
        )
        assert r.status_code == 403

    def test_sem_autenticacao_retorna_401(self, client):
        r = client.post(
            BASE,
            json={"nome": "X", "email": "x@x.com", "senha": "senha123", "role": "locatario"},
        )
        assert r.status_code == 401


# ── POST /usuarios/{id}/mfa/setup e enable e DELETE /mfa ─────────────────────────

class TestMfaAdminRoutes:
    def test_admin_faz_setup_mfa_de_usuario(self, client, user_locatario, token_admin):
        r = client.post(f"{BASE}/{user_locatario.id}/mfa/setup", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert "secret" in data["dados"]

    def test_setup_usuario_inexistente(self, client, token_admin):
        r = client.post(f"{BASE}/id-invalido/mfa/setup", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False

    def test_admin_habilita_mfa_de_usuario(self, client, user_locatario, token_admin):
        r = client.post(
            f"{BASE}/{user_locatario.id}/mfa/enable",
            json={"secret": MFA_TEST_SECRET, "codigo": totp_now()},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["mfa_ativo"] is True

    def test_admin_reseta_mfa_de_usuario(self, client, user_vistoriador, token_admin):
        # user_vistoriador já tem MFA configurado; o próprio MFA não se reseta por esta rota
        r = client.delete(f"{BASE}/{user_vistoriador.id}/mfa", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["mfa_ativo"] is False

    def test_locatario_nao_pode_resetar_mfa_de_outro(self, client, user_admin, token_locatario):
        r = client.delete(f"{BASE}/{user_admin.id}/mfa", headers=auth(token_locatario))
        assert r.status_code == 403

    def test_admin_habilita_e_desabilita_mfa_rotas_alternativas(self, client, user_locatario, token_admin):
        r_hab = client.post(f"{BASE}/{user_locatario.id}/mfa/habilitar", headers=auth(token_admin))
        assert r_hab.json()["sucesso"] is True
        assert r_hab.json()["dados"]["mfa_enabled"] is True

        r_des = client.post(f"{BASE}/{user_locatario.id}/mfa/desabilitar", headers=auth(token_admin))
        assert r_des.json()["sucesso"] is True
        assert r_des.json()["dados"]["mfa_enabled"] is False


# ── PUT /me/senha ─────────────────────────────────────────────────────────────────

class TestAlterarSenhaDedicada:
    def test_alterar_senha_sucesso(self, client, user_locatario, token_locatario):
        r = client.put(
            f"{BASE}/me/senha",
            json={"senha_atual": TEST_SENHA, "nova_senha": "NovaSenhaFase3@123"},
            headers=auth(token_locatario),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert "mensagem" in data["dados"]

    def test_alterar_senha_atual_incorreta(self, client, token_locatario):
        r = client.put(
            f"{BASE}/me/senha",
            json={"senha_atual": "senha_errada", "nova_senha": "NovaSenhaFase3@123"},
            headers=auth(token_locatario),
        )
        data = r.json()
        assert data["sucesso"] is False
        assert "incorreta" in data["erro"].lower()


# ── DELETE /usuarios/{id} (Soft Delete) ───────────────────────────────────────────

class TestDeleteUsuario:
    def test_admin_desativa_usuario(self, client, db, token_admin):
        from app.models import Usuario
        from tests.conftest import _SENHA_HASH
        u = Usuario(
            nome="Para Desativar",
            email="desativar@test.com",
            senha_hash=_SENHA_HASH,
            role="locatario",
            ativo=True,
        )
        db.add(u)
        db.flush()

        r = client.delete(f"{BASE}/{u.id}", headers=auth(token_admin))
        assert r.json()["sucesso"] is True

        # Verificar que usuário está inativo no banco
        db.refresh(u)
        assert u.ativo is False

    def test_admin_nao_pode_desativar_propria_conta(self, client, user_admin, token_admin):
        r = client.delete(f"{BASE}/{user_admin.id}", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "própria" in data["erro"].lower()

    def test_desativar_usuario_inexistente(self, client, token_admin):
        r = client.delete(f"{BASE}/00000000-0000-0000-0000-000000000000", headers=auth(token_admin))
        assert r.json()["sucesso"] is False

    def test_locatario_nao_pode_desativar_usuario(self, client, user_admin, token_locatario):
        r = client.delete(f"{BASE}/{user_admin.id}", headers=auth(token_locatario))
        assert r.status_code == 403


# ── Validação de duplicidade de email no PUT ──────────────────────────────────────

class TestUpdateUsuarioEmail:
    def test_update_email_duplicado_retorna_erro(self, client, user_locatario, user_gestor, token_admin):
        r = client.put(
            f"{BASE}/{user_locatario.id}",
            json={"email": user_gestor.email},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is False
        assert "já está cadastrado" in data["erro"].lower()
