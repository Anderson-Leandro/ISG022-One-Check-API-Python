"""
Segurança — SEC-035: o QR do setup de MFA é gerado pela própria API

Antes, mfa_provisioning_data devolvia qr_url apontando para https://api.qrserver.com com o otpauth:// na
query string: quem abria o QR entregava a semente TOTP e o e-mail da conta a um serviço externo. Agora o QR
vem como data URI (PNG) gerado pela API. O campo continua com o mesmo nome e funciona em <img src>.
"""

import re

import pytest

from app.auth import create_mfa_setup_token, mfa_provisioning_data
from app.models import Usuario
from tests.conftest import _SENHA_HASH, auth

API = "/api/v1"


def _confere_sem_vazamento(dados):
    secret = dados["secret"]
    corpo = str({k: v for k, v in dados.items() if k != "secret" and k not in ("provisioning_uri", "otpauth_uri")})
    assert not re.search(r"https?://", corpo), "a resposta do setup não pode trazer URL externa"
    assert "qrserver" not in corpo
    assert secret not in dados["qr_url"]
    assert dados["qr_url"].startswith("data:image/png;base64,")


def test_qr_e_data_uri_local_sem_o_segredo():
    dados = mfa_provisioning_data("usuario@test.com", "JBSWY3DPEHPK3PXP")
    _confere_sem_vazamento(dados)


def test_qr_e_um_png_valido_do_otpauth_uri():
    """O PNG decodifica (assinatura e dimensões) e é o QR do provisioning_uri, não do segredo isolado."""
    import base64
    import io

    import segno
    from PIL import Image

    dados = mfa_provisioning_data("usuario@test.com", "JBSWY3DPEHPK3PXP")
    png = base64.b64decode(dados["qr_url"].split(",", 1)[1])
    with Image.open(io.BytesIO(png)) as im:
        assert im.format == "PNG" and im.size[0] == im.size[1] >= 150
    assert dados["qr_url"] == segno.make(dados["provisioning_uri"], error="m").png_data_uri(scale=5, border=4)
    assert dados["qr_url"] != segno.make("JBSWY3DPEHPK3PXP", error="m").png_data_uri(scale=5, border=4)


@pytest.fixture
def novo_vistoriador(db):
    u = Usuario(
        nome="Novo",
        email="novo.qr@test.com",
        senha_hash=_SENHA_HASH,
        role="vistoriador",
        mfa_enabled=True,
        mfa_secret=None,
        ativo=True,
    )
    db.add(u)
    db.flush()
    return u


@pytest.mark.parametrize("rota", ["auth_setup", "setup_login", "usuarios_me_setup"])
def test_rotas_de_setup_nao_apontam_para_servico_externo(client, novo_vistoriador, token_locatario, rota):
    if rota == "auth_setup":
        r = client.post(f"{API}/auth/mfa/setup", headers=auth(token_locatario))
    elif rota == "setup_login":
        token = create_mfa_setup_token(novo_vistoriador.id, novo_vistoriador.token_version)
        r = client.get(f"{API}/auth/mfa/setup-login", params={"temp_token": token})
    else:
        r = client.post(f"{API}/usuarios/me/mfa/setup", headers=auth(token_locatario))
    assert r.status_code == 200, r.text
    _confere_sem_vazamento(r.json()["dados"])
