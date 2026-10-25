"""
Segurança — N6: sem limite de tentativas em login, MFA e reautenticação

Cenário original: POST /auth/login e /auth/mfa/verify aceitavam tentativas
ilimitadas. Com o temp_token válido por 10 minutos e valid_window=1 (3 códigos
aceitos por vez), dava para varrer senhas e códigos TOTP. A reautenticação
criada em N5 (senha + código para desligar o MFA) herdava o mesmo problema.

Regras verificadas:
  - por conta: RATE_LIMIT_FALHAS_CONTA falhas na janela bloqueiam novas tentativas (429)
  - por IP: RATE_LIMIT_FALHAS_IP falhas na janela bloqueiam o IP (429)
  - durante o bloqueio nem a credencial correta é aceita (não vira oráculo)
  - sucesso zera o contador da conta; a janela expira sozinha
  - falhas de MFA ficam registradas no log de operações
"""
import pytest

from app.auth import create_temp_token
from app.config import RATE_LIMIT_FALHAS_CONTA, RATE_LIMIT_FALHAS_IP, RATE_LIMIT_JANELA_MIN
from app.models import LogOperacao, Usuario
from app.rate_limit import limitador
from tests.conftest import MFA_TEST_SECRET, TEST_SENHA, _SENHA_HASH, auth, totp_now

AUTH = "/api/v1/auth"


def _codigo_errado() -> str:
    import time
    import pyotp
    totp = pyotp.TOTP(MFA_TEST_SECRET)
    validos = {totp.at(time.time() + d) for d in (-30, 0, 30)}
    return next(c for c in ("000000", "111111", "222222", "333333") if c not in validos)


def _login(client, email, senha):
    return client.post(f"{AUTH}/login", json={"email": email, "senha": senha})


def _esgota_conta(client, email):
    for _ in range(RATE_LIMIT_FALHAS_CONTA):
        assert _login(client, email, "senha-errada").status_code == 200


# ── Login por conta ──────────────────────────────────────────────────────────────

class TestLoginPorConta:
    def test_bloqueia_apos_limite_mesmo_com_senha_correta(self, client, user_locatario):
        _esgota_conta(client, user_locatario.email)
        r = _login(client, user_locatario.email, TEST_SENHA)
        assert r.status_code == 429
        assert int(r.headers["Retry-After"]) > 0
        assert "access_token" not in r.text

    def test_email_com_caixa_diferente_conta_como_a_mesma_conta(self, client, user_locatario):
        _esgota_conta(client, user_locatario.email.upper())
        assert _login(client, user_locatario.email, TEST_SENHA).status_code == 429

    def test_outra_conta_nao_e_afetada(self, client, user_locatario, user_visualizador):
        _esgota_conta(client, user_locatario.email)
        r = _login(client, user_visualizador.email, TEST_SENHA)
        assert r.json()["sucesso"] is True

    def test_sucesso_zera_o_contador(self, client, user_locatario):
        for _ in range(RATE_LIMIT_FALHAS_CONTA - 1):
            _login(client, user_locatario.email, "senha-errada")
        assert _login(client, user_locatario.email, TEST_SENHA).json()["sucesso"] is True
        for _ in range(RATE_LIMIT_FALHAS_CONTA - 1):
            _login(client, user_locatario.email, "senha-errada")
        assert _login(client, user_locatario.email, TEST_SENHA).json()["sucesso"] is True

    def test_bloqueio_expira_com_a_janela(self, client, user_locatario, monkeypatch):
        agora = [1_000_000.0]
        monkeypatch.setattr(limitador, "_agora", lambda: agora[0])
        _esgota_conta(client, user_locatario.email)
        assert _login(client, user_locatario.email, TEST_SENHA).status_code == 429
        agora[0] += RATE_LIMIT_JANELA_MIN * 60 + 1
        assert _login(client, user_locatario.email, TEST_SENHA).json()["sucesso"] is True


# ── Login por IP ─────────────────────────────────────────────────────────────────

class TestLoginPorIp:
    def test_varredura_de_contas_bloqueia_o_ip(self, client, user_locatario):
        # cada e-mail falha menos que o limite por conta: só o limite por IP pega
        for i in range(RATE_LIMIT_FALHAS_IP):
            _login(client, f"alvo{i}@test.com", "senha-errada")
        r = _login(client, user_locatario.email, TEST_SENHA)
        assert r.status_code == 429


# ── MFA ──────────────────────────────────────────────────────────────────────────

class TestMfaVerify:
    def test_bloqueia_apos_limite_mesmo_com_codigo_correto(self, client, user_admin):
        temp = create_temp_token(user_admin.id)
        for _ in range(RATE_LIMIT_FALHAS_CONTA):
            r = client.post(f"{AUTH}/mfa/verify", json={"temp_token": temp, "codigo": _codigo_errado()})
            assert r.json()["sucesso"] is False
        r = client.post(f"{AUTH}/mfa/verify", json={"temp_token": temp, "codigo": totp_now()})
        assert r.status_code == 429
        assert "access_token" not in r.text

    def test_novo_temp_token_nao_zera_o_limite(self, client, user_admin):
        for _ in range(RATE_LIMIT_FALHAS_CONTA):
            client.post(f"{AUTH}/mfa/verify", json={"temp_token": create_temp_token(user_admin.id), "codigo": _codigo_errado()})
        r = client.post(f"{AUTH}/mfa/verify", json={"temp_token": create_temp_token(user_admin.id), "codigo": totp_now()})
        assert r.status_code == 429

    def test_falha_de_mfa_e_registrada_no_log(self, client, db, user_admin):
        client.post(f"{AUTH}/mfa/verify", json={"temp_token": create_temp_token(user_admin.id), "codigo": _codigo_errado()})
        db.expire_all()
        assert db.query(LogOperacao).filter(LogOperacao.acao == "mfa_falho", LogOperacao.usuario_id == user_admin.id).count() == 1

    def test_ativacao_no_primeiro_acesso_tambem_e_limitada(self, client, db):
        from app.auth import create_mfa_setup_token
        u = Usuario(nome="Novo", email="novo_rl@test.com", senha_hash=_SENHA_HASH, role="vistoriador",
                    mfa_enabled=True, mfa_secret=None, ativo=True)
        db.add(u)
        db.flush()
        temp = create_mfa_setup_token(u.id)
        client.get(f"{AUTH}/mfa/setup-login", params={"temp_token": temp})
        for _ in range(RATE_LIMIT_FALHAS_CONTA):
            client.post(f"{AUTH}/mfa/activate-login", json={"temp_token": temp, "codigo": "000000"})
        r = client.post(f"{AUTH}/mfa/activate-login", json={"temp_token": temp, "codigo": "000000"})
        assert r.status_code == 429


# ── Reautenticação ───────────────────────────────────────────────────────────────

class TestReautenticacao:
    @pytest.mark.parametrize("metodo,url", [
        ("post", f"{AUTH}/mfa/desabilitar"),
        ("delete", "/api/v1/usuarios/me/mfa"),
    ])
    def test_desativar_mfa_limita_tentativas_de_senha(self, client, token_locatario, metodo, url):
        for _ in range(RATE_LIMIT_FALHAS_CONTA):
            r = client.request(metodo.upper(), url, json={"senha": "senha-errada"}, headers=auth(token_locatario))
            assert r.json()["sucesso"] is False
        r = client.request(metodo.upper(), url, json={"senha": TEST_SENHA}, headers=auth(token_locatario))
        assert r.status_code == 429

    def test_troca_de_senha_limita_tentativas(self, client, token_locatario):
        url = "/api/v1/usuarios/me/senha"
        for _ in range(RATE_LIMIT_FALHAS_CONTA):
            client.put(url, json={"senha_atual": "senha-errada", "nova_senha": "nova-senha-123"}, headers=auth(token_locatario))
        r = client.put(url, json={"senha_atual": TEST_SENHA, "nova_senha": "nova-senha-123"}, headers=auth(token_locatario))
        assert r.status_code == 429

    def test_troca_de_autenticador_limita_codigo_atual(self, client, token_admin):
        import pyotp
        novo = client.post(f"{AUTH}/mfa/setup", headers=auth(token_admin)).json()["dados"]["secret"]
        for _ in range(RATE_LIMIT_FALHAS_CONTA):
            r = client.post(
                f"{AUTH}/mfa/activate",
                json={"codigo": pyotp.TOTP(novo).now(), "codigo_atual": _codigo_errado()},
                headers=auth(token_admin),
            )
            assert r.json()["sucesso"] is False
        r = client.post(
            f"{AUTH}/mfa/activate",
            json={"codigo": pyotp.TOTP(novo).now(), "codigo_atual": totp_now()},
            headers=auth(token_admin),
        )
        assert r.status_code == 429
