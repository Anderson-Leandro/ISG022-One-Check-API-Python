"""
Segurança — SEC-028: direitos do titular (LGPD, art. 18)

Cenário original: não havia como o usuário obter os próprios dados nem pedir a eliminação deles. A
exclusão era só lógica (ativo=False) e mantinha nome, e-mail e CPF.

Regras verificadas (decisão do PO em 2026-11-11, ADR-0017):
  - GET /usuarios/me/dados devolve só os dados do próprio usuário, com o CPF completo, os contratos em
    que ele é locatário, as atualizações de problema que escreveu, os aceites e os próprios logs
  - POST /usuarios/me/anonimizar exige reautenticação (senha e, com autenticador, o código)
  - depois dela: nome 'Usuário removido', e-mail único e inválido, CPF apagado, MFA e senha
    inutilizados, conta desativada e sessões revogadas; os laudos e os logs continuam
  - o último admin ativo não pode se anonimizar
  - não existe rota para exportar ou anonimizar os dados de outro usuário
"""

import pytest

from app.models import AceiteChecklist, AtualizacaoProblema, Checklist, LogOperacao, Problema, Usuario
from tests.conftest import TEST_SENHA, auth, totp_now

API = "/api/v1/usuarios"
ANONIMIZADO = "Usuário removido"


def _anonimizar(client, token, senha=TEST_SENHA, codigo=None):
    corpo = {"senha": senha} if codigo is None else {"senha": senha, "codigo": codigo}
    return client.post(f"{API}/me/anonimizar", json=corpo, headers=auth(token))


@pytest.fixture
def cpf_locatario(db, user_locatario):
    user_locatario.cpf = "52998224725"
    db.commit()
    return "52998224725"


class TestExportacao:
    def test_devolve_os_proprios_dados_com_o_cpf_completo(self, client, token_locatario, user_locatario, cpf_locatario):
        r = client.get(f"{API}/me/dados", headers=auth(token_locatario))
        assert r.status_code == 200, r.text
        dados = r.json()["dados"]
        assert dados["usuario"]["id"] == user_locatario.id
        assert dados["usuario"]["email"] == user_locatario.email
        assert dados["usuario"]["cpf"] == cpf_locatario
        assert {"contratos", "aceites", "atualizacoes_de_problema", "logs"} <= set(dados)

    def test_traz_o_contrato_e_os_logs_do_proprio_usuario(self, client, db, token_locatario, contrato, user_locatario):
        db.add(LogOperacao(usuario_id=user_locatario.id, acao="login", entidade="usuario", ip="10.0.0.1"))
        db.commit()
        dados = client.get(f"{API}/me/dados", headers=auth(token_locatario)).json()["dados"]
        assert [c["id"] for c in dados["contratos"]] == [contrato.id]
        assert any(log["acao"] == "login" and log["ip"] == "10.0.0.1" for log in dados["logs"])

    def test_nao_traz_dados_de_outro_usuario(self, client, db, contrato, user_locatario, user_locatario_2, user_admin):
        from app.auth import create_access_token

        db.add(LogOperacao(usuario_id=user_locatario.id, acao="login", entidade="usuario", ip="10.9.9.9"))
        db.add(LogOperacao(usuario_id=user_admin.id, acao="login", entidade="usuario", ip="10.8.8.8"))
        db.commit()
        token_outro = create_access_token(user_locatario_2.id, user_locatario_2.role)
        r = client.get(f"{API}/me/dados", headers=auth(token_outro))
        dados = r.json()["dados"]
        assert dados["usuario"]["id"] == user_locatario_2.id
        assert dados["contratos"] == [] and dados["logs"] == []
        assert user_locatario.email not in r.text and "10.9.9.9" not in r.text and "10.8.8.8" not in r.text

    def test_traz_o_que_outra_pessoa_fez_sobre_a_conta_sem_expor_quem_fez(
        self, client, db, token_locatario, user_locatario, user_admin
    ):
        db.add(
            LogOperacao(
                usuario_id=user_admin.id,
                acao="update",
                entidade="usuario",
                entidade_id=user_locatario.id,
                detalhes="mfa_reset",
                ip="10.7.7.7",
            )
        )
        db.commit()
        r = client.get(f"{API}/me/dados", headers=auth(token_locatario))
        eventos = r.json()["dados"]["eventos_sobre_a_conta"]
        assert [(e["acao"], e["detalhes"]) for e in eventos] == [("update", "mfa_reset")]
        assert user_admin.id not in r.text and "10.7.7.7" not in r.text

    def test_sem_login_recebe_401(self, client):
        assert client.get(f"{API}/me/dados").status_code == 401


class TestLogSemEmail:
    def test_login_criacao_e_desativacao_nao_gravam_o_email(self, client, db, user_locatario, token_admin):
        client.post("/api/v1/auth/login", json={"email": user_locatario.email, "senha": TEST_SENHA})
        novo = client.post(
            API,
            json={"nome": "Nova Conta", "email": "nova@test.com", "senha": "Senha.Forte#2026", "role": "locatario"},
            headers=auth(token_admin),
        )
        assert novo.status_code == 200, novo.text
        client.delete(f"{API}/{novo.json()['dados']['id']}", headers=auth(token_admin))
        detalhes = [d or "" for (d,) in db.query(LogOperacao.detalhes).all()]
        assert not any(user_locatario.email in d or "nova@test.com" in d for d in detalhes)


class TestAnonimizacao:
    def test_anonimiza_desativa_e_revoga_as_sessoes(self, client, db, token_locatario, user_locatario, cpf_locatario):
        uid, email = user_locatario.id, user_locatario.email
        r = _anonimizar(client, token_locatario)
        assert r.status_code == 200, r.text
        db.expire_all()
        u = db.get(Usuario, uid)
        assert u.nome == ANONIMIZADO
        assert u.email != email and u.email.endswith(".invalid")
        assert u.cpf is None
        assert u.ativo is False and u.mfa_secret is None and u.mfa_enabled is False
        # o token antigo deixa de valer, e o login com a senha antiga falha
        assert client.get(f"{API}/me", headers=auth(token_locatario)).status_code == 401
        login = client.post("/api/v1/auth/login", json={"email": email, "senha": TEST_SENHA})
        assert login.status_code == 401

    def test_o_log_registra_a_anonimizacao_sem_dados_pessoais(
        self, client, db, token_locatario, user_locatario, cpf_locatario
    ):
        uid, email = user_locatario.id, user_locatario.email
        _anonimizar(client, token_locatario)
        log = db.query(LogOperacao).filter(LogOperacao.acao == "anonimizacao", LogOperacao.usuario_id == uid).one()
        assert email not in (log.detalhes or "") and cpf_locatario not in (log.detalhes or "")

    def test_laudo_e_aceite_continuam_e_mostram_usuario_removido(
        self, client, db, checklist, user_locatario, token_locatario, token_admin, monkeypatch
    ):
        from app.routers import checklists as rota_checklists

        db.add(AceiteChecklist(checklist_id=checklist.id, locatario_id=user_locatario.id, status="aceito"))
        pb = Problema(contrato_id=checklist.contrato_id, titulo="Infiltração")
        db.add(pb)
        db.flush()
        db.add(AtualizacaoProblema(problema_id=pb.id, autor_id=user_locatario.id, descricao="Piorou"))
        db.commit()
        assert _anonimizar(client, token_locatario).status_code == 200
        db.expire_all()
        assert db.get(Checklist, checklist.id) is not None
        assert db.query(AceiteChecklist).filter_by(checklist_id=checklist.id).one().locatario_id == user_locatario.id
        assert db.query(AtualizacaoProblema).filter_by(problema_id=pb.id).count() == 1

        # o PDF do laudo continua saindo, com o locatário anonimizado
        recebido = {}
        monkeypatch.setattr(
            rota_checklists, "gerar_pdf_checklist", lambda **kw: recebido.update(kw) or b"%PDF-1.4 teste"
        )
        r = client.get(f"/api/v1/checklists/{checklist.id}/pdf", headers=auth(token_admin))
        assert r.status_code == 200
        assert recebido["locatario"]["nome"] == ANONIMIZADO
        assert recebido["locatario"]["email"].endswith(".invalid")

    def test_senha_errada_recebe_403_e_nada_muda(self, client, db, token_locatario, user_locatario, cpf_locatario):
        r = _anonimizar(client, token_locatario, senha="senha-errada")
        assert r.status_code == 403
        db.expire_all()
        u = db.get(Usuario, user_locatario.id)
        assert u.nome == "Locatario Teste" and u.cpf == cpf_locatario and u.ativo is True

    def test_com_autenticador_exige_o_codigo(self, client, db, token_admin, user_admin, user_gestor):
        # há outro admin ativo: a regra do último admin não interfere neste teste
        user_gestor.role = "admin"
        db.commit()
        assert _anonimizar(client, token_admin).status_code == 403
        db.expire_all()
        assert db.get(Usuario, user_admin.id).ativo is True
        assert _anonimizar(client, token_admin, codigo=totp_now()).status_code == 200

    def test_ultimo_admin_ativo_nao_se_anonimiza(self, client, db, token_admin, user_admin):
        r = _anonimizar(client, token_admin, codigo=totp_now())
        assert r.status_code == 409
        db.expire_all()
        assert db.get(Usuario, user_admin.id).nome == "Admin Teste"

    def test_sem_login_recebe_401(self, client):
        assert client.post(f"{API}/me/anonimizar", json={"senha": "x"}).status_code == 401


class TestSoOProprioUsuario:
    @pytest.mark.parametrize("metodo,rota", [("GET", "/{id}/dados"), ("POST", "/{id}/anonimizar")])
    def test_nao_ha_rota_para_outro_usuario(self, client, token_admin, user_locatario, metodo, rota):
        r = client.request(metodo, API + rota.format(id=user_locatario.id), headers=auth(token_admin), json={})
        assert r.status_code in (404, 405)
        assert client.get(f"{API}/{user_locatario.id}", headers=auth(token_admin)).json()["dados"]["nome"] == (
            "Locatario Teste"
        )
