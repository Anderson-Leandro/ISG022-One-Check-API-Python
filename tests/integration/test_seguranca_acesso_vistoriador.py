"""
Segurança — SEC-004: leitura por ID ignora o vínculo do vistoriador (BOLA)

Cenário original: as listagens de contratos e imóveis restringiam o vistoriador
aos contratos em que ele tem vistoria, mas o acesso por ID só restringia o
locatário. Um vistoriador lia valor do aluguel, locatário, datas e endereço de
qualquer contrato pelo ID. GET /imoveis/{id}/comodos não restringia ninguém.

Regras verificadas (as mesmas das listagens):
  - vistoriador: só contratos/imóveis em que tem checklist atribuído
  - locatário: só o próprio contrato; imóvel só com contrato ativo
  - admin, gestor e visualizador mantêm a leitura (alcance do visualizador: decisão de negócio pendente)
"""
from datetime import date

import pytest

from app.auth import create_access_token
from app.models import Checklist, Contrato, Endereco, Imovel, Usuario
from tests.conftest import _SENHA_HASH, MFA_TEST_SECRET, auth


def _rotas_contrato(ct):
    return [f"/api/v1/contratos/{ct.id}", f"/api/v1/contratos/{ct.id}/agendamentos"]


def _rotas_imovel(im):
    return [f"/api/v1/imoveis/{im.id}", f"/api/v1/imoveis/{im.id}/endereco", f"/api/v1/imoveis/{im.id}/comodos"]


@pytest.fixture
def endereco(db, imovel):
    end = Endereco(imovel_id=imovel.id, rua="Rua A", numero="1", bairro="Centro", cidade="São Paulo", estado="SP", cep="01001000", ativo=True)
    db.add(end)
    db.flush()
    return end


@pytest.fixture
def outro_vistoriador(db):
    u = Usuario(nome="Outro Vistoriador", email="outro.vist@test.com", senha_hash=_SENHA_HASH,
                role="vistoriador", mfa_enabled=True, mfa_secret=MFA_TEST_SECRET)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def outro_imovel(db):
    """Imóvel com contrato de outro locatário e sem vistoria do vistoriador de teste."""
    im = Imovel(tipo="casa", titulo="Casa Alheia", codigo="CASA-9", status="locado", garagem=False, garagem_vagas=0)
    db.add(im)
    db.flush()
    dono = Usuario(nome="Outro Locatario", email="outro.loc@test.com", senha_hash=_SENHA_HASH, role="locatario")
    db.add(dono)
    db.flush()
    db.add(Contrato(imovel_id=im.id, locatario_id=dono.id, data_inicio=date(2025, 1, 1),
                    data_fim=date(2025, 12, 31), valor_mensal=9000, status="ativo"))
    db.flush()
    return im


class TestVistoriadorSemVinculo:
    def test_contrato_por_id_negado(self, client, contrato, endereco, token_vistoriador):
        for url in _rotas_contrato(contrato):
            assert client.get(url, headers=auth(token_vistoriador)).status_code == 403, url

    def test_imovel_por_id_negado(self, client, contrato, imovel, endereco, token_vistoriador):
        for url in _rotas_imovel(imovel):
            assert client.get(url, headers=auth(token_vistoriador)).status_code == 403, url

    def test_vistoria_de_outro_vistoriador_nao_da_acesso(
        self, client, db, contrato, imovel, endereco, outro_vistoriador, token_vistoriador
    ):
        db.add(Checklist(contrato_id=contrato.id, vistoriador_id=outro_vistoriador.id, tipo="inicial", status="em_preenchimento"))
        db.flush()
        for url in _rotas_contrato(contrato) + _rotas_imovel(imovel):
            assert client.get(url, headers=auth(token_vistoriador)).status_code == 403, url

    def test_resposta_negada_nao_expoe_dados(self, client, contrato, token_vistoriador):
        r = client.get(f"/api/v1/contratos/{contrato.id}", headers=auth(token_vistoriador))
        assert "1500" not in r.text and "valor_mensal" not in r.text


class TestVistoriadorComVinculo:
    def test_le_contrato_e_imovel_da_propria_vistoria(self, client, checklist, contrato, imovel, endereco, token_vistoriador):
        for url in _rotas_contrato(contrato) + _rotas_imovel(imovel):
            r = client.get(url, headers=auth(token_vistoriador))
            assert r.status_code == 200 and r.json()["sucesso"] is True, url

    def test_vistoria_concluida_mantem_acesso(self, client, db, checklist, contrato, token_vistoriador):
        checklist.status = "aceito"
        db.flush()
        assert client.get(f"/api/v1/contratos/{contrato.id}", headers=auth(token_vistoriador)).status_code == 200


class TestLocatario:
    def test_comodos_de_imovel_alheio_negado(self, client, outro_imovel, token_locatario):
        r = client.get(f"/api/v1/imoveis/{outro_imovel.id}/comodos", headers=auth(token_locatario))
        assert r.status_code == 403

    def test_comodos_do_proprio_imovel(self, client, contrato, imovel, token_locatario):
        r = client.get(f"/api/v1/imoveis/{imovel.id}/comodos", headers=auth(token_locatario))
        assert r.json()["sucesso"] is True

    def test_contrato_alheio_continua_negado(self, client, db, outro_imovel, token_locatario):
        ct = db.query(Contrato).filter(Contrato.imovel_id == outro_imovel.id).first()
        assert client.get(f"/api/v1/contratos/{ct.id}", headers=auth(token_locatario)).status_code == 403


class TestPerfisComLeituraGeral:
    @pytest.mark.parametrize("perfil", ["admin", "gestor", "visualizador"])
    def test_leitura_mantida(self, client, db, contrato, imovel, endereco, perfil):
        u = Usuario(nome=perfil, email=f"{perfil}.leitura@test.com", senha_hash=_SENHA_HASH, role=perfil)
        db.add(u)
        db.flush()
        token = create_access_token(u.id, u.role)
        for url in _rotas_contrato(contrato) + _rotas_imovel(imovel):
            r = client.get(url, headers=auth(token))
            assert r.status_code == 200 and r.json()["sucesso"] is True, (perfil, url)
