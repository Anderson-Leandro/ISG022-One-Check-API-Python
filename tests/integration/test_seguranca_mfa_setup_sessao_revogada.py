"""
Segurança — SEC-034: token de primeiro acesso emitido antes de uma troca de credencial

A avaliação SPK-005 (docs/quality/avaliacao-testes-2026-11-02.md, seção 1) mostrou que o ramo
"sessao_vigente falso" de GET /auth/mfa/setup-login e POST /auth/mfa/activate-login nunca era
executado. Um token mfa_setup vale 10 minutos; se a senha mudar nesse intervalo (o dono percebeu o
vazamento), o token antigo não pode mais configurar o autenticador.

Cada teste deixa o cenário pronto para o setup dar certo (segredo pendente e código válido), de modo
que só a checagem da sessão impede a configuração.
"""
import pytest

from app.auth import create_mfa_setup_token
from app.models import Usuario
from tests.conftest import _SENHA_HASH, MFA_TEST_SECRET, auth, totp_now

API = "/api/v1"
NOVA = "NovaSenha#2026segura"


@pytest.fixture
def novo_vistoriador(db):
    """Vistoriador no primeiro acesso: MFA obrigatório, ainda sem autenticador."""
    u = Usuario(nome="Novo Vistoriador", email="novo.vist@test.com", senha_hash=_SENHA_HASH,
                role="vistoriador", mfa_enabled=True, mfa_secret=None, ativo=True)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def token_antigo(client, db, novo_vistoriador, token_admin):
    """Token mfa_setup emitido e, logo depois, a senha trocada pelo admin (encerra as sessões)."""
    token = create_mfa_setup_token(novo_vistoriador.id, novo_vistoriador.token_version)
    r = client.put(f"{API}/usuarios/{novo_vistoriador.id}", json={"senha": NOVA}, headers=auth(token_admin))
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(Usuario, novo_vistoriador.id).token_version == 1
    return token


def _usuario(db, id_):
    db.expire_all()
    return db.get(Usuario, id_)


class TestSetupLoginComTokenAntigo:
    def test_recusado_e_nenhum_segredo_pendente_gravado(self, client, db, novo_vistoriador, token_antigo):
        r = client.get(f"{API}/auth/mfa/setup-login", params={"temp_token": token_antigo})

        assert r.status_code == 401, r.text
        assert r.json()["detail"] == "Token MFA inválido ou expirado"
        u = _usuario(db, novo_vistoriador.id)
        assert (u.mfa_secret_pendente, u.mfa_secret) == (None, None)

    def test_token_novo_depois_da_troca_funciona(self, client, db, novo_vistoriador, token_antigo):
        """Controle positivo: o mesmo pedido com um token emitido depois da troca configura o setup."""
        u = _usuario(db, novo_vistoriador.id)
        novo = create_mfa_setup_token(u.id, u.token_version)

        r = client.get(f"{API}/auth/mfa/setup-login", params={"temp_token": novo})

        assert r.status_code == 200, r.text
        assert _usuario(db, novo_vistoriador.id).mfa_secret_pendente is not None


class TestActivateLoginComTokenAntigo:
    def test_recusado_e_autenticador_nao_ativado(self, client, db, novo_vistoriador, token_antigo):
        u = _usuario(db, novo_vistoriador.id)
        u.mfa_secret_pendente = MFA_TEST_SECRET
        db.flush()

        r = client.post(f"{API}/auth/mfa/activate-login", json={"temp_token": token_antigo, "codigo": totp_now()})

        assert r.status_code == 401, r.text
        assert r.json()["erro"] == "Token MFA inválido ou expirado"
        assert "dados" not in r.json() or not r.json().get("dados")
        u = _usuario(db, novo_vistoriador.id)
        assert (u.mfa_secret, u.mfa_secret_pendente) == (None, MFA_TEST_SECRET)
