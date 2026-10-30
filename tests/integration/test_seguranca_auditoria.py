"""
Segurança — SEC-010 e SEC-013: trilha de auditoria e enumeração de e-mails no login

Cenários originais:
  - SEC-010: log_operacao aceitava o IP, mas nenhuma rota o passava; as edições
    gravavam só "update usuario", sem dizer o que mudou; e o logger de
    notificações escrevia e-mail, assunto e corpo da mensagem no log da aplicação.
  - SEC-013: com um e-mail inexistente o login não rodava o bcrypt e respondia
    bem mais rápido, revelando quais e-mails têm conta.

Regras verificadas:
  - todo evento gravado durante uma requisição traz o IP de origem
  - as edições registram os nomes dos campos alterados, nunca os valores
  - o log de notificações não tem e-mail nem conteúdo da mensagem
  - o login confere a senha contra um hash de mesmo custo quando a conta não existe
"""
import logging

import pytest

import app.auth as auth_mod
from app.models import LogOperacao, Usuario
from app.notification_service import notificar_admins, notificar_usuario
from app.serializers import log_operacao
from tests.conftest import TEST_SENHA, auth

LOGIN = "/api/v1/auth/login"
USUARIOS = "/api/v1/usuarios"


def _ultimo(db, acao: str) -> LogOperacao:
    db.expire_all()
    return db.query(LogOperacao).filter(LogOperacao.acao == acao).order_by(LogOperacao.created_at.desc()).first()


# ── SEC-010: IP de origem ────────────────────────────────────────────────────────

class TestIpDeOrigem:
    def test_login_falho_grava_ip(self, client, db, user_locatario):
        client.post(LOGIN, json={"email": user_locatario.email, "senha": "errada"})
        assert _ultimo(db, "login_falho").ip == "testclient"

    def test_login_grava_ip(self, client, db, user_locatario):
        client.post(LOGIN, json={"email": user_locatario.email, "senha": TEST_SENHA})
        assert _ultimo(db, "login").ip == "testclient"

    def test_mutacao_grava_ip(self, client, db, imovel, token_admin):
        client.put(f"/api/v1/imoveis/{imovel.id}", json={"titulo": "Novo"}, headers=auth(token_admin))
        assert _ultimo(db, "update").ip == "testclient"

    def test_fora_de_requisicao_fica_sem_ip(self, db):
        log_operacao(db, None, "seed", "sistema")
        assert _ultimo(db, "seed").ip is None

    def test_ip_explicito_tem_precedencia(self, db):
        log_operacao(db, None, "seed", "sistema", ip="10.0.0.1")
        assert _ultimo(db, "seed").ip == "10.0.0.1"


# ── SEC-010: campos alterados ────────────────────────────────────────────────────

class TestCamposAlterados:
    def test_admin_edita_usuario(self, client, db, user_locatario, token_admin):
        client.put(f"{USUARIOS}/{user_locatario.id}", json={"nome": "Outro", "senha": "senha-nova-123"},
                   headers=auth(token_admin))
        log = _ultimo(db, "update")
        assert log.payload == {"campos": ["nome", "senha_hash"]}
        assert "senha-nova-123" not in str(log.payload) and "Outro" not in str(log.payload)

    def test_valor_igual_nao_conta_como_alteracao(self, client, db, user_locatario, token_admin):
        client.put(f"{USUARIOS}/{user_locatario.id}", json={"nome": user_locatario.nome}, headers=auth(token_admin))
        assert _ultimo(db, "update").payload == {"campos": []}

    def test_proprio_perfil(self, client, db, token_locatario):
        client.patch(f"{USUARIOS}/me", json={"nome": "Novo Nome"}, headers=auth(token_locatario))
        assert _ultimo(db, "update").payload == {"campos": ["nome"]}

    def test_imovel_com_endereco(self, client, db, imovel, token_admin):
        body = {"titulo": "Novo", "endereco": {"rua": "Rua A", "cidade": "Recife", "estado": "PE"}}
        client.put(f"/api/v1/imoveis/{imovel.id}", json=body, headers=auth(token_admin))
        campos = _ultimo(db, "update").payload["campos"]
        assert "titulo" in campos and "endereco.rua" in campos and "endereco.cidade" in campos
        assert "codigo" not in campos


# ── SEC-010: PII no log de notificações ──────────────────────────────────────────

class TestLogDeNotificacoes:
    def test_sem_email_nem_conteudo(self, db, user_locatario, user_admin, caplog):
        with caplog.at_level(logging.INFO, logger="onecheck.notifications"):
            notificar_usuario(db, user_locatario.id, "Assunto sigiloso", "Corpo com CPF 123")
            notificar_admins(db, "Assunto sigiloso", "Corpo com CPF 123")
        texto = caplog.text
        assert user_locatario.id in texto and user_admin.id in texto
        for dado in (user_locatario.email, user_admin.email, "Assunto sigiloso", "CPF 123"):
            assert dado not in texto


# ── SEC-013: tempo do login ──────────────────────────────────────────────────────

class TestLoginSemEnumeracao:
    @pytest.fixture
    def conferencias(self, monkeypatch):
        chamadas = []
        original = auth_mod.verify_password

        def espiao(senha, senha_hash):
            chamadas.append(senha_hash)
            return original(senha, senha_hash)

        monkeypatch.setattr(auth_mod, "verify_password", espiao)
        return chamadas

    def test_email_inexistente_roda_o_bcrypt(self, client, db, conferencias):
        r = client.post(LOGIN, json={"email": "ninguem@test.com", "senha": TEST_SENHA})
        assert r.json()["sucesso"] is False
        assert conferencias == [auth_mod._HASH_FICTICIO]

    def test_conta_inativa_roda_o_bcrypt(self, client, db, user_locatario, conferencias):
        user_locatario.ativo = False
        db.flush()
        client.post(LOGIN, json={"email": user_locatario.email, "senha": TEST_SENHA})
        assert conferencias == [auth_mod._HASH_FICTICIO]

    def test_hash_ficticio_tem_o_custo_de_uma_senha_real(self):
        custo_real = auth_mod.hash_password("x").split("$")[2]
        assert auth_mod._HASH_FICTICIO.split("$")[2] == custo_real

    def test_hash_ficticio_nao_aceita_senha_nenhuma(self):
        assert auth_mod.conferir_credenciais(None, "") is False
        assert auth_mod.conferir_credenciais(None, TEST_SENHA) is False

    def test_mesma_resposta_para_email_inexistente_e_senha_errada(self, client, db, user_locatario):
        inexistente = client.post(LOGIN, json={"email": "ninguem@test.com", "senha": "x"})
        errada = client.post(LOGIN, json={"email": user_locatario.email, "senha": "x"})
        assert inexistente.status_code == errada.status_code
        assert inexistente.json() == errada.json()

    def test_senha_correta_continua_entrando(self, client, db, user_locatario):
        r = client.post(LOGIN, json={"email": user_locatario.email, "senha": TEST_SENHA})
        assert r.json()["sucesso"] is True
