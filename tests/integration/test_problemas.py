from datetime import date
import io
import pytest

from app.models import Contrato, Imovel, ImovelComodo, Problema, Usuario
from tests.conftest import auth

BASE_CONTRATOS = "/api/v1/contratos"
BASE_PROBLEMAS = "/api/v1/problemas"


@pytest.fixture
def outro_locatario(db):
    from tests.conftest import _SENHA_HASH
    u = Usuario(
        nome="Outro Locatario",
        email="outro_loc@teste.com",
        senha_hash=_SENHA_HASH,
        role="locatario",
        mfa_enabled=False,
        ativo=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def token_outro_locatario(outro_locatario):
    from app.auth import create_access_token
    return create_access_token(outro_locatario.id, outro_locatario.role)


@pytest.fixture
def outro_contrato(db, outro_locatario):
    im = Imovel(tipo="Casa", status="alugado", ativo=True)
    db.add(im)
    db.flush()
    com = ImovelComodo(imovel_id=im.id, tipo="Quarto", nome="Quarto 1")
    db.add(com)
    db.flush()
    ct = Contrato(
        imovel_id=im.id,
        locatario_id=outro_locatario.id,
        data_inicio=date(2026, 1, 1),
        data_fim=date(2027, 1, 1),
        status="ativo",
    )
    db.add(ct)
    db.commit()
    db.refresh(ct)
    return ct


@pytest.fixture
def comodo_contrato(db, contrato):
    com = ImovelComodo(imovel_id=contrato.imovel_id, tipo="Sala", nome="Sala Principal")
    db.add(com)
    db.commit()
    db.refresh(com)
    return com


@pytest.fixture
def comodo_alheio(db, outro_contrato):
    com = ImovelComodo(imovel_id=outro_contrato.imovel_id, tipo="Cozinha", nome="Cozinha Alheia")
    db.add(com)
    db.commit()
    db.refresh(com)
    return com


@pytest.fixture
def problema_criado(client, contrato, comodo_contrato, token_locatario):
    r = client.post(
        f"{BASE_CONTRATOS}/{contrato.id}/problemas",
        json={
            "comodo_id": comodo_contrato.id,
            "titulo": "Vazamento na pia",
            "descricao": "A torneira da pia está vazando sem parar.",
        },
        headers=auth(token_locatario),
    )
    assert r.status_code == 201
    return r.json()["dados"]


# ── POST /contratos/{id}/problemas ──────────────────────────────────────────────

class TestCriarProblema:
    def test_locatario_cria_problema_valido_e_retorna_201(
        self, client, contrato, comodo_contrato, token_locatario
    ):
        r = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/problemas",
            json={
                "comodo_id": comodo_contrato.id,
                "titulo": "Vazamento na torneira",
                "descricao": "A torneira da sala está vazando constantemente.",
            },
            headers=auth(token_locatario),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["contrato_id"] == contrato.id
        assert data["dados"]["comodo_id"] == comodo_contrato.id
        assert data["dados"]["titulo"] == "Vazamento na torneira"
        assert data["dados"]["status"] == "aberto"

    def test_admin_cria_problema_no_contrato(
        self, client, contrato, comodo_contrato, token_admin
    ):
        r = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/problemas",
            json={
                "comodo_id": comodo_contrato.id,
                "titulo": "Problema registrado pelo admin",
                "descricao": "Admin identificou rachadura na parede.",
            },
            headers=auth(token_admin),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["status"] == "aberto"

    def test_body_vazio_ao_criar_problema_retorna_422(
        self, client, contrato, token_locatario
    ):
        r = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/problemas",
            json={},
            headers=auth(token_locatario),
        )
        assert r.status_code == 422
        data = r.json()
        assert data["sucesso"] is False

    def test_comodo_nao_pertencente_ao_imovel_retorna_404(
        self, client, contrato, comodo_alheio, token_locatario
    ):
        r = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/problemas",
            json={
                "comodo_id": comodo_alheio.id,
                "titulo": "Tentativa com cômodo alheio",
                "descricao": "Descrição de teste para validação.",
            },
            headers=auth(token_locatario),
        )
        assert r.status_code == 404
        data = r.json()
        assert data["sucesso"] is False

    def test_locatario_alheio_recebe_403(
        self, client, contrato, comodo_contrato, token_outro_locatario
    ):
        r = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/problemas",
            json={
                "comodo_id": comodo_contrato.id,
                "titulo": "Tentativa de outro locatário",
                "descricao": "Descrição de teste para validação.",
            },
            headers=auth(token_outro_locatario),
        )
        assert r.status_code == 403
        data = r.json()
        assert data["sucesso"] is False

    def test_contrato_inexistente_retorna_404(self, client, token_admin):
        r = client.post(
            f"{BASE_CONTRATOS}/00000000-0000-4000-a000-000000000000/problemas",
            json={"titulo": "Problema X", "descricao": "Descrição válida."},
            headers=auth(token_admin),
        )
        assert r.status_code == 404
        data = r.json()
        assert data["sucesso"] is False

    def test_contrato_encerrado_retorna_422(
        self, client, db, contrato, comodo_contrato, token_admin
    ):
        contrato.status = "encerrado"
        db.commit()
        r = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/problemas",
            json={
                "comodo_id": comodo_contrato.id,
                "titulo": "Problema em contrato encerrado",
                "descricao": "Descrição de teste para validação.",
            },
            headers=auth(token_admin),
        )
        assert r.status_code == 422
        data = r.json()
        assert data["sucesso"] is False
        assert "ativos" in data["erro"].lower()

    def test_upload_foto_problema_multipart(
        self, client, contrato, comodo_contrato, token_locatario
    ):
        fake_file = io.BytesIO(b"fake image data jpg")
        r = client.post(
            f"{BASE_CONTRATOS}/{contrato.id}/problemas",
            data={
                "comodo_id": comodo_contrato.id,
                "titulo": "Infiltração com foto",
                "descricao": "Infiltração grave registrada com foto.",
            },
            files={"foto": ("infiltracao.jpg", fake_file, "image/jpeg")},
            headers=auth(token_locatario),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["foto_url"] is not None


# ── GET /contratos/{id}/problemas ───────────────────────────────────────────────

class TestListarProblemas:
    def test_admin_lista_problemas(self, client, contrato, problema_criado, token_admin):
        r = client.get(f"{BASE_CONTRATOS}/{contrato.id}/problemas", headers=auth(token_admin))
        assert r.status_code == 200
        data = r.json()
        assert data["sucesso"] is True
        assert len(data["dados"]) >= 1

    def test_locatario_lista_seus_problemas(self, client, contrato, problema_criado, token_locatario):
        r = client.get(f"{BASE_CONTRATOS}/{contrato.id}/problemas", headers=auth(token_locatario))
        assert r.status_code == 200
        data = r.json()
        assert data["sucesso"] is True
        assert len(data["dados"]) >= 1

    def test_locatario_alheio_recebe_403(self, client, contrato, problema_criado, token_outro_locatario):
        r = client.get(f"{BASE_CONTRATOS}/{contrato.id}/problemas", headers=auth(token_outro_locatario))
        assert r.status_code == 403
        data = r.json()
        assert data["sucesso"] is False


# ── GET /problemas/{id} ─────────────────────────────────────────────────────────

class TestBuscarProblemaPorId:
    def test_admin_busca_problema_por_id(self, client, problema_criado, token_admin):
        r = client.get(f"{BASE_PROBLEMAS}/{problema_criado['id']}", headers=auth(token_admin))
        assert r.status_code == 200
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["id"] == problema_criado["id"]

    def test_locatario_busca_proprio_problema(self, client, problema_criado, token_locatario):
        r = client.get(f"{BASE_PROBLEMAS}/{problema_criado['id']}", headers=auth(token_locatario))
        assert r.status_code == 200
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["id"] == problema_criado["id"]

    def test_locatario_alheio_recebe_403(self, client, problema_criado, token_outro_locatario):
        r = client.get(f"{BASE_PROBLEMAS}/{problema_criado['id']}", headers=auth(token_outro_locatario))
        assert r.status_code == 403
        data = r.json()
        assert data["sucesso"] is False

    def test_problema_inexistente_retorna_404(self, client, token_admin):
        r = client.get(f"{BASE_PROBLEMAS}/00000000-0000-4000-a000-000000000000", headers=auth(token_admin))
        assert r.status_code == 404


# ── PATCH /problemas/{id}/status ────────────────────────────────────────────────

class TestAtualizarStatusProblema:
    def test_admin_altera_status_para_em_andamento_e_resolvido(self, client, problema_criado, token_admin):
        r = client.patch(
            f"{BASE_PROBLEMAS}/{problema_criado['id']}/status",
            json={"status": "em_andamento"},
            headers=auth(token_admin),
        )
        assert r.status_code == 200
        assert r.json()["dados"]["status"] == "em_andamento"

        r2 = client.patch(
            f"{BASE_PROBLEMAS}/{problema_criado['id']}/status",
            json={"status": "resolvido"},
            headers=auth(token_admin),
        )
        assert r2.status_code == 200
        assert r2.json()["dados"]["status"] == "resolvido"

    def test_status_invalido_retorna_422(self, client, problema_criado, token_admin):
        r = client.patch(
            f"{BASE_PROBLEMAS}/{problema_criado['id']}/status",
            json={"status": "status_inexistente"},
            headers=auth(token_admin),
        )
        assert r.status_code == 422
        data = r.json()
        assert data["sucesso"] is False

    def test_locatario_nao_pode_alterar_status_e_recebe_403(self, client, problema_criado, token_locatario):
        r = client.patch(
            f"{BASE_PROBLEMAS}/{problema_criado['id']}/status",
            json={"status": "resolvido"},
            headers=auth(token_locatario),
        )
        assert r.status_code == 403


# ── POST e GET /problemas/{id}/atualizacoes ─────────────────────────────────────

class TestAtualizacoesProblema:
    def test_admin_adiciona_atualizacoes_e_lista_cronologicamente(
        self, client, problema_criado, token_admin, token_locatario
    ):
        # 1. Cria primeira atualização
        r1 = client.post(
            f"{BASE_PROBLEMAS}/{problema_criado['id']}/atualizacoes",
            json={"descricao": "Encaminhamos um técnico para verificar o vazamento."},
            headers=auth(token_admin),
        )
        assert r1.status_code == 201
        data1 = r1.json()
        assert data1["sucesso"] is True
        assert data1["dados"]["problema_id"] == problema_criado["id"]

        # 2. Cria segunda atualização com foto multipart
        fake_file = io.BytesIO(b"foto reparo")
        r2 = client.post(
            f"{BASE_PROBLEMAS}/{problema_criado['id']}/atualizacoes",
            data={"descricao": "O técnico trocou a vedação da torneira."},
            files={"foto": ("reparo.jpg", fake_file, "image/jpeg")},
            headers=auth(token_admin),
        )
        assert r2.status_code == 201

        # 3. Locatário lista atualizações do seu problema
        r_list = client.get(
            f"{BASE_PROBLEMAS}/{problema_criado['id']}/atualizacoes",
            headers=auth(token_locatario),
        )
        assert r_list.status_code == 200
        items = r_list.json()["dados"]
        assert len(items) >= 2
        assert items[0]["descricao"] == "Encaminhamos um técnico para verificar o vazamento."

    def test_descricao_curta_retorna_422(self, client, problema_criado, token_admin):
        r = client.post(
            f"{BASE_PROBLEMAS}/{problema_criado['id']}/atualizacoes",
            json={"descricao": "Oi"},
            headers=auth(token_admin),
        )
        assert r.status_code == 422

    def test_locatario_nao_pode_adicionar_atualizacao(self, client, problema_criado, token_locatario):
        r = client.post(
            f"{BASE_PROBLEMAS}/{problema_criado['id']}/atualizacoes",
            json={"descricao": "Tentativa de atualização pelo locatário."},
            headers=auth(token_locatario),
        )
        assert r.status_code == 403

    def test_vistoriador_nao_pode_adicionar_atualizacao(self, client, problema_criado, token_vistoriador):
        r = client.post(
            f"{BASE_PROBLEMAS}/{problema_criado['id']}/atualizacoes",
            json={"descricao": "Tentativa pelo vistoriador."},
            headers=auth(token_vistoriador),
        )
        assert r.status_code == 403

    def test_locatario_alheio_nao_pode_listar_atualizacoes(
        self, client, problema_criado, token_outro_locatario
    ):
        r = client.get(
            f"{BASE_PROBLEMAS}/{problema_criado['id']}/atualizacoes",
            headers=auth(token_outro_locatario),
        )
        assert r.status_code == 403
