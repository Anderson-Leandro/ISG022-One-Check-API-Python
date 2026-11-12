"""
DEBT-013 — Mensagem específica para o token de verificação usado no setup-login e no activate-login

Cenário original: GET /auth/mfa/setup-login e POST /auth/mfa/activate-login respondiam "Token MFA inválido ou
expirado" tanto para um token ilegível ou expirado quanto para um token válido do tipo "mfa" (emitido para
quem já tem autenticador). A recusa é correta (falha N1, SEC-021), mas a mensagem confundia quem integra a API.

Regras verificadas:
  - token válido do tipo "mfa": 401 com a mensagem que aponta para /auth/mfa/verify, nas duas rotas
  - nenhum segredo é gerado nem alterado
  - token ilegível, com assinatura inválida ou expirado: a mensagem continua genérica
  - a recusa do token "mfa" acontece antes de consultar o usuário no banco
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth import create_temp_token
from app.config import JWT_SECRET
from app.models import Usuario
from app.routers.auth_router import TOKEN_DE_VERIFICACAO, TOKEN_MFA_INVALIDO
from tests.conftest import totp_now

AUTH = "/api/v1/auth"
GENERICA = TOKEN_MFA_INVALIDO
VERIFICACAO = TOKEN_DE_VERIFICACAO


def _setup_login(client, token):
    return client.get(f"{AUTH}/mfa/setup-login", params={"temp_token": token})


def _activate_login(client, token):
    return client.post(f"{AUTH}/mfa/activate-login", json={"temp_token": token, "codigo": totp_now()})


ROTAS = [_setup_login, _activate_login]


class TestTokenDeVerificacao:
    def test_mensagem_aponta_o_caminho_completo_da_api(self):
        assert "POST /api/v1/auth/mfa/verify" in VERIFICACAO

    @pytest.mark.parametrize("rota", ROTAS, ids=["setup-login", "activate-login"])
    def test_recusa_com_a_mensagem_especifica(self, client, db, user_admin, rota):
        segredo, pendente = user_admin.mfa_secret, user_admin.mfa_secret_pendente
        r = rota(client, create_temp_token(user_admin.id, user_admin.token_version))
        assert r.status_code == 401
        assert r.json()["sucesso"] is False and r.json()["erro"] == VERIFICACAO
        db.expire_all()
        u = db.get(Usuario, user_admin.id)
        assert u.mfa_secret == segredo and u.mfa_secret_pendente == pendente

    @pytest.mark.parametrize("rota", ROTAS, ids=["setup-login", "activate-login"])
    def test_recusa_antes_de_consultar_o_usuario(self, client, rota):
        # o usuário do token nem existe: a resposta só depende do tipo, sem revelar se a conta existe
        r = rota(client, create_temp_token("00000000-0000-0000-0000-000000000000"))
        assert r.status_code == 401 and r.json()["erro"] == VERIFICACAO


class TestOutrosTokensContinuamGenericos:
    @pytest.mark.parametrize("rota", ROTAS, ids=["setup-login", "activate-login"])
    @pytest.mark.parametrize(
        "token",
        [
            "nao-e-um-jwt",
            jwt.encode(
                {"sub": "x", "type": "mfa", "exp": datetime.now(UTC) + timedelta(minutes=5)},
                "outra-chave-qualquer-com-32-caracteres!!",
                algorithm="HS256",
            ),
            jwt.encode(
                {"sub": "x", "type": "mfa", "exp": datetime.now(UTC) - timedelta(minutes=5)},
                JWT_SECRET,
                algorithm="HS256",
            ),
        ],
        ids=["ilegivel", "assinatura-invalida", "expirado"],
    )
    def test_mensagem_generica(self, client, rota, token):
        r = rota(client, token)
        assert r.status_code == 401 and r.json()["erro"] == GENERICA
