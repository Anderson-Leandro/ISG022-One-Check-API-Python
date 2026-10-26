"""
Segurança — SEC-005: troca de senha e reset de MFA não revogavam as sessões

Cenário original: verify_refresh_token só conferia hash, validade e usuário
ativo, e o access token só a assinatura. Se a vítima (ou o admin) trocasse a
senha ou resetasse o MFA depois de um roubo de sessão, o refresh token do
atacante continuava emitindo access tokens por até 30 dias.

Regras verificadas:
  - troca de senha, de autenticador, desativação de MFA, reset de MFA, mudança de
    perfil e desativação da conta encerram todas as sessões (access e refresh)
  - nas trocas feitas pelo próprio usuário, a resposta traz uma sessão nova
  - tokens de MFA emitidos antes da troca também deixam de valer
  - mudanças que não são de credencial (ex.: nome) não derrubam a sessão
  - a sessão de outros usuários não é afetada
"""
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from jose import jwt

from app.auth import create_access_token, create_refresh_token, create_temp_token
from app.config import JWT_ALGORITHM, JWT_SECRET
from app.models import Usuario
from tests.conftest import TEST_SENHA, auth, totp_now

ME = "/api/v1/usuarios/me"
NOVA = "senha-nova-forte-123"


def _sessao(db, user) -> dict:
    """Sessão como a emitida pelo login (versão atual do usuário)."""
    return {
        "access": create_access_token(user.id, user.role, user.token_version),
        "refresh": create_refresh_token(db, user.id),
    }


def _ativa(client, sessao) -> bool:
    return client.get(ME, headers=auth(sessao["access"])).status_code == 200


def _refresh_ok(client, sessao) -> bool:
    return client.post("/api/v1/auth/refresh", json={"refresh_token": sessao["refresh"]}).json()["sucesso"] is True


def _encerrada(client, sessao) -> bool:
    return not _ativa(client, sessao) and not _refresh_ok(client, sessao)


def _nova_valida(client, dados) -> bool:
    nova = {"access": dados["sessao"]["access_token"], "refresh": dados["sessao"]["refresh_token"]}
    return _ativa(client, nova) and _refresh_ok(client, nova)


# ── Ações do próprio usuário ─────────────────────────────────────────────────────

class TestProprioUsuario:
    def test_put_senha(self, client, db, user_locatario):
        s = _sessao(db, user_locatario)
        r = client.put(f"{ME}/senha", json={"senha_atual": TEST_SENHA, "nova_senha": NOVA}, headers=auth(s["access"]))
        assert r.json()["sucesso"] is True
        assert _encerrada(client, s)
        assert _nova_valida(client, r.json()["dados"])

    def test_patch_me_com_senha(self, client, db, user_locatario):
        s = _sessao(db, user_locatario)
        r = client.patch(ME, json={"senha_atual": TEST_SENHA, "senha_nova": NOVA}, headers=auth(s["access"]))
        assert r.json()["sucesso"] is True
        assert _encerrada(client, s)
        assert _nova_valida(client, r.json()["dados"])

    def test_patch_me_so_nome_mantem_sessao(self, client, db, user_locatario):
        s = _sessao(db, user_locatario)
        r = client.patch(ME, json={"nome": "Novo Nome"}, headers=auth(s["access"]))
        assert "sessao" not in r.json()["dados"]
        assert _ativa(client, s) and _refresh_ok(client, s)

    def test_senha_atual_errada_nao_derruba(self, client, db, user_locatario):
        s = _sessao(db, user_locatario)
        client.put(f"{ME}/senha", json={"senha_atual": "errada", "nova_senha": NOVA}, headers=auth(s["access"]))
        assert _ativa(client, s)

    def test_todas_as_sessoes_sao_encerradas(self, client, db, user_locatario):
        celular, notebook = _sessao(db, user_locatario), _sessao(db, user_locatario)
        client.put(f"{ME}/senha", json={"senha_atual": TEST_SENHA, "nova_senha": NOVA}, headers=auth(notebook["access"]))
        assert _encerrada(client, celular)

    def test_troca_de_autenticador(self, client, db, user_admin):
        s = _sessao(db, user_admin)
        novo = pyotp.random_base32()
        r = client.post(f"{ME}/mfa/enable", headers=auth(s["access"]),
                        json={"secret": novo, "codigo": pyotp.TOTP(novo).now(), "codigo_atual": totp_now()})
        assert r.json()["sucesso"] is True
        assert _encerrada(client, s)
        assert _nova_valida(client, r.json()["dados"])

    def test_troca_de_autenticador_via_auth_activate(self, client, db, user_admin):
        s = _sessao(db, user_admin)
        novo = client.post("/api/v1/auth/mfa/setup", headers=auth(s["access"])).json()["dados"]["secret"]
        r = client.post("/api/v1/auth/mfa/activate", headers=auth(s["access"]),
                        json={"codigo": pyotp.TOTP(novo).now(), "codigo_atual": totp_now()})
        assert r.json()["sucesso"] is True
        assert _encerrada(client, s)
        assert _nova_valida(client, r.json()["dados"])

    @pytest.mark.parametrize("rota", ["delete_me_mfa", "auth_desabilitar"])
    def test_desativar_mfa(self, client, db, user_locatario, rota):
        user_locatario.mfa_enabled, user_locatario.mfa_secret = True, pyotp.random_base32()
        db.flush()
        s = _sessao(db, user_locatario)
        body = {"senha": TEST_SENHA, "codigo": pyotp.TOTP(user_locatario.mfa_secret).now()}
        if rota == "delete_me_mfa":
            r = client.request("DELETE", f"{ME}/mfa", json=body, headers=auth(s["access"]))
        else:
            r = client.post("/api/v1/auth/mfa/desabilitar", json=body, headers=auth(s["access"]))
        assert r.json()["sucesso"] is True
        assert _encerrada(client, s)
        assert _nova_valida(client, r.json()["dados"])


# ── Ações do administrador sobre outro usuário ──────────────────────────────────

class TestAdministrador:
    @pytest.mark.parametrize("body", [{"senha": NOVA}, {"role": "visualizador"}], ids=["senha", "perfil"])
    def test_put_usuario_com_credencial(self, client, db, user_locatario, token_admin, body):
        s = _sessao(db, user_locatario)
        r = client.put(f"/api/v1/usuarios/{user_locatario.id}", json=body, headers=auth(token_admin))
        assert r.json()["sucesso"] is True
        assert _encerrada(client, s)

    def test_put_usuario_so_nome_mantem_sessao(self, client, db, user_locatario, token_admin):
        s = _sessao(db, user_locatario)
        client.put(f"/api/v1/usuarios/{user_locatario.id}", json={"nome": "Outro"}, headers=auth(token_admin))
        assert _ativa(client, s) and _refresh_ok(client, s)

    @pytest.mark.parametrize("rota", ["usuarios_delete", "usuarios_desabilitar", "auth_disable"])
    def test_reset_de_mfa(self, client, db, user_vistoriador, token_admin, rota):
        s = _sessao(db, user_vistoriador)
        if rota == "usuarios_delete":
            r = client.delete(f"/api/v1/usuarios/{user_vistoriador.id}/mfa", headers=auth(token_admin))
        elif rota == "usuarios_desabilitar":
            r = client.post(f"/api/v1/usuarios/{user_vistoriador.id}/mfa/desabilitar", headers=auth(token_admin))
        else:
            r = client.post("/api/v1/auth/mfa/disable", json={"usuario_id": user_vistoriador.id}, headers=auth(token_admin))
        assert r.json()["sucesso"] is True
        assert _encerrada(client, s)

    def test_desativar_conta(self, client, db, user_locatario, token_admin):
        s = _sessao(db, user_locatario)
        client.delete(f"/api/v1/usuarios/{user_locatario.id}", headers=auth(token_admin))
        assert _encerrada(client, s)

    def test_sessao_de_outro_usuario_nao_e_afetada(self, client, db, user_locatario, user_visualizador, token_admin):
        alheia = _sessao(db, user_visualizador)
        client.put(f"/api/v1/usuarios/{user_locatario.id}", json={"senha": NOVA}, headers=auth(token_admin))
        assert _ativa(client, alheia) and _refresh_ok(client, alheia)


# ── Tokens de MFA e compatibilidade ─────────────────────────────────────────────

class TestTokensDeMfa:
    def test_temp_token_anterior_ao_reset_e_recusado(self, client, db, user_vistoriador, token_admin):
        temp = create_temp_token(user_vistoriador.id, user_vistoriador.token_version)
        client.put(f"/api/v1/usuarios/{user_vistoriador.id}", json={"senha": NOVA}, headers=auth(token_admin))
        r = client.post("/api/v1/auth/mfa/verify", json={"temp_token": temp, "codigo": totp_now()})
        assert r.json()["sucesso"] is False

    def test_login_novo_funciona_apos_troca(self, client, db, user_vistoriador, token_admin):
        client.put(f"/api/v1/usuarios/{user_vistoriador.id}", json={"senha": NOVA}, headers=auth(token_admin))
        temp = client.post("/api/v1/auth/login", json={"email": user_vistoriador.email, "senha": NOVA}).json()["dados"]["temp_token"]
        r = client.post("/api/v1/auth/mfa/verify", json={"temp_token": temp, "codigo": totp_now()})
        assert r.json()["sucesso"] is True
        assert client.get(ME, headers=auth(r.json()["dados"]["access_token"])).status_code == 200

    def test_token_emitido_antes_do_deploy_continua_valido(self, client, db, user_locatario):
        # Tokens antigos não têm "ver"; valem até a primeira troca de credencial
        antigo = jwt.encode({"sub": user_locatario.id, "role": "locatario", "type": "access",
                             "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, JWT_SECRET, algorithm=JWT_ALGORITHM)
        assert client.get(ME, headers=auth(antigo)).status_code == 200
        db.expire_all()
        u = db.query(Usuario).filter(Usuario.id == user_locatario.id).first()
        u.token_version = 1
        db.flush()
        assert client.get(ME, headers=auth(antigo)).status_code == 401
