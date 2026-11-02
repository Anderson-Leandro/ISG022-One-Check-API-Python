"""
Segurança — SEC-011 e SEC-012: política de senha e regras de negócio no servidor

Cenários originais:
  - SEC-011: senhas novas só precisavam de 6 caracteres; "123456", "senha123" e
    "password" eram aceitas, e o bcrypt ignorava o que passasse de 72 bytes.
  - SEC-012: o locatário escolhia o status inicial do problema (inclusive
    "fechado"), e GET /dashboard devolvia os totais globais a qualquer perfil.

Regras verificadas:
  - criação de usuário e as três rotas de troca de senha exigem 10+ caracteres,
    no máximo 72 bytes, e recusam senhas comuns ou só com números e símbolos
  - o login continua aceitando a senha já cadastrada, mesmo fora da política
  - o problema nasce "aberto"; outro status no corpo é recusado
  - o dashboard aplica o recorte das listagens e devolve null no que o perfil não acessa
"""
from datetime import date

import pytest

from app.models import AgendamentoVistoria, Checklist, Contrato, Imovel, Problema, Usuario
from app.senhas import validar_senha
from tests.conftest import TEST_SENHA, _SENHA_HASH, auth

USUARIOS = "/api/v1/usuarios"
FORTE = "Vistoria-Casa-Azul-42"
FRACAS = [
    "123456",                 # curta
    "senha123",               # curta e comum
    "1234567890",             # só números
    "12/05/1990-11",          # data: só números e símbolos
    "Senha@2024!",            # palavra comum + números e símbolos
    "Password12345",
    "qwertyuiop",
    "aaaaaaaaaa",             # previsível
    "abababababab",
    "é" * 37,                 # 37 caracteres, 74 bytes
]


# ── SEC-011: política de senha ───────────────────────────────────────────────────

class TestValidarSenha:
    @pytest.mark.parametrize("senha", FRACAS)
    def test_recusa_fracas(self, senha):
        with pytest.raises(ValueError):
            validar_senha(senha)

    @pytest.mark.parametrize("senha", [FORTE, "correto cavalo bateria grampo", "Kq8#vT2!mZ", "a" + "bcdefghij" * 7])
    def test_aceita_fortes(self, senha):
        assert validar_senha(senha) == senha


class TestRotasDeSenha:
    @pytest.mark.parametrize("senha", ["senha123", "1234567890", "Senha@2024!"])
    def test_criar_usuario(self, client, token_admin, senha):
        r = client.post(USUARIOS, json={"nome": "N", "email": "n@test.com", "senha": senha, "role": "locatario"},
                        headers=auth(token_admin))
        assert r.status_code == 422

    def test_criar_usuario_com_senha_forte(self, client, token_admin):
        r = client.post(USUARIOS, json={"nome": "N", "email": "n@test.com", "senha": FORTE, "role": "locatario"},
                        headers=auth(token_admin))
        assert r.json()["sucesso"] is True

    def test_admin_troca_senha(self, client, user_locatario, token_admin):
        r = client.put(f"{USUARIOS}/{user_locatario.id}", json={"senha": "senha12345"}, headers=auth(token_admin))
        assert r.status_code == 422

    def test_put_me_senha(self, client, token_locatario):
        r = client.put(f"{USUARIOS}/me/senha", json={"senha_atual": TEST_SENHA, "nova_senha": "qwertyuiop"},
                       headers=auth(token_locatario))
        assert r.status_code == 422

    def test_patch_me_senha(self, client, token_locatario):
        r = client.patch(f"{USUARIOS}/me", json={"senha_atual": TEST_SENHA, "senha_nova": "1234567890"},
                         headers=auth(token_locatario))
        assert r.status_code == 422

    def test_mensagem_explica_a_regra(self, client, token_locatario):
        r = client.put(f"{USUARIOS}/me/senha", json={"senha_atual": TEST_SENHA, "nova_senha": "curta"},
                       headers=auth(token_locatario))
        assert "pelo menos 10 caracteres" in r.json()["detail"][0]["msg"]

    def test_login_aceita_senha_antiga_fora_da_politica(self, client, user_locatario):
        # TEST_SENHA ("senha123") não passaria na política, mas já está cadastrada
        r = client.post("/api/v1/auth/login", json={"email": user_locatario.email, "senha": TEST_SENHA})
        assert r.json()["sucesso"] is True


# ── SEC-012: status inicial do problema ──────────────────────────────────────────

class TestStatusInicialDoProblema:
    def _criar(self, client, contrato, token, **extra):
        return client.post(f"/api/v1/contratos/{contrato.id}/problemas", json={"titulo": "Vazamento", **extra},
                           headers=auth(token))

    @pytest.mark.parametrize("status", ["fechado", "resolvido", "em_andamento"])
    def test_locatario_nao_escolhe_o_status(self, client, db, contrato, token_locatario, status):
        r = self._criar(client, contrato, token_locatario, status=status)
        assert r.status_code == 422 and "status" in r.json()["erros"]
        assert db.query(Problema).count() == 0

    def test_admin_tambem_cria_aberto(self, client, contrato, token_admin):
        assert self._criar(client, contrato, token_admin, status="resolvido").status_code == 422

    def test_multipart_tambem(self, client, db, contrato, token_locatario):
        partes = {"titulo": (None, "X"), "status": (None, "fechado")}
        r = client.post(f"/api/v1/contratos/{contrato.id}/problemas", files=partes, headers=auth(token_locatario))
        assert r.status_code == 422 and "status" in r.json()["erros"]

    @pytest.mark.parametrize("extra", [{}, {"status": "aberto"}])
    def test_sem_status_ou_aberto(self, client, contrato, token_locatario, extra):
        r = self._criar(client, contrato, token_locatario, **extra)
        assert r.status_code == 201 and r.json()["dados"]["status"] == "aberto"


# ── SEC-012: dashboard por perfil ────────────────────────────────────────────────

@pytest.fixture
def cenario(db, contrato, user_vistoriador):
    """Dados do locatário/vistoriador de teste mais um contrato alheio com os mesmos tipos de registro."""
    db.add(Checklist(contrato_id=contrato.id, vistoriador_id=user_vistoriador.id, tipo="inicial",
                     status="pendente_aceite", data_vistoria=date.today()))
    db.add(Problema(contrato_id=contrato.id, titulo="Meu", status="aberto"))

    outro_loc = Usuario(nome="Outro", email="outro@test.com", senha_hash=_SENHA_HASH, role="locatario",
                        mfa_enabled=False, ativo=True)
    outro_vist = Usuario(nome="Outro V", email="outrov@test.com", senha_hash=_SENHA_HASH, role="vistoriador",
                         mfa_enabled=True, ativo=True)
    outro_im = Imovel(tipo="casa", titulo="Alheio", status="locado", garagem=False, garagem_vagas=0)
    db.add_all([outro_loc, outro_vist, outro_im])
    db.flush()
    outro_ct = Contrato(imovel_id=outro_im.id, locatario_id=outro_loc.id, data_inicio=date(2025, 1, 1),
                        data_fim=date(2025, 12, 31), status="ativo")
    db.add(outro_ct)
    db.flush()
    db.add_all([
        Checklist(contrato_id=outro_ct.id, vistoriador_id=outro_vist.id, tipo="inicial",
                  status="pendente_aceite", data_vistoria=date.today()),
        Problema(contrato_id=outro_ct.id, titulo="Alheio", status="aberto"),
        AgendamentoVistoria(contrato_id=outro_ct.id, tipo="inicial", data_agendada=date(2025, 1, 1)),
    ])
    db.flush()


def _dashboard(client, token) -> dict:
    return client.get("/api/v1/dashboard", headers=auth(token)).json()["dados"]


class TestDashboardPorPerfil:
    @pytest.mark.parametrize("token", ["token_admin", "token_gestor"])
    def test_admin_e_gestor_veem_tudo(self, client, cenario, token, request):
        assert _dashboard(client, request.getfixturevalue(token)) == {
            "imoveis_locados": 2, "checklists_pendentes": 2, "problemas_abertos": 2, "vistorias_agendadas": 3,
        }

    def test_visualizador_sem_problemas(self, client, cenario, token_visualizador):
        assert _dashboard(client, token_visualizador) == {
            "imoveis_locados": 2, "checklists_pendentes": 2, "problemas_abertos": None, "vistorias_agendadas": 3,
        }

    def test_locatario_so_o_proprio_contrato(self, client, cenario, token_locatario):
        assert _dashboard(client, token_locatario) == {
            "imoveis_locados": 1, "checklists_pendentes": 1, "problemas_abertos": 1, "vistorias_agendadas": None,
        }

    def test_vistoriador_so_onde_atua(self, client, cenario, token_vistoriador):
        assert _dashboard(client, token_vistoriador) == {
            "imoveis_locados": 1, "checklists_pendentes": 1, "problemas_abertos": None, "vistorias_agendadas": 2,
        }

    def test_vistoriador_sem_vistorias_ve_zero(self, client, contrato, token_vistoriador):
        assert _dashboard(client, token_vistoriador) == {
            "imoveis_locados": 0, "checklists_pendentes": 0, "problemas_abertos": None, "vistorias_agendadas": 0,
        }

    def test_imovel_inativo_nao_conta(self, client, db, contrato, imovel, token_admin):
        imovel.ativo = False
        db.flush()
        assert _dashboard(client, token_admin)["imoveis_locados"] == 0
