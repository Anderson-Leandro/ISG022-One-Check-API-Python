"""
Segurança — Item 1: o setup de MFA sobrescrevia o autenticador ativo

Cenário original: GET /auth/mfa/setup gravava o novo segredo direto em
mfa_secret. Abrir a tela "Reconfigurar autenticador" sem concluir o activate
trancava o usuário para fora (o autenticador do celular deixava de valer).
Além disso, quem tivesse só o access token trocava o autenticador da vítima
por um seu (POST /auth/mfa/activate e POST /usuarios/me/mfa/enable), sem
provar posse do autenticador atual.

Regras verificadas:
  - o setup grava só o segredo pendente; o ativo não muda até o activate
  - o activate confirma o código do segredo pendente
  - trocar um autenticador ativo exige o código do autenticador atual (codigo_atual)
"""
import time

import pyotp
import pytest

from app.auth import create_temp_token
from app.models import Usuario
from tests.conftest import MFA_TEST_SECRET, auth, totp_now

AUTH = "/api/v1/auth"
ME = "/api/v1/usuarios/me"


def _codigo_errado(secret: str) -> str:
    """Código fora da janela aceita (atual ± 1 passo) do segredo informado."""
    totp = pyotp.TOTP(secret)
    agora = time.time()
    validos = {totp.at(agora + delta) for delta in (-30, 0, 30)}
    for candidato in ("000000", "111111", "222222", "333333"):
        if candidato not in validos:
            return candidato
    raise AssertionError("sem código inválido disponível")


def _recarregar(db, user):
    db.expire_all()
    return db.query(Usuario).filter(Usuario.id == user.id).first()


def _login_mfa_ok(client, user) -> bool:
    r = client.post(f"{AUTH}/mfa/verify", json={"temp_token": create_temp_token(user.id), "codigo": totp_now()})
    return r.json()["sucesso"] is True


# ── Setup não mexe no autenticador ativo ─────────────────────────────────────────

class TestSetupNaoSobrescreve:
    @pytest.mark.parametrize("metodo", ["get", "post"])
    def test_setup_preserva_segredo_ativo(self, client, db, user_admin, token_admin, metodo):
        r = getattr(client, metodo)(f"{AUTH}/mfa/setup", headers=auth(token_admin))
        assert r.json()["sucesso"] is True
        u = _recarregar(db, user_admin)
        assert u.mfa_secret == MFA_TEST_SECRET
        assert u.mfa_secret_pendente == r.json()["dados"]["secret"]

    def test_setup_abandonado_nao_tranca_o_usuario(self, client, user_admin, token_admin):
        client.get(f"{AUTH}/mfa/setup", headers=auth(token_admin))
        assert _login_mfa_ok(client, user_admin)


# ── Activate em /auth ────────────────────────────────────────────────────────────

class TestActivateTroca:
    def _setup(self, client, token):
        return client.post(f"{AUTH}/mfa/setup", headers=auth(token)).json()["dados"]["secret"]

    def test_troca_sem_codigo_atual_e_recusada(self, client, db, user_admin, token_admin):
        novo = self._setup(client, token_admin)
        r = client.post(f"{AUTH}/mfa/activate", json={"codigo": pyotp.TOTP(novo).now()}, headers=auth(token_admin))
        assert r.json()["sucesso"] is False
        assert _recarregar(db, user_admin).mfa_secret == MFA_TEST_SECRET

    def test_troca_com_codigo_atual_errado_e_recusada(self, client, db, user_admin, token_admin):
        novo = self._setup(client, token_admin)
        r = client.post(
            f"{AUTH}/mfa/activate",
            json={"codigo": pyotp.TOTP(novo).now(), "codigo_atual": _codigo_errado(MFA_TEST_SECRET)},
            headers=auth(token_admin),
        )
        assert r.json()["sucesso"] is False
        assert _recarregar(db, user_admin).mfa_secret == MFA_TEST_SECRET

    def test_troca_com_codigo_novo_errado_e_recusada(self, client, db, user_admin, token_admin):
        novo = self._setup(client, token_admin)
        r = client.post(
            f"{AUTH}/mfa/activate",
            json={"codigo": _codigo_errado(novo), "codigo_atual": totp_now()},
            headers=auth(token_admin),
        )
        assert r.json()["sucesso"] is False
        assert _recarregar(db, user_admin).mfa_secret == MFA_TEST_SECRET

    def test_troca_legitima_promove_o_pendente(self, client, db, user_admin, token_admin):
        novo = self._setup(client, token_admin)
        r = client.post(
            f"{AUTH}/mfa/activate",
            json={"codigo": pyotp.TOTP(novo).now(), "codigo_atual": totp_now()},
            headers=auth(token_admin),
        )
        assert r.json()["sucesso"] is True
        u = _recarregar(db, user_admin)
        assert u.mfa_secret == novo
        assert u.mfa_secret_pendente is None

    def test_activate_sem_setup_pendente_falha(self, client, token_admin):
        r = client.post(
            f"{AUTH}/mfa/activate",
            json={"codigo": totp_now(), "codigo_atual": totp_now()},
            headers=auth(token_admin),
        )
        assert r.json()["sucesso"] is False

    def test_pendente_nao_e_reaproveitado(self, client, db, user_admin, token_admin):
        novo = self._setup(client, token_admin)
        body = {"codigo": pyotp.TOTP(novo).now(), "codigo_atual": totp_now()}
        assert client.post(f"{AUTH}/mfa/activate", json=body, headers=auth(token_admin)).json()["sucesso"] is True
        # segunda chamada: o pendente já foi consumido
        body2 = {"codigo": pyotp.TOTP(novo).now(), "codigo_atual": pyotp.TOTP(novo).now()}
        assert client.post(f"{AUTH}/mfa/activate", json=body2, headers=auth(token_admin)).json()["sucesso"] is False

    def test_primeira_configuracao_nao_exige_codigo_atual(self, client, db, user_locatario, token_locatario):
        novo = self._setup(client, token_locatario)
        r = client.post(f"{AUTH}/mfa/activate", json={"codigo": pyotp.TOTP(novo).now()}, headers=auth(token_locatario))
        assert r.json()["sucesso"] is True
        u = _recarregar(db, user_locatario)
        assert u.mfa_secret == novo
        assert u.mfa_enabled is True


# ── Enable em /usuarios/me ───────────────────────────────────────────────────────

class TestEnableMe:
    def test_troca_sem_codigo_atual_e_recusada(self, client, db, user_admin, token_admin):
        novo = pyotp.random_base32()
        r = client.post(
            f"{ME}/mfa/enable",
            json={"secret": novo, "codigo": pyotp.TOTP(novo).now()},
            headers=auth(token_admin),
        )
        assert r.json()["sucesso"] is False
        assert _recarregar(db, user_admin).mfa_secret == MFA_TEST_SECRET

    def test_troca_com_codigo_atual_errado_e_recusada(self, client, db, user_admin, token_admin):
        novo = pyotp.random_base32()
        r = client.post(
            f"{ME}/mfa/enable",
            json={"secret": novo, "codigo": pyotp.TOTP(novo).now(), "codigo_atual": _codigo_errado(MFA_TEST_SECRET)},
            headers=auth(token_admin),
        )
        assert r.json()["sucesso"] is False
        assert _recarregar(db, user_admin).mfa_secret == MFA_TEST_SECRET

    def test_troca_com_codigo_atual(self, client, db, user_admin, token_admin):
        novo = pyotp.random_base32()
        r = client.post(
            f"{ME}/mfa/enable",
            json={"secret": novo, "codigo": pyotp.TOTP(novo).now(), "codigo_atual": totp_now()},
            headers=auth(token_admin),
        )
        assert r.json()["sucesso"] is True
        assert _recarregar(db, user_admin).mfa_secret == novo

    def test_primeira_configuracao_nao_exige_codigo_atual(self, client, db, user_locatario, token_locatario):
        novo = pyotp.random_base32()
        r = client.post(
            f"{ME}/mfa/enable",
            json={"secret": novo, "codigo": pyotp.TOTP(novo).now()},
            headers=auth(token_locatario),
        )
        assert r.json()["sucesso"] is True
        assert _recarregar(db, user_locatario).mfa_secret == novo
